"""
metrics.py – Live hardware stats from the host machine (primary data center server).

Fixes for Windows accuracy:
  - Temperature: Uses Windows WMI (MSAcpi_ThermalZoneTemperature) for real sensor data.
  - Network: Picks only the BEST active physical adapter (highest traffic), 
    excluding loopback, virtual, Bluetooth, and tunnel adapters.
"""

import time
import psutil
import platform

# ── WMI temperature (Windows only) ───────────────────────────────────────────
_wmi_conn = None

def _wmi_temperature() -> float | None:
    """Try to read CPU thermal sensor via Windows WMI. Returns °C or None."""
    global _wmi_conn
    try:
        # Only attempt WMI on Windows
        if platform.system() != "Windows":
            return None

        if _wmi_conn is None:
            import wmi
            _wmi_conn = wmi.WMI(namespace="root\\wmi")
        zones = _wmi_conn.MSAcpi_ThermalZoneTemperature()
        if zones:
            # Convert: raw value is in tenths of Kelvin
            temps = [(z.CurrentTemperature / 10.0) - 273.15 for z in zones]
            return round(float(sum(temps) / len(temps)), 1)
    except ImportError:
        # WMI module not installed (e.g., on Linux/Render)
        pass
    except Exception:
        pass
    return None


def _get_temperature() -> float:
    """
    Real CPU temperature with layered fallback:
    1. Windows WMI sensor (most accurate)
    2. psutil sensors_temperatures (Linux/macOS)
    3. CPU-load-derived estimate (last resort)
    """
    # 1. WMI (Windows real sensor)
    wmi_temp = _wmi_temperature()
    if wmi_temp is not None and 10 < wmi_temp < 110:
        return wmi_temp

    # 2. psutil sensors
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for key in ("coretemp", "k10temp", "acpitz", "cpu_thermal"):
                if key in temps:
                    readings = [e.current for e in temps[key] if e.current]
                    if readings:
                        return round(float(sum(readings) / len(readings)), 1)
            for entries in temps.values():
                readings = [e.current for e in entries if e.current]
                if readings:
                    return round(float(sum(readings) / len(readings)), 1)
    except Exception:
        pass

    # 3. Estimate from CPU load (40°C idle → ~95°C at full load)
    cpu = psutil.cpu_percent(interval=0)
    return round(40.0 + cpu * 0.55, 1)


# ── Network – best physical adapter only ────────────────────────────────────
# Keywords that indicate virtual/skippable adapters
_SKIP_KEYWORDS = [
    "loopback", "isatap", "teredo", "6to4", "bluetooth",
    "vmware", "virtualbox", "vethernet", "vbox", "hyper-v",
    "pseudo", "tunnel", "miniport", "wan miniport",
]

_prev_net_nic: str | None = None
_prev_net_stat = None
_prev_ts = time.time()


def _pick_best_nic(per_nic: dict, if_stats: dict) -> str | None:
    """Pick the physical NIC with the highest traffic that is currently UP."""
    best_name, best_bytes = None, -1
    for name, st in per_nic.items():
        nl = name.lower()
        if any(kw in nl for kw in _SKIP_KEYWORDS):
            continue
            
        # Must be UP to be considered
        stat = if_stats.get(name)
        if stat and not stat.isup:
            continue
            
        total = st.bytes_sent + st.bytes_recv
        if total > best_bytes:
            best_bytes = total
            best_name = name
    return best_name


def _bytes_to_mbps(byte_delta: float, elapsed_s: float) -> float:
    if elapsed_s <= 0:
        return 0.0
    return round((byte_delta * 8) / (elapsed_s * 1_000_000), 3)


