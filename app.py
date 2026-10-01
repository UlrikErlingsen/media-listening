"""ListenSignal Streamlit application (entry point). Pages live in pages/; analysis lives in src/listensignal/."""

from __future__ import annotations

import os

# Keep Arrow serialization stable on macOS. This must be set before Streamlit imports Arrow.
os.environ.setdefault("ARROW_DEFAULT_MEMORY_POOL", "system")

import base64
from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
for path in (SRC, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from listensignal import __version__
from pages._ui import PERIODS, db_count, show_error, workspace

mark_path = ROOT / "assets" / "listensignal-mark.svg"
MARK_URI = (
    "data:image/svg+xml;base64," + base64.b64encode(mark_path.read_bytes()).decode("ascii") if mark_path.exists() else ""
)

st.set_page_config(page_title="ListenSignal | Norwegian media listening", page_icon="◉", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --ps-ink:#17322e; --ps-deep:#102c2a; --ps-teal:#173c3a;
        --ps-coral:#d95b40; --ps-mint:#83d2b4; --ps-gold:#f2c66d;
        --ps-paper:#f8f5ed; --ps-line:rgba(23,50,46,.14);
    }
    [data-testid="stAppViewContainer"] {
        background:radial-gradient(circle at 94% 2%,rgba(131,210,180,.17),transparent 28rem),
                   radial-gradient(circle at 3% 93%,rgba(242,198,109,.14),transparent 25rem),
                   linear-gradient(180deg,#fbf9f3 0%,var(--ps-paper) 100%);
    }
    [data-testid="stHeader"] { background:rgba(248,245,237,.78); }
    [data-testid="stSidebar"] { background:linear-gradient(165deg,#173c3a 0%,#102c2a 65%,#0c2422 100%); }
    [data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] span { color:#f8f5ed; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { color:#b9cbc5; }
    [data-testid="stSidebar"] a span, [data-testid="stSidebarNav"] span { color:#f8f5ed !important; }
    [data-testid="stSidebar"] [data-baseweb="select"] span { color:#17322e; }
    [data-testid="stSidebar"] button {
        background:rgba(255,255,255,.08); color:#f8f5ed !important; border-color:rgba(255,255,255,.23);
    }
    [data-testid="stSidebar"] button * { color:#f8f5ed !important; }
    .block-container { max-width:1240px; padding-top:4.4rem; padding-bottom:4rem; }
    h1,h2,h3 { color:var(--ps-ink); letter-spacing:-.025em; }
    a { color:#9b3e2b; }
    [data-testid="stMetric"] {
        background:rgba(255,255,255,.75); border:1px solid var(--ps-line); border-radius:16px;
        padding:1rem 1.05rem; box-shadow:0 8px 28px rgba(23,50,46,.045);
    }
    [data-testid="stMetricValue"] { color:var(--ps-ink); font-size:clamp(1.35rem,2.3vw,1.9rem); }
    .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
        background:linear-gradient(135deg,#e26748,#c94c34); color:white; border:0;
        box-shadow:0 8px 20px rgba(217,91,64,.22); font-weight:750;
    }
    button:focus-visible,a:focus-visible,input:focus-visible,[role="radio"]:focus-visible {
        outline:3px solid #f2c66d !important; outline-offset:2px;
    }
    [data-testid="stExpander"],[data-testid="stAlert"],[data-testid="stVerticalBlockBorderWrapper"] { border-radius:14px; }
    [data-testid="stPlotlyChart"] { border:1px solid var(--ps-line); border-radius:14px; overflow:hidden; background:#fcfcfb; }
    .ps-lockup { display:flex; align-items:center; gap:.65rem; }
    .ps-mark { width:38px; height:38px; }
    .ps-name { color:white; font-size:1.28rem; line-height:1; font-weight:850; letter-spacing:-.04em; }
    .ps-name span { color:#f2c66d !important; }
    .ps-tag { margin:.55rem 0 0 !important; color:#b9cbc5 !important; font-size:.77rem; line-height:1.4; }
    .ps-masthead {
        display:flex; justify-content:space-between; align-items:center; gap:1rem; padding:.72rem 1rem .72rem .78rem;
        margin-bottom:1.35rem; background:rgba(255,255,255,.65); border:1px solid var(--ps-line);
        border-radius:18px; box-shadow:0 10px 36px rgba(23,50,46,.05);
    }
    .ps-masthead .ps-mark { width:48px; height:48px; }
    .ps-wordmark { color:var(--ps-ink); font-weight:850; letter-spacing:-.045em; font-size:1.55rem; line-height:1; }
    .ps-wordmark span { color:var(--ps-coral); }
    .ps-kicker { margin-top:.32rem; color:#59716c; font-size:.67rem; font-weight:800; letter-spacing:.13em; }
    .ps-promise { color:#47645e; font-size:.78rem; font-weight:700; white-space:nowrap; }
    .ps-promise span { color:var(--ps-coral); padding:0 .3rem; }
    .ps-hero {
        position:relative; overflow:hidden; padding:clamp(1.5rem,3.4vw,2.8rem); margin-bottom:1.1rem;
        background:linear-gradient(135deg,#173c3a 0%,#102c2a 75%); border-radius:26px;
        box-shadow:0 18px 50px rgba(23,50,46,.17);
    }
    .ps-hero:after {
        content:""; position:absolute; width:330px; height:330px; right:-105px; top:-148px;
        border-radius:50%; border:56px solid rgba(131,210,180,.12);
    }
    .ps-eyebrow { color:#83d2b4; font-size:.72rem; font-weight:850; letter-spacing:.16em; }
    .ps-hero h1 { color:white; font-size:clamp(2rem,4.2vw,3.8rem); line-height:.98; margin:.65rem 0 .9rem; max-width:960px; }
    .ps-hero h1 em { color:#f2c66d; font-style:normal; }
    .ps-hero p { color:#d7e3df; font-size:1.02rem; line-height:1.6; max-width:820px; }
    .ps-pills { display:flex; flex-wrap:wrap; gap:.55rem; margin-top:1rem; }
    .ps-pill {
        padding:.4rem .72rem; border:1px solid rgba(255,255,255,.16); border-radius:999px;
        color:#f8f5ed; font-size:.78rem; font-weight:700; background:rgba(255,255,255,.055);
    }
    .pulse-kicker {font-size:.72rem;font-weight:800;letter-spacing:.14em;color:var(--ps-coral);text-transform:uppercase;}
    .pulse-title {font-size:2.15rem;line-height:1.08;font-weight:850;color:var(--ps-ink);margin:.2rem 0 .6rem;}
    .pulse-subtitle {font-size:1.02rem;color:#526a65;max-width:850px;margin-bottom:1.2rem;line-height:1.55;}
    .boundary {border-left:4px solid var(--ps-mint);background:rgba(255,255,255,.62);border-radius:0 14px 14px 0;padding:1rem 1.1rem;color:#47645e;}
    .warning-box {border-left:4px solid var(--ps-gold);background:rgba(242,198,109,.17);border-radius:0 14px 14px 0;padding:.8rem 1.1rem;color:#604b1f;margin-bottom:.4rem;}
    .change-note {border-left:4px solid var(--ps-coral);background:rgba(255,255,255,.7);border-radius:0 12px 12px 0;padding:.6rem 1rem;margin:.35rem 0;color:#17322e;}
    .small-note {font-size:.86rem;color:#617670;}
    .ps-footer { margin-top:3.2rem; padding-top:1rem; border-top:1px solid var(--ps-line); color:#617670; font-size:.76rem; text-align:center; }
    .ps-footer span { color:var(--ps-coral); padding:0 .38rem; }
    @media (max-width:760px) { .ps-promise{display:none}.ps-hero{border-radius:20px}.block-container{padding-top:3.5rem} }
    @media (prefers-reduced-motion:reduce) { * { scroll-behavior:auto !important; transition:none !important; } }
    </style>
    """,
    unsafe_allow_html=True,
)


def masthead() -> None:
    mark = f'<img class="ps-mark" src="{MARK_URI}" alt="">' if MARK_URI else ""
    st.markdown(
        f"""
        <div class="ps-masthead">
          <div class="ps-lockup">{mark}<div><div class="ps-wordmark">Listen<span>Signal</span></div>
          <div class="ps-kicker">LISTEN → COMPARE → FLAG</div></div></div>
          <div class="ps-promise">Norwegian sources <span>◆</span> Local sentiment <span>◆</span> Visible rules</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def footer() -> None:
    st.markdown(
        f'<div class="ps-footer">ListenSignal v{__version__} <span>◆</span> counts what feeds published, not what '
        'people think <span>◆</span> Part of the Signal suite <span>◆</span> AGPL-3.0-or-later</div>',
        unsafe_allow_html=True,
    )


PAGES = [
    st.Page("pages/overview.py", title="Overview", icon=":material/insights:", default=True),
    st.Page("pages/what_changed.py", title="What changed", icon=":material/trending_up:"),
    st.Page("pages/mentions.py", title="Mentions", icon=":material/article:"),
    st.Page("pages/topics.py", title="Topics", icon=":material/category:"),
    st.Page("pages/pulse.py", title="Weekly pulse", icon=":material/download:"),
    st.Page("pages/sources.py", title="Sources & brands", icon=":material/rss_feed:"),
    st.Page("pages/methods.py", title="Methods & limits", icon=":material/menu_book:"),
]

with st.sidebar:
    mark = f'<img class="ps-mark" src="{MARK_URI}" alt="">' if MARK_URI else ""
    st.markdown(
        f'<div class="ps-lockup">{mark}<div class="ps-name">Listen<span>Signal</span></div></div>'
        '<p class="ps-tag">Norwegian media listening without the monitoring subscription.</p>',
        unsafe_allow_html=True,
    )
    st.caption(f"Media & social listening · v{__version__}")

page = st.navigation(PAGES)

with st.sidebar:
    stored = db_count()
    modes = {"demo": "Fictional demo", "db": f"My collected data ({stored:,} items)"}
    st.radio("Data", list(modes), format_func=modes.get, key="data_mode")
    st.selectbox("Period", list(PERIODS), index=1, key="period")
    ws = workspace()
    st.caption(f"{len(ws.brands)} brands · {len(ws.articles):,} feed items · {len(ws.mentions):,} brand mentions")
    st.caption("Local mode · no telemetry · no accounts · no external AI calls · network only for your RSS feeds")

masthead()
try:
    page.run()
except Exception as exc:  # friendly message; tracebacks only with LISTENSIGNAL_DEBUG=1
    show_error(exc)
footer()
