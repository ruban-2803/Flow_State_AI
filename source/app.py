"""
app.py - Streamlit frontend for Cuber's AI Coach by SanRu Labs
"""

import os
import time
import tempfile
import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# ── Config ────────────────────────────────────────────────────────────────────
API_URL = os.environ.get("API_URL", "http://localhost:8000")
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "200"))

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cuber's AI Coach | SanRu Labs",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
        /* ── Global ── */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        /* ── Hide Streamlit chrome ── */
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        header { visibility: hidden; }

        /* ── App background ── */
        .stApp {
            background: linear-gradient(135deg, #0d0d1a 0%, #111827 60%, #0d0d1a 100%);
            color: #e5e7eb;
        }

        /* ── Metric cards ── */
        .metric-card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            padding: 24px 20px;
            text-align: center;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 32px rgba(99,102,241,0.15);
        }
        .metric-value {
            font-size: 2.4rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            line-height: 1;
            margin-bottom: 6px;
        }
        .metric-label {
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: #9ca3af;
        }
        .metric-sub {
            font-size: 0.75rem;
            color: #6b7280;
            margin-top: 4px;
        }

        /* ── Flow score gradient ── */
        .flow-excellent { color: #34d399; }
        .flow-good      { color: #fbbf24; }
        .flow-poor      { color: #f87171; }

        /* ── Pause badge ── */
        .pause-badge {
            display: inline-block;
            background: rgba(248,113,113,0.12);
            border: 1px solid rgba(248,113,113,0.3);
            color: #fca5a5;
            border-radius: 20px;
            padding: 3px 12px;
            font-size: 0.8rem;
            margin: 4px 4px 4px 0;
        }

        /* ── Advice card ── */
        .advice-card {
            background: rgba(99,102,241,0.06);
            border-left: 3px solid #6366f1;
            border-radius: 0 12px 12px 0;
            padding: 14px 18px;
            margin: 8px 0;
            font-size: 0.92rem;
            line-height: 1.6;
            color: #d1d5db;
        }

        /* ── Section header ── */
        .section-header {
            font-size: 1.05rem;
            font-weight: 700;
            color: #a5b4fc;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin: 28px 0 14px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(99,102,241,0.2);
        }

        /* ── Upload zone ── */
        .upload-hint {
            text-align: center;
            color: #6b7280;
            font-size: 0.85rem;
            margin-top: 6px;
        }

        /* ── Hero ── */
        .hero-logo {
            font-size: 2.8rem;
            font-weight: 800;
            letter-spacing: -0.04em;
            background: linear-gradient(90deg, #818cf8, #c084fc, #38bdf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .hero-tagline {
            font-size: 1rem;
            color: #6b7280;
            margin-top: 2px;
            letter-spacing: 0.02em;
        }
        .sanru-badge {
            display: inline-block;
            background: rgba(99,102,241,0.12);
            border: 1px solid rgba(99,102,241,0.25);
            color: #a5b4fc;
            border-radius: 20px;
            padding: 2px 12px;
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            margin-bottom: 10px;
        }

        /* ── Progress spinner override ── */
        .stSpinner > div {
            border-top-color: #818cf8 !important;
        }

        /* ── Plotly chart ── */
        .js-plotly-plot .plotly .modebar {
            background: transparent !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Helper functions ──────────────────────────────────────────────────────────

def flow_score_class(score: float) -> str:
    if score >= 85:
        return "flow-excellent"
    elif score >= 70:
        return "flow-good"
    return "flow-poor"


def format_time(seconds: float) -> str:
    """Format seconds as mm:ss.xx"""
    mins = int(seconds // 60)
    secs = seconds % 60
    if mins:
        return f"{mins}:{secs:05.2f}"
    return f"{secs:.2f}s"


def build_intensity_chart(
    timestamps: list,
    intensities: list,
    pauses: list,
    threshold: float = 2.0,
) -> go.Figure:
    """Build an interactive Plotly chart of turning intensity over time."""

    # Shade pause regions
    shapes = []
    for p in pauses:
        shapes.append(
            dict(
                type="rect",
                xref="x",
                yref="paper",
                x0=p["start_time"],
                x1=p["end_time"],
                y0=0,
                y1=1,
                fillcolor="rgba(248,113,113,0.12)",
                line=dict(width=0),
                layer="below",
            )
        )

    fig = go.Figure()

    # Fill area under curve
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=intensities,
            mode="lines",
            name="Intensity",
            line=dict(color="#818cf8", width=2),
            fill="tozeroy",
            fillcolor="rgba(129,140,248,0.1)",
            hovertemplate="<b>%{x:.2f}s</b><br>Intensity: %{y:.2f}<extra></extra>",
        )
    )

    # Threshold line
    fig.add_hline(
        y=threshold,
        line=dict(color="rgba(248,113,113,0.6)", width=1.5, dash="dash"),
        annotation_text="Pause threshold",
        annotation_font=dict(color="rgba(248,113,113,0.8)", size=11),
        annotation_position="bottom right",
    )

    fig.update_layout(
        shapes=shapes,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.02)",
        margin=dict(l=10, r=10, t=10, b=10),
        height=340,
        xaxis=dict(
            title="Time (seconds)",
            title_font=dict(color="#9ca3af", size=12),
            tickfont=dict(color="#6b7280", size=11),
            gridcolor="rgba(255,255,255,0.04)",
            zeroline=False,
        ),
        yaxis=dict(
            title="Motion Intensity",
            title_font=dict(color="#9ca3af", size=12),
            tickfont=dict(color="#6b7280", size=11),
            gridcolor="rgba(255,255,255,0.04)",
            zeroline=False,
        ),
        legend=dict(font=dict(color="#9ca3af")),
        hoverlabel=dict(
            bgcolor="#1f2937",
            bordercolor="#374151",
            font_color="#e5e7eb",
        ),
    )

    return fig


def call_analyze_api(video_bytes: bytes, filename: str) -> dict:
    """POST video to the FastAPI backend and return JSON result."""
    response = requests.post(
        f"{API_URL}/analyze",
        files={"file": (filename, video_bytes, "video/mp4")},
        timeout=300,  # 5 min timeout for long videos
    )
    response.raise_for_status()
    return response.json()


# ── Layout ────────────────────────────────────────────────────────────────────

# Hero header
col_logo, col_spacer = st.columns([3, 1])
with col_logo:
    st.markdown('<div class="sanru-badge">⚡ SanRu Labs</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-logo">🧊 Cuber\'s AI Coach</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="hero-tagline">Upload your solve video — AI detects every Recognition Pause and tells you exactly how to fix it.</div>',
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ── Upload section ─────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📂 Upload Your Solve</div>', unsafe_allow_html=True)

upload_col, preview_col = st.columns([1, 1], gap="large")

with upload_col:
    uploaded_file = st.file_uploader(
        "Drop your video here",
        type=["mp4", "mov", "avi", "webm", "mkv", "mpeg"],
        label_visibility="collapsed",
        help=f"Maximum file size: {MAX_UPLOAD_MB} MB. Supported: MP4, MOV, AVI, WebM, MKV.",
    )
    st.markdown(
        f'<div class="upload-hint">MP4, MOV, AVI, WebM, MKV · Max {MAX_UPLOAD_MB} MB</div>',
        unsafe_allow_html=True,
    )

with preview_col:
    if uploaded_file is not None:
        st.video(uploaded_file)
    else:
        st.markdown(
            """
            <div style="height:200px;border:2px dashed rgba(99,102,241,0.2);border-radius:12px;
                        display:flex;align-items:center;justify-content:center;
                        color:#4b5563;font-size:0.9rem;">
                🎬 Video preview will appear here
            </div>
            """,
            unsafe_allow_html=True,
        )

# ── Analysis button ────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)

analyze_btn = st.button(
    "🔍 Analyze My Solve",
    disabled=(uploaded_file is None),
    use_container_width=True,
    type="primary",
)

# ── Run analysis ───────────────────────────────────────────────────────────────
if analyze_btn and uploaded_file is not None:
    video_bytes = uploaded_file.getvalue()
    file_mb = len(video_bytes) / 1024 / 1024

    if file_mb > MAX_UPLOAD_MB:
        st.error(f"❌ File is {file_mb:.1f} MB, which exceeds the {MAX_UPLOAD_MB} MB limit. Please compress or trim the video.")
    else:
        with st.spinner("🧠 Analyzing optical flow — this may take 15–60s depending on video length..."):
            t_start = time.time()
            try:
                result = call_analyze_api(video_bytes, uploaded_file.name)
                elapsed = time.time() - t_start
            except requests.exceptions.ConnectionError:
                st.error(
                    "❌ Could not connect to the analysis API. "
                    "Make sure the backend (`main.py`) is running and `API_URL` is set correctly."
                )
                st.stop()
            except requests.exceptions.HTTPError as e:
                try:
                    detail = e.response.json().get("detail", str(e))
                except Exception:
                    detail = str(e)
                st.error(f"❌ Analysis failed: {detail}")
                st.stop()
            except Exception as e:
                st.error(f"❌ Unexpected error: {e}")
                st.stop()

        st.success(f"✅ Analysis complete in {elapsed:.1f}s!")
        st.session_state["result"] = result

# ── Results dashboard ──────────────────────────────────────────────────────────
if "result" in st.session_state:
    result = st.session_state["result"]
    pauses = result.get("pauses", [])
    num_pauses = len(pauses)
    total_time = result["total_time"]
    total_pause_time = result["total_pause_time"]
    flow_score = result["flow_score"]

    st.markdown('<div class="section-header">📊 Results Dashboard</div>', unsafe_allow_html=True)

    # ── Metric cards row ────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4, gap="small")

    with c1:
        st.markdown(
            f"""<div class="metric-card">
                <div class="metric-value" style="color:#38bdf8">{format_time(total_time)}</div>
                <div class="metric-label">Total Solve Time</div>
                <div class="metric-sub">{result['frame_count']:,} frames @ {result['fps']:.1f} fps</div>
            </div>""",
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""<div class="metric-card">
                <div class="metric-value" style="color:#f87171">{num_pauses}</div>
                <div class="metric-label">Recognition Pauses</div>
                <div class="metric-sub">{total_pause_time:.2f}s total paused</div>
            </div>""",
            unsafe_allow_html=True,
        )

    with c3:
        score_class = flow_score_class(flow_score)
        st.markdown(
            f"""<div class="metric-card">
                <div class="metric-value {score_class}">{flow_score:.1f}%</div>
                <div class="metric-label">Flow Score</div>
                <div class="metric-sub">% of time in motion</div>
            </div>""",
            unsafe_allow_html=True,
        )

    with c4:
        avg_pause = (total_pause_time / num_pauses) if num_pauses else 0
        st.markdown(
            f"""<div class="metric-card">
                <div class="metric-value" style="color:#c084fc">{avg_pause:.2f}s</div>
                <div class="metric-label">Avg Pause Length</div>
                <div class="metric-sub">{"Great!" if avg_pause < 0.8 else "Room to improve"}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Intensity chart ─────────────────────────────────────────────────────
    st.markdown('<div class="section-header">📈 Turning Intensity Over Time</div>', unsafe_allow_html=True)
    st.markdown(
        '<p style="color:#6b7280;font-size:0.85rem;margin-top:-8px;margin-bottom:12px;">'
        "Red shaded areas are Recognition Pauses. The dashed line is the pause threshold.</p>",
        unsafe_allow_html=True,
    )

    fig = build_intensity_chart(
        result["timestamps"],
        result["intensities"],
        pauses,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── Pause timeline ──────────────────────────────────────────────────────
    if pauses:
        st.markdown('<div class="section-header">⏸️ Pause Breakdown</div>', unsafe_allow_html=True)

        df = pd.DataFrame(pauses)
        df["start_time"] = df["start_time"].map(lambda x: f"{x:.2f}s")
        df["end_time"] = df["end_time"].map(lambda x: f"{x:.2f}s")
        df["duration"] = df["duration"].map(lambda x: f"{x:.2f}s")
        df.index = df.index + 1
        df.columns = ["Start", "End", "Duration"]
        df.index.name = "#"

        pause_col, _ = st.columns([1, 1])
        with pause_col:
            st.dataframe(
                df,
                use_container_width=True,
                height=min(300, 38 + len(df) * 35),
            )

    # ── Coach's Advice ──────────────────────────────────────────────────────
    st.markdown('<div class="section-header">🎓 Coach\'s Advice</div>', unsafe_allow_html=True)

    for tip in result.get("advice", []):
        st.markdown(f'<div class="advice-card">{tip}</div>', unsafe_allow_html=True)

    # ── Export ───────────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">💾 Export</div>', unsafe_allow_html=True)
    export_col1, export_col2, _ = st.columns([1, 1, 2])

    with export_col1:
        import json
        st.download_button(
            label="⬇️ Download JSON Report",
            data=json.dumps(result, indent=2),
            file_name="cubers_ai_coach_report.json",
            mime="application/json",
            use_container_width=True,
        )

    with export_col2:
        csv_data = pd.DataFrame(
            {"timestamp_s": result["timestamps"], "intensity": result["intensities"]}
        ).to_csv(index=False)
        st.download_button(
            label="⬇️ Download CSV (intensity data)",
            data=csv_data,
            file_name="intensity_data.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.markdown("<br><br>", unsafe_allow_html=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="text-align:center;color:#374151;font-size:0.75rem;padding:20px 0;
                border-top:1px solid rgba(255,255,255,0.05);margin-top:20px;">
        Built with ❤️ by <span style="color:#818cf8;font-weight:600;">SanRu Labs</span> &nbsp;·&nbsp;
        Powered by OpenCV Optical Flow &nbsp;·&nbsp;
        <span style="color:#6b7280;">Cuber's AI Coach v1.0</span>
    </div>
    """,
    unsafe_allow_html=True,
)