def _get_network() -> dict:
    global _prev_net_nic, _prev_net_stat, _prev_ts

    now_ts = time.time()
    elapsed = max(0.001, now_ts - _prev_ts)

    per_nic = psutil.net_io_counters(pernic=True)
    try:
        if_stats = psutil.net_if_stats()
    except Exception:
        if_stats = {}

    # Check if the currently sticky NIC is still UP
    current_up = False
    if _prev_net_nic and _prev_net_nic in if_stats:
        current_up = if_stats[_prev_net_nic].isup

    # Choose best NIC if we don't have one, or the current one went down
    if _prev_net_nic is None or _prev_net_nic not in per_nic or not current_up:
        _prev_net_nic = _pick_best_nic(per_nic, if_stats)
        
        # We just switched NICs, speeds can't be reliably calculated this tick
        _prev_net_stat = per_nic.get(_prev_net_nic) if _prev_net_nic else None
        _prev_ts = now_ts
        return {
            "upload_mbps":   0.0,
            "download_mbps": 0.0,
            "pkts_sent":     _prev_net_stat.packets_sent if _prev_net_stat else 0,
            "pkts_recv":     _prev_net_stat.packets_recv if _prev_net_stat else 0,
            "nic_name":      _prev_net_nic or "OFFLINE",
        }

    now_stat  = per_nic.get(_prev_net_nic) if _prev_net_nic else None
    prev_stat = _prev_net_stat

    if now_stat and prev_stat:
        upload   = _bytes_to_mbps(now_stat.bytes_sent - prev_stat.bytes_sent, elapsed)
        download = _bytes_to_mbps(now_stat.bytes_recv - prev_stat.bytes_recv, elapsed)
        pkts_sent = now_stat.packets_sent
        pkts_recv = now_stat.packets_recv
    else:
        upload = download = 0.0
        pkts_sent = pkts_recv = 0

    _prev_net_stat = now_stat
    _prev_ts = now_ts

    return {
        "upload_mbps":   max(0.0, upload),
        "download_mbps": max(0.0, download),
        "pkts_sent":     pkts_sent,
        "pkts_recv":     pkts_recv,
        "nic_name":      _prev_net_nic or "OFFLINE",
    }


# ── Power estimate ────────────────────────────────────────────────────────────
def _compute_power(cpu_pct: float, temp_c: float) -> float:
    base, tdp = 15.0, 45.0
    cpu_factor  = (cpu_pct / 100.0) * 0.65
    temp_factor = max(0.0, (temp_c - 40.0) / 60.0) * 0.20
    return round(base + tdp * (0.15 + cpu_factor + temp_factor), 1)


def _compute_failure_risk(cpu: float, mem: float, temp: float) -> float:
    risk = 0.0
    if cpu  > 90: risk += 40
    elif cpu > 75: risk += 20
    elif cpu > 60: risk += 8
    if mem  > 90: risk += 30
    elif mem > 80: risk += 15
    elif mem > 70: risk += 5
    if temp > 85: risk += 30
    elif temp > 70: risk += 15
    elif temp > 60: risk += 5
    return min(100.0, round(risk, 1))


def _compute_health(cpu, mem, temp, disk, risk) -> int:
    penalty = cpu*0.30 + mem*0.25 + min(temp,100)*0.20 + disk*0.05 + risk*0.20
    return max(0, min(100, round(100 - penalty)))


# ── Public API ────────────────────────────────────────────────────────────────
# Warm up CPU percent (non-blocking after first call)
psutil.cpu_percent(interval=None)


def get_host_metrics() -> dict:
    """Return all live host (primary server) metrics."""
    cpu_pct   = psutil.cpu_percent(interval=None)
    cpu_freq  = psutil.cpu_freq()
    cpu_cores = psutil.cpu_count(logical=True)
    cpu_phys  = psutil.cpu_count(logical=False) or 1

    vm = psutil.virtual_memory()
    mem_pct      = vm.percent
    mem_total_gb = round(vm.total / 1e9, 1)
    mem_used_gb  = round(vm.used  / 1e9, 1)

    temp = _get_temperature()

    disk = psutil.disk_usage("/")
    disk_pct      = disk.percent
    disk_total_gb = round(disk.total / 1e9, 1)
    disk_used_gb  = round(disk.used  / 1e9, 1)

    net = _get_network()
    nic_down = (net["nic_name"] in ["OFFLINE", "unknown", None])

    power = _compute_power(cpu_pct, temp)
    risk  = _compute_failure_risk(cpu_pct, mem_pct, temp)
    
    if nic_down:
        risk = min(100.0, risk + 50.0) # Network link down is critical
        
    health= _compute_health(cpu_pct, mem_pct, temp, disk_pct, risk)

    return {
        "name":         platform.node() or "Primary-Server",
        "os":           platform.system() + " " + platform.release(),
        "cpu_pct":      cpu_pct,
        "cpu_cores":    cpu_cores,
        "cpu_phys":     cpu_phys,
        "cpu_freq_mhz": round(cpu_freq.current, 0) if cpu_freq else 0,
        "mem_pct":      mem_pct,
        "mem_total_gb": mem_total_gb,
        "mem_used_gb":  mem_used_gb,
        "temp_c":       temp,
        "disk_pct":     disk_pct,
        "disk_total_gb":disk_total_gb,
        "disk_used_gb": disk_used_gb,
        "upload_mbps":  net["upload_mbps"],
        "download_mbps":net["download_mbps"],
        "pkts_sent":    net["pkts_sent"],
        "pkts_recv":    net["pkts_recv"],
        "nic_name":     net["nic_name"],
        "power_w":      power,
        "failure_risk": risk,
        "health":       health,
    }
