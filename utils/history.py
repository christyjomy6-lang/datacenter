"""
history.py – Circular in-memory time-series store for dashboard charts.
Keeps the last MAX_POINTS snapshots of host and aggregate virtual server metrics.
"""

from collections import deque
import time

MAX_POINTS = 60  # ~3 min at 3-second refresh


class MetricsHistory:
    def __init__(self, maxlen: int = MAX_POINTS):
        self._maxlen = maxlen
        self.timestamps:    deque = deque(maxlen=maxlen)
        self.cpu:           deque = deque(maxlen=maxlen)
        self.mem:           deque = deque(maxlen=maxlen)
        self.temp:          deque = deque(maxlen=maxlen)
        self.upload_mbps:   deque = deque(maxlen=maxlen)
        self.download_mbps: deque = deque(maxlen=maxlen)
        self.power:         deque = deque(maxlen=maxlen)
        self.health:        deque = deque(maxlen=maxlen)

    def push(self, host: dict) -> None:
        self.timestamps.append(time.strftime("%H:%M:%S"))
        self.cpu.append(host["cpu_pct"])
        self.mem.append(host["mem_pct"])
        self.temp.append(host["temp_c"])
        self.upload_mbps.append(host["upload_mbps"])
        self.download_mbps.append(host["download_mbps"])
        self.power.append(host["power_w"])
        self.health.append(host["health"])

    def as_lists(self) -> dict:
        return {
            "timestamps":    list(self.timestamps),
            "cpu":           list(self.cpu),
            "mem":           list(self.mem),
            "temp":          list(self.temp),
            "upload_mbps":   list(self.upload_mbps),
            "download_mbps": list(self.download_mbps),
            "power":         list(self.power),
            "health":        list(self.health),
        }
