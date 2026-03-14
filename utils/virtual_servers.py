"""
virtual_servers.py – Generate N virtual servers derived from the primary server's
real hardware stats using AI-weighted variation (Gaussian noise + learned offsets).

Uses scikit-learn's IsolationForest to score anomaly likelihood per server.
"""

import numpy as np
from sklearn.ensemble import IsolationForest

# ── seeded RNG so per-slot personalities are stable across refreshes ──────────
_personalities = {}  # slot_id → {"cpu_bias", "mem_bias", "temp_bias", "net_bias"}


def _get_personality(slot_id: int) -> dict:
    """Each virtual server has a persistent 'personality' – fixed biases that
    mimic different workload profiles (idle node, compute-heavy, network-heavy)."""
    if slot_id not in _personalities:
        rng = np.random.default_rng(slot_id * 42 + 7)
        _personalities[slot_id] = {
            "cpu_bias":  float(rng.uniform(-8, 8)),
            "mem_bias":  float(rng.uniform(-5, 5)),
            "temp_bias": float(rng.uniform(-4, 4)),
            "net_bias":  float(rng.uniform(-2, 2)),
            "disk_bias": float(rng.uniform(-3, 3)),
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


# ── IsolationForest anomaly scoring ──────────────────────────────────────────
_if_model = IsolationForest(n_estimators=50, contamination=0.1, random_state=42)
_if_fitted = False


def _anomaly_score(feature_matrix: np.ndarray) -> np.ndarray:
    """Return per-row anomaly probability (0–100). Higher = more anomalous."""
    global _if_fitted
    if feature_matrix.shape[0] < 2:
        return np.zeros(feature_matrix.shape[0])
    if not _if_fitted or feature_matrix.shape[0] >= 5:
        _if_model.fit(feature_matrix)
        _if_fitted = True
    raw = _if_model.score_samples(feature_matrix)   # negative; lower = more anomalous
    # Normalize to 0–100 probability-like score
    normalized = (raw - raw.min()) / (raw.max() - raw.min() + 1e-9)
    return np.round((1 - normalized) * 100, 1)


# ── public API ────────────────────────────────────────────────────────────────

def generate_virtual_servers(host: dict, n: int = 9) -> list[dict]:
    """
    Generate `n` virtual server dicts from the host (primary server) metrics.

    Each virtual server has a persistent 'personality' bias plus per-tick
    Gaussian noise, making them feel like distinct machines with believable
    load patterns.
    """
    rng = np.random.default_rng()  # new seed per call for live variation

    servers = []
    feature_rows = []

    for i in range(n):
        p    = _get_personality(i)
        slot = i + 1  # 1-indexed slot label

        # ── base values = host + personality bias + live noise ─────────────
        cpu  = _clamp(host["cpu_pct"]      + p["cpu_bias"]  + rng.normal(0, 2.5), 0, 100)
        mem  = _clamp(host["mem_pct"]      + p["mem_bias"]  + rng.normal(0, 1.5), 0, 100)
        temp = _clamp(host["temp_c"]       + p["temp_bias"] + rng.normal(0, 1.0), 25, 105)
        ul   = _clamp(host["upload_mbps"]  + p["net_bias"]  + rng.normal(0, 0.5),  0, 10000)
        dl   = _clamp(host["download_mbps"]+ p["net_bias"]  + rng.normal(0, 0.5),  0, 10000)
        disk = _clamp(host["disk_pct"]     + p["disk_bias"] + rng.normal(0, 1.0),  0, 100)

        power = _compute_power(cpu, temp)
        risk  = _compute_failure_risk(cpu, mem, temp)
        health= _compute_health(cpu, mem, temp, disk, risk)

        # Simulate per-server packet traffic proportional to network speed
        pkts_sent = int(host["pkts_sent"] * (ul / max(host["upload_mbps"], 0.001)) * rng.uniform(0.85, 1.15))
        pkts_recv = int(host["pkts_recv"] * (dl / max(host["download_mbps"], 0.001)) * rng.uniform(0.85, 1.15))

        feature_rows.append([cpu, mem, temp, ul, dl, disk])

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
        })

    # Attach AI anomaly scores
    feat_matrix = np.array(feature_rows)
    anomaly_scores = _anomaly_score(feat_matrix)
    for i, s in enumerate(servers):
        s["anomaly_score"] = float(anomaly_scores[i])

    return servers
