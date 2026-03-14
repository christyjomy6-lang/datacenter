"""
cyber_api.py – GOD-EYE Data Center — FastAPI Backend
Serves live host metrics + AI-derived virtual servers as JSON.
Also serves the cyberpunk HTML dashboard at /.
"""

import sys, os
import csv
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import uvicorn

from utils.metrics import get_host_metrics
from utils.virtual_servers import generate_virtual_servers

app = FastAPI(title="GOD-EYE Data Center API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HTML_FILE = Path(__file__).parent / "cyber_dash.html"
DATASET_FILE = Path(__file__).parent / "telemetry_dataset.csv"

def append_to_csv(host: dict, servers: list[dict]):
    write_header = not DATASET_FILE.exists()
    try:
        with open(DATASET_FILE, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow([
                    "timestamp", "node_type", "node_id", "name", "role", 
                    "cpu_pct", "mem_pct", "temp_c", "upload_mbps", "download_mbps", 
                    "disk_pct", "power_w", "pkts_sent", "pkts_recv", 
                    "failure_risk", "health", "anomaly_score"
                ])
            
            ts = datetime.now().isoformat()
            
            # Host
            writer.writerow([
                ts, "host", "0", host.get("name", "Host"), "Primary",
                host.get("cpu_pct", 0), host.get("mem_pct", 0), host.get("temp_c", 0),
                host.get("upload_mbps", 0), host.get("download_mbps", 0), host.get("disk_pct", 0),
                host.get("power_w", 0), host.get("pkts_sent", 0), host.get("pkts_recv", 0),
                host.get("failure_risk", 0), host.get("health", 0), 0.0
            ])
            
            # Virtual Servers
            for s in servers:
                writer.writerow([
                    ts, "virtual", s.get("id"), s.get("name"), s.get("role"),
                    s.get("cpu_pct", 0), s.get("mem_pct", 0), s.get("temp_c", 0),
                    s.get("upload_mbps", 0), s.get("download_mbps", 0), s.get("disk_pct", 0),
                    s.get("power_w", 0), s.get("pkts_sent", 0), s.get("pkts_recv", 0),
                    s.get("failure_risk", 0), s.get("health", 0), s.get("anomaly_score", 0.0)
                ])
    except Exception as e:
        print(f"Error writing to CSV: {e}")


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_FILE.read_text(encoding="utf-8")


@app.get("/api/metrics")
def metrics(n: int = Query(default=9, ge=1, le=99)):
    host = get_host_metrics()
    servers = generate_virtual_servers(host, n=n)
    append_to_csv(host, servers)
    return JSONResponse({"host": host, "servers": servers})


@app.get("/api/export")
def export_data():
    if not DATASET_FILE.exists():
        return JSONResponse({"error": "Dataset not generated yet."}, status_code=404)
    return FileResponse(DATASET_FILE, media_type="text/csv", filename="telemetry_dataset.csv")


if __name__ == "__main__":
    # Use Render's PORT environment variable if available, fallback to 8000
    port = int(os.environ.get("PORT", 8000))
    # Must bind to 0.0.0.0 for Render to route external traffic
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
