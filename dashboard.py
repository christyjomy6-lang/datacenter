"""
dashboard.py – Data Center Monitoring Dashboard
Primary Server: Your Laptop (real psutil stats)
Virtual Servers: 9 AI-derived simulated nodes powered by your laptop's data

Run: streamlit run dashboard.py
"""

import time
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from utils.metrics import get_host_metrics
from utils.virtual_servers import generate_virtual_servers
from utils.history import MetricsHistory

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Data Center Dashboard",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Base ── */
html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }
[data-testid="stAppViewContainer"] { background: #0d1117; color: #e6edf3; }
[data-testid="stHeader"]           { background: transparent; }
[data-testid="stSidebar"]          { background: #161b22; border-right: 1px solid #30363d; }

/* ── Section headers ── */
.section-title {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #58a6ff;
    padding: 6px 0 4px 0;
    border-bottom: 1px solid #21262d;
    margin-bottom: 10px;
}

/* ── KPI card ── */
.kpi-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 14px 16px 10px 16px;
    text-align: center;
    position: relative;
    transition: border-color 0.2s;
}
.kpi-card:hover { border-color: #388bfd; }
.kpi-label {
    font-size: 0.65rem;
    color: #8b949e;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 4px;
}
.kpi-value {
    font-size: 1.55rem;
    font-weight: 700;
    line-height: 1.1;
}
.kpi-sub {
    font-size: 0.62rem;
    color: #8b949e;
    margin-top: 2px;
}
.kpi-bar-wrap {
    background: #21262d;
    border-radius: 4px;
    height: 5px;
    margin-top: 8px;
    overflow: hidden;
}
.kpi-bar { height: 5px; border-radius: 4px; }

/* ── Server tile ── */
.srv-tile {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 10px 12px 8px 12px;
    font-size: 0.7rem;
    color: #c9d1d9;
    cursor: pointer;
    transition: border-color 0.2s, box-shadow 0.2s;
}
.srv-tile:hover { border-color: #388bfd; box-shadow: 0 0 10px #388bfd33; }
.srv-title {
    font-size: 0.75rem;
    font-weight: 700;
    color: #e6edf3;
    margin-bottom: 4px;
}
.srv-badge {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 10px;
    font-size: 0.6rem;
    font-weight: 600;
    margin-bottom: 6px;
}
.badge-ok     { background: #1a3a1a; color: #3fb950; border: 1px solid #3fb950; }
.badge-warn   { background: #3a2d0a; color: #d29922; border: 1px solid #d29922; }
.badge-crit   { background: #3a0d0d; color: #f85149; border: 1px solid #f85149; }
.badge-anom   { background: #2d1a3a; color: #bc8cff; border: 1px solid #bc8cff; }
.srv-row { display: flex; justify-content: space-between; margin: 1px 0; }
.srv-row .lbl { color: #8b949e; }

/* ── Alert row colors ── */
.alert-crit { color: #f85149; font-weight: 600; }
.alert-warn { color: #d29922; }
</style>
""", unsafe_allow_html=True)

# ── session state ─────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = MetricsHistory()
if "selected_server" not in st.session_state:
    st.session_state.selected_server = None

# ── sidebar config ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    n_virtual = st.slider("Virtual Servers", 1, 9, 9, key="n_virtual")
    refresh   = st.slider("Refresh Interval (s)", 2, 10, 3, key="refresh")
    heatmap_metric = st.selectbox("Heatmap Metric", ["CPU %", "Temperature °C", "Network Upload Mbps", "Failure Risk %"], key="hm_metric")
    st.markdown("---")
    st.markdown("### 🔔 Thresholds")
    cpu_thresh  = st.number_input("CPU Alert >", 70, 100, 90)
    temp_thresh = st.number_input("Temp Alert > (°C)", 50, 100, 70)
    risk_thresh = st.number_input("Failure Risk Alert >", 10, 100, 40)
    st.markdown("---")
    export_now = st.button("📥 Export CSV", use_container_width=True)

# ── fetch data ────────────────────────────────────────────────────────────────
host    = get_host_metrics()
st.session_state.history.push(host)
servers = generate_virtual_servers(host, n=n_virtual)
hist    = st.session_state.history.as_lists()

# ── header ────────────────────────────────────────────────────────────────────
hcol1, hcol2 = st.columns([5, 1])
with hcol1:
    st.markdown(
        f"<h1 style='margin:0;font-size:1.5rem;color:#e6edf3;letter-spacing:0.04em;'>"
        f"🖥️ DATA CENTER OPERATIONS CENTER</h1>"
        f"<p style='margin:2px 0 0 0;font-size:0.72rem;color:#8b949e;'>"
        f"Primary Server: <b style='color:#58a6ff'>{host['name']}</b> &nbsp;|&nbsp; "
        f"OS: {host['os']} &nbsp;|&nbsp; "
        f"Cores: {host['cpu_phys']}P / {host['cpu_cores']}L &nbsp;|&nbsp; "
        f"Last updated: {time.strftime('%H:%M:%S')}</p>",
        unsafe_allow_html=True,
    )
with hcol2:
    st.markdown(f"<div style='text-align:right;padding-top:8px;font-size:0.68rem;color:#8b949e;'>"
                f"Auto-refresh every <b style='color:#58a6ff'>{refresh}s</b></div>",
                unsafe_allow_html=True)

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# ①  PRIMARY SERVER STATS PANEL
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">▶ PRIMARY SERVER — Live Hardware Metrics</div>',
            unsafe_allow_html=True)


def _color(pct: float, lo=60, hi=80) -> str:
    if pct >= hi:   return "#f85149"
    if pct >= lo:   return "#d29922"
    return "#3fb950"


def kpi(label: str, value: str, sub: str, bar_pct: float | None = None, color: str = "#3fb950",
        unit_color: str | None = None) -> str:
    bar_html = ""
    if bar_pct is not None:
        bar_pct_clamped = max(0, min(100, bar_pct))
        bar_html = (
            f"<div class='kpi-bar-wrap'>"
            f"<div class='kpi-bar' style='width:{bar_pct_clamped}%;background:{color};'></div>"
            f"</div>"
        )
    c = unit_color or color
    return (
        f"<div class='kpi-card'>"
        f"<div class='kpi-label'>{label}</div>"
        f"<div class='kpi-value' style='color:{c};'>{value}</div>"
        f"<div class='kpi-sub'>{sub}</div>"
        f"{bar_html}"
        f"</div>"
    )


k1, k2, k3, k4, k5, k6, k7, k8 = st.columns(8)

with k1:
    c = _color(host["cpu_pct"])
    st.markdown(kpi("CPU Usage", f"{host['cpu_pct']:.1f}%",
                    f"{host['cpu_freq_mhz']:.0f} MHz", host["cpu_pct"], c), unsafe_allow_html=True)
with k2:
    c = _color(host["mem_pct"])
    st.markdown(kpi("Memory", f"{host['mem_pct']:.1f}%",
                    f"{host['mem_used_gb']}/{host['mem_total_gb']} GB", host["mem_pct"], c), unsafe_allow_html=True)
with k3:
    c = _color(host["temp_c"], 60, 80)
    st.markdown(kpi("Temperature", f"{host['temp_c']:.1f}°C",
                    "CPU Core Avg", host["temp_c"], c, c), unsafe_allow_html=True)
with k4:
    c = _color(host["power_w"], 30, 40)
    st.markdown(kpi("Power Draw", f"{host['power_w']}W",
                    "Est. Consumption", None, c, c), unsafe_allow_html=True)
with k5:
    st.markdown(kpi("Upload", f"{host['upload_mbps']:.2f}",
                    "Mbps ↑", None, "#388bfd", "#388bfd"), unsafe_allow_html=True)
with k6:
    st.markdown(kpi("Download", f"{host['download_mbps']:.2f}",
                    "Mbps ↓", None, "#58a6ff", "#58a6ff"), unsafe_allow_html=True)
with k7:
    c = _color(host["disk_pct"], 75, 90)
    st.markdown(kpi("Disk", f"{host['disk_pct']:.1f}%",
                    f"{host['disk_used_gb']}/{host['disk_total_gb']} GB", host["disk_pct"], c), unsafe_allow_html=True)
with k8:
    hc = "#3fb950" if host["health"] >= 70 else "#d29922" if host["health"] >= 40 else "#f85149"
    st.markdown(kpi("Health Score", str(host["health"]),
                    f"Risk: {host['failure_risk']}%", host["health"], hc, hc), unsafe_allow_html=True)

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# Network packets sub-row
pkt_col1, pkt_col2, pkt_col3 = st.columns([2, 2, 4])
with pkt_col1:
    st.markdown(
        f"<div style='background:#161b22;border:1px solid #30363d;border-radius:8px;padding:8px 14px;"
        f"font-size:0.7rem;color:#8b949e;'>"
        f"📤 Packets Sent: <b style='color:#e6edf3;'>{host['pkts_sent']:,}</b> &nbsp;|&nbsp; "
        f"📥 Packets Recv: <b style='color:#e6edf3;'>{host['pkts_recv']:,}</b></div>",
        unsafe_allow_html=True)
with pkt_col2:
    ri = host["failure_risk"]
    rs = "CRITICAL" if ri >= 60 else "WARNING" if ri >= 30 else "NORMAL"
    rc = "#f85149" if ri >= 60 else "#d29922" if ri >= 30 else "#3fb950"
    st.markdown(
        f"<div style='background:#161b22;border:1px solid {rc};border-radius:8px;padding:8px 14px;"
        f"font-size:0.7rem;color:#8b949e;'>"
        f"🚨 Failure Risk: <b style='color:{rc};'>{ri}% — {rs}</b></div>",
        unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# ②  VIRTUAL SERVER RACK GRID
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
st.markdown('<div class="section-title">▶ VIRTUAL SERVER RACK — AI-Derived from Primary Server</div>',
            unsafe_allow_html=True)


def _srv_badge(risk: float, anomaly: float) -> str:
    if anomaly > 70:
        return "<span class='srv-badge badge-anom'>⚠ ANOMALY</span>"
    if risk >= 60:
        return "<span class='srv-badge badge-crit'>● CRITICAL</span>"
    if risk >= 30:
        return "<span class='srv-badge badge-warn'>● WARNING</span>"
    return "<span class='srv-badge badge-ok'>● ONLINE</span>"


def _srv_tile(s: dict) -> str:
    cpu  = s["cpu_pct"]
    mem  = s["mem_pct"]
    temp = s["temp_c"]
    risk = s["failure_risk"]
    anom = s["anomaly_score"]
    hc   = "#3fb950" if s["health"] >= 70 else "#d29922" if s["health"] >= 40 else "#f85149"
    badge = _srv_badge(risk, anom)
    return f"""
<div class='srv-tile'>
  <div class='srv-title'>{s['name']} <span style='font-size:0.6rem;color:#8b949e;'>[{s['role']}]</span></div>
  {badge}
  <div class='srv-row'><span class='lbl'>CPU</span>     <b>{cpu:.1f}%</b></div>
  <div class='srv-row'><span class='lbl'>Memory</span>  <b>{mem:.1f}%</b></div>
  <div class='srv-row'><span class='lbl'>Temp</span>    <b>{temp:.1f}°C</b></div>
  <div class='srv-row'><span class='lbl'>Power</span>   <b>{s['power_w']}W</b></div>
  <div class='srv-row'><span class='lbl'>UL/DL</span>  <b>{s['upload_mbps']:.2f}/{s['download_mbps']:.2f} Mbps</b></div>
  <div class='srv-row'><span class='lbl'>Disk</span>   <b>{s['disk_pct']:.1f}%</b></div>
  <div class='srv-row'><span class='lbl'>Risk</span>   <b style='color:{_color(risk,30,60)};'>{risk:.0f}%</b></div>
  <div class='srv-row'><span class='lbl'>Health</span> <b style='color:{hc};'>{s['health']}</b></div>
  <div class='srv-row'><span class='lbl'>Anomaly</span><b style='color:#bc8cff;'>{anom:.0f}%</b></div>
</div>"""


COLS = 3
rows = [servers[i:i+COLS] for i in range(0, len(servers), COLS)]
for row in rows:
    cols = st.columns(COLS)
    for col, srv in zip(cols, row):
        with col:
            st.markdown(_srv_tile(srv), unsafe_allow_html=True)
            if st.button(f"🔍 {srv['name']}", key=f"btn_{srv['id']}", use_container_width=True):
                if st.session_state.selected_server == srv["id"]:
                    st.session_state.selected_server = None
                else:
                    st.session_state.selected_server = srv["id"]
    # empty spacer columns if row is short
    for _ in range(COLS - len(row)):
        cols[_].empty()

# ── expanded server detail ────────────────────────────────────────────────────
if st.session_state.selected_server is not None:
    sel = next((s for s in servers if s["id"] == st.session_state.selected_server), None)
    if sel:
        with st.expander(f"🖥️ Detailed View — {sel['name']} [{sel['role']}]", expanded=True):
            d1, d2, d3, d4, d5, d6 = st.columns(6)
            metrics_detail = [
                ("CPU",       f"{sel['cpu_pct']:.1f}%",        "Utilization"),
                ("Memory",    f"{sel['mem_pct']:.1f}%",        f"{sel['mem_pct']/100*host['mem_total_gb']:.1f} GB est."),
                ("Temp",      f"{sel['temp_c']:.1f}°C",        "Core Avg"),
                ("Power",     f"{sel['power_w']}W",            "Est. Draw"),
                ("Upload",    f"{sel['upload_mbps']:.3f} Mbps","↑ Throughput"),
                ("Download",  f"{sel['download_mbps']:.3f} Mbps","↓ Throughput"),
            ]
            for col_obj, (lbl, val, sub) in zip([d1,d2,d3,d4,d5,d6], metrics_detail):
                with col_obj:
                    st.metric(lbl, val, sub)
            d7, d8, d9, d10 = st.columns(4)
            with d7: st.metric("Disk", f"{sel['disk_pct']:.1f}%")
            with d8: st.metric("Pkts Sent", f"{sel['pkts_sent']:,}")
            with d9: st.metric("Pkts Recv", f"{sel['pkts_recv']:,}")
            with d10:
                st.metric("Failure Risk", f"{sel['failure_risk']:.1f}%")
                st.metric("Anomaly Score", f"{sel['anomaly_score']:.1f}%")
            st.metric("Health Score", f"{sel['health']}/100")

# ─────────────────────────────────────────────────────────────────────────────
# ③  TABS: HEATMAP / TIME-SERIES / ALERTS / EXPORT
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
tab_hm, tab_ts, tab_al = st.tabs(["🌡 Rack Heatmap", "📈 Time-Series Charts", "🚨 Alerts & Health"])

# ── Heatmap ───────────────────────────────────────────────────────────────────
with tab_hm:
    col_map = {"CPU %": "cpu_pct", "Temperature °C": "temp_c",
               "Network Upload Mbps": "upload_mbps", "Failure Risk %": "failure_risk"}
    metric_key = col_map[heatmap_metric]

    # Build grid: 3 cols × ceil(n/3) rows
    ncols = COLS
    nrows = int(np.ceil(n_virtual / ncols))
    grid  = np.full((nrows, ncols), np.nan)
    labels= [["" for _ in range(ncols)] for _ in range(nrows)]

    for i, s in enumerate(servers):
        r, c = divmod(i, ncols)
        grid[r][c]   = s[metric_key]
        labels[r][c] = f"{s['name']}<br>{s[metric_key]:.1f}"

    color_scales = {
        "CPU %": "RdYlGn_r", "Temperature °C": "Inferno",
        "Network Upload Mbps": "Blues", "Failure Risk %": "OrRd",
    }
    fig_hm = go.Figure(go.Heatmap(
        z=grid, text=labels, texttemplate="%{text}",
        colorscale=color_scales[heatmap_metric],
        showscale=True,
        xgap=4, ygap=4,
        hovertemplate="Slot: %{text}<br>Value: %{z:.2f}<extra></extra>",
    ))
    fig_hm.update_layout(
        title=dict(text=f"Rack Heatmap — {heatmap_metric}", font=dict(size=13, color="#8b949e")),
        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
        font=dict(color="#c9d1d9"),
        margin=dict(l=10, r=10, t=40, b=10),
        height=280,
        xaxis=dict(showticklabels=False, showgrid=False),
        yaxis=dict(showticklabels=False, showgrid=False),
    )
    st.plotly_chart(fig_hm, use_container_width=True)

# ── Time-Series Charts ────────────────────────────────────────────────────────
with tab_ts:
    if len(hist["timestamps"]) < 2:
        st.info("Collecting data… charts appear after a few seconds.")
    else:
        ts = hist["timestamps"]
        fig_ts = make_subplots(
            rows=2, cols=2,
            subplot_titles=("CPU Usage (%)", "Memory Usage (%)",
                            "Temperature (°C)", "Network (Mbps)"),
            vertical_spacing=0.18,
        )
        line_style = dict(width=2)
        fig_ts.add_trace(go.Scatter(x=ts, y=hist["cpu"],  mode="lines",
                                    line=dict(**line_style, color="#388bfd"), name="CPU"), row=1, col=1)
        fig_ts.add_trace(go.Scatter(x=ts, y=hist["mem"],  mode="lines",
                                    line=dict(**line_style, color="#3fb950"), name="Memory"), row=1, col=2)
        fig_ts.add_trace(go.Scatter(x=ts, y=hist["temp"], mode="lines",
                                    line=dict(**line_style, color="#d29922"), name="Temp"), row=2, col=1)
        fig_ts.add_trace(go.Scatter(x=ts, y=hist["upload_mbps"],   mode="lines",
                                    line=dict(**line_style, color="#f85149"), name="Upload"), row=2, col=2)
        fig_ts.add_trace(go.Scatter(x=ts, y=hist["download_mbps"], mode="lines",
                                    line=dict(**line_style, color="#bc8cff"), name="Download"), row=2, col=2)
        fig_ts.update_layout(
            paper_bgcolor="#0d1117", plot_bgcolor="#161b22",
            font=dict(color="#c9d1d9", size=11),
            legend=dict(bgcolor="#161b22", bordercolor="#30363d", borderwidth=1),
            margin=dict(l=10, r=10, t=50, b=10),
            height=400, showlegend=True,
        )
        for ann in fig_ts["layout"]["annotations"]:
            ann["font"] = dict(size=11, color="#8b949e")
        fig_ts.update_xaxes(gridcolor="#21262d", showgrid=True, zeroline=False)
        fig_ts.update_yaxes(gridcolor="#21262d", showgrid=True, zeroline=False)
        st.plotly_chart(fig_ts, use_container_width=True)

# ── Alerts & Health Table ─────────────────────────────────────────────────────
with tab_al:
    all_nodes = [
        {**host, "name": f"⭐ {host['name']}", "role": "Primary", "anomaly_score": 0.0}
    ] + servers

    df = pd.DataFrame(all_nodes)[[
        "name", "role", "cpu_pct", "mem_pct", "temp_c",
        "power_w", "upload_mbps", "download_mbps", "disk_pct",
        "failure_risk", "anomaly_score", "health"
    ]]
    df.columns = ["Server", "Role", "CPU %", "Mem %", "Temp °C",
                  "Power W", "Upload Mbps", "Download Mbps", "Disk %",
                  "Risk %", "Anomaly %", "Health"]

    alerts_df = df[(df["CPU %"] > cpu_thresh) |
                   (df["Temp °C"] > temp_thresh) |
                   (df["Risk %"] > risk_thresh)]

    al1, al2 = st.columns([1, 3])
    with al1:
        st.markdown(f"""
<div style='background:#3a0d0d;border:1px solid #f85149;border-radius:10px;padding:16px;text-align:center;'>
  <div style='font-size:2rem;font-weight:700;color:#f85149;'>{len(alerts_df)}</div>
  <div style='font-size:0.7rem;color:#8b949e;letter-spacing:0.1em;'>ACTIVE ALERTS</div>
</div>
<div style='height:8px'></div>
<div style='background:#161b22;border:1px solid #30363d;border-radius:10px;padding:16px;text-align:center;'>
  <div style='font-size:2rem;font-weight:700;color:#3fb950;'>{len(df)-len(alerts_df)}</div>
  <div style='font-size:0.7rem;color:#8b949e;letter-spacing:0.1em;'>NODES HEALTHY</div>
</div>""", unsafe_allow_html=True)
    with al2:
        if len(alerts_df):
            st.dataframe(
                alerts_df.style
                .apply(lambda col: [
                    "background-color:#3a0d0d;color:#f85149" if v > cpu_thresh  else "" for v in col
                ] if col.name == "CPU %" else (
                    ["background-color:#3a0d0d;color:#f85149" if v > temp_thresh else "" for v in col]
                    if col.name == "Temp °C" else
                    ["background-color:#3a0d0d;color:#f85149" if v > risk_thresh else "" for v in col]
                    if col.name == "Risk %" else [""] * len(col)
                ), axis=0)
                .format({"CPU %": "{:.1f}", "Mem %": "{:.1f}", "Temp °C": "{:.1f}",
                         "Upload Mbps": "{:.3f}", "Download Mbps": "{:.3f}",
                         "Risk %": "{:.1f}", "Anomaly %": "{:.1f}"}),
                use_container_width=True, height=220,
            )
        else:
            st.success("✅ All servers operating within normal thresholds.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**All Servers — Full Metrics Table**")
    st.dataframe(df.style.format({
        "CPU %": "{:.1f}", "Mem %": "{:.1f}", "Temp °C": "{:.1f}",
        "Upload Mbps": "{:.3f}", "Download Mbps": "{:.3f}",
        "Risk %": "{:.1f}", "Anomaly %": "{:.1f}", "Health": "{:.0f}",
    }), use_container_width=True)

    # CSV export
    if export_now:
        csv = df.to_csv(index=False)
        st.download_button(
            "📥 Download CSV",
            data=csv,
            file_name=f"datacenter_snapshot_{time.strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )

# ─────────────────────────────────────────────────────────────────────────────
# Auto-refresh
# ─────────────────────────────────────────────────────────────────────────────
time.sleep(refresh)
st.rerun()
