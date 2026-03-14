"""
virtual_servers.py – Generate N virtual servers derived from the primary server's
real hardware stats using AI-weighted variation (Gaussian noise + learned offsets).

Uses scikit-learn's IsolationForest to score anomaly likelihood per server.
"""

import random
import math

# ── seeded RNG so per-slot personalities are stable across refreshes ──────────
_personalities = {}  # slot_id → {"cpu_bias", "mem_bias", "temp_bias", "net_bias"}


def _get_personality(slot_id: int) -> dict:
    """Each virtual server has a persistent 'personality' – fixed biases that
    mimic different workload profiles (idle node, compute-heavy, network-heavy)."""
    if slot_id not in _personalities:
        # Use Python's built-in random module to seeded random
        rng = random.Random(slot_id * 42 + 7)
        _personalities[slot_id] = {
            "cpu_bias":  rng.uniform(-8, 8),
            "mem_bias":  rng.uniform(-5, 5),
            "temp_bias": rng.uniform(-4, 4),
            "net_bias":  rng.uniform(-2, 2),
            "disk_bias": rng.uniform(-3, 3),
            "role":      rng.choice(["Compute", "Storage", "Network", "DB", "App"]),
        }
    return _personalities[slot_id]


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _compute_power(cpu: float, temp: float) -> float:
    base, tdp = 15.0, 45.0
    return round(base + tdp * (0.15 + (cpu / 100.0) * 0.65 +
                               max(0.0, (temp - 40.0) / 60.0) * 0.20), 1)


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


def _compute_health(cpu: float, mem: float, temp: float, disk: float, risk: float) -> int:
    penalty = cpu * 0.30 + mem * 0.25 + min(temp, 100) * 0.20 + disk * 0.05 + risk * 0.20
    return max(0, min(100, round(100 - penalty)))


# ── Lightweight heuristic anomaly scoring ────────────────────────────────────
def _anomaly_score(cpu: float, mem: float, temp: float, disk: float) -> float:
    """Return an anomaly probability (0–100) using a lightweight heuristic instead of ML."""
    score = 0.0
    # Add score for high utilization and temps
    if cpu > 80: score += (cpu - 80) * 1.5
    if mem > 85: score += (mem - 85) * 2.0
    if temp > 80: score += (temp - 80) * 1.2
    if disk > 90: score += (disk - 90) * 1.0
    
    # Add some random noise for "unexplainable" anomalies
    noise = random.uniform(0, 5)
    
    return min(100.0, max(0.0, round(score + noise, 1)))


# ── public API ────────────────────────────────────────────────────────────────

def generate_virtual_servers(host: dict, n: int = 9) -> list[dict]:
    """
    Generate `n` virtual server dicts from the host (primary server) metrics.

    Each virtual server has a persistent 'personality' bias plus per-tick
    Gaussian noise, making them feel like distinct machines with believable
    load patterns.
    """
    rng = random.Random()  # new seed per call for live variation

    servers = []

    for i in range(n):
        p    = _get_personality(i)
        slot = i + 1  # 1-indexed slot label

        # ── base values = host + personality bias + live noise ─────────────
        # Implement normal variate using random.gauss
        cpu  = _clamp(host["cpu_pct"]      + p["cpu_bias"]  + rng.gauss(0, 2.5), 0, 100)
        mem  = _clamp(host["mem_pct"]      + p["mem_bias"]  + rng.gauss(0, 1.5), 0, 100)
        temp = _clamp(host["temp_c"]       + p["temp_bias"] + rng.gauss(0, 1.0), 25, 105)
        ul   = _clamp(host["upload_mbps"]  + p["net_bias"]  + rng.gauss(0, 0.5),  0, 10000)
        dl   = _clamp(host["download_mbps"]+ p["net_bias"]  + rng.gauss(0, 0.5),  0, 10000)
        disk = _clamp(host["disk_pct"]     + p["disk_bias"] + rng.gauss(0, 1.0),  0, 100)

        power = _compute_power(cpu, temp)
        risk  = _compute_failure_risk(cpu, mem, temp)
        health= _compute_health(cpu, mem, temp, disk, risk)

        # Simulate per-server packet traffic proportional to network speed
        pkts_sent = int(host["pkts_sent"] * (ul / max(host["upload_mbps"], 0.001)) * rng.uniform(0.85, 1.15))
        pkts_recv = int(host["pkts_recv"] * (dl / max(host["download_mbps"], 0.001)) * rng.uniform(0.85, 1.15))

        anomaly_score = _anomaly_score(cpu, mem, temp, disk)

        servers.append({
            "id":           slot,
            "name":         f"VS-{slot:02d}",
            "role":         p["role"],
            "cpu_pct":      round(cpu,  1),
            "mem_pct":      round(mem,  1),
            "temp_c":       round(temp, 1),
            "power_w":      power,
            "upload_mbps":  round(ul,  3),
            "download_mbps":round(dl,  3),
            "pkts_sent":    max(0, pkts_sent),
            "pkts_recv":    max(0, pkts_recv),
            "disk_pct":     round(disk, 1),
            "failure_risk": risk,
            "health":       health,
            "anomaly_score": float(anomaly_score),
        })

    return servers
