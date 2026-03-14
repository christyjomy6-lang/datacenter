"""
cyber_api.py – GOD-EYE Data Center — FastAPI Backend
Serves live host metrics + AI-derived virtual servers as JSON.
Also serves the cyberpunk HTML dashboard at /.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
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


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_FILE.read_text(encoding="utf-8")


@app.get("/api/metrics")
def metrics(n: int = Query(default=9, ge=1, le=99)):
    host = get_host_metrics()
    servers = generate_virtual_servers(host, n=n)
    return JSONResponse({"host": host, "servers": servers})


if __name__ == "__main__":
    # Use Render's PORT environment variable if available, fallback to 8000
    port = int(os.environ.get("PORT", 8000))
    # Must bind to 0.0.0.0 for Render to route external traffic
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
