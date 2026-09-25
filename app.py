import base64
import hmac
import html as html_lib
import io
import json
import os
import zipfile
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo
from email.message import EmailMessage
from email.utils import formatdate
from urllib.parse import parse_qs, quote, quote_plus, unquote, urljoin, urlparse

from bs4 import BeautifulSoup
from fpdf import FPDF
import pandas as pd
from pydantic import BaseModel, Field
import requests
import streamlit as st

# ==========================================
# DESIGN SYSTEM (theme, CSS & HTML components)
# ==========================================

APP_NAME = "Prospect Engine"
APP_TAGLINE = "UK sales intelligence"

APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
  --bg: #0A0E1A;
  --surface: #111827;
  --surface-2: #161F33;
  --surface-3: #1C2740;
  --border: rgba(148, 163, 184, 0.14);
  --border-strong: rgba(148, 163, 184, 0.26);
  --text: #E7EAF3;
  --muted: #8C98B0;
  --faint: #5E6A82;
  --accent: #7C83FF;
  --accent-2: #38D6F5;
  --accent-soft: rgba(124, 131, 255, 0.14);
  --good: #34D399;
  --warn: #FBBF24;
  --risk: #FB923C;
  --bad: #F87171;
  --radius: 14px;
  --grad: linear-gradient(135deg, #7C83FF 0%, #38D6F5 100%);
}

html, body, [class*="css"], .stApp, button, input, textarea, select {
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important;
}
.stApp {
  background:
    radial-gradient(1200px 500px at 85% -10%, rgba(56, 214, 245, 0.07), transparent 60%),
    radial-gradient(900px 500px at 10% -20%, rgba(124, 131, 255, 0.10), transparent 60%),
    var(--bg);
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stDecoration"] { display: none; }
footer { visibility: hidden; }
.block-container { padding-top: 1.6rem !important; padding-bottom: 3rem !important; max-width: 1500px; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0D1322 0%, #0A0E1A 100%);
  border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] .block-container, [data-testid="stSidebarContent"] { padding-top: 0.6rem; }
[data-testid="stSidebarUserContent"] { padding-top: 1rem; }

/* ---------- Typography ---------- */
h1, h2, h3, h4 { color: var(--text); letter-spacing: -0.02em; }
p, li, label, .stMarkdown { color: var(--text); }
[data-testid="stCaptionContainer"], .stCaption { color: var(--muted) !important; }
[data-testid="stWidgetLabel"] p {
  font-size: 0.76rem !important; font-weight: 600 !important; color: var(--muted) !important;
  text-transform: uppercase; letter-spacing: 0.06em;
}

/* ---------- Cards (bordered containers) ---------- */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]),
div[data-testid="stVerticalBlockBorderWrapper"] {
  border-radius: var(--radius) !important;
}
.st-key-card-queue { margin-top: 18px; }
.st-key-card-left, .st-key-card-select, .st-key-card-right, .st-key-card-login, .st-key-card-queue {
  background: linear-gradient(180deg, rgba(22, 31, 51, 0.85) 0%, rgba(17, 24, 39, 0.85) 100%);
  border: 1px solid var(--border) !important;
  border-radius: var(--radius);
  padding: 22px 22px 18px 22px;
  box-shadow: 0 1px 0 rgba(255,255,255,0.03) inset, 0 20px 40px -24px rgba(0,0,0,0.6);
}

/* ---------- Inputs ---------- */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] {
  background: var(--surface) !important;
  border: 1px solid var(--border-strong) !important;
  border-radius: 10px !important;
  transition: border-color .15s ease, box-shadow .15s ease;
}
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within, [data-baseweb="textarea"]:focus-within {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px var(--accent-soft) !important;
}
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea { color: var(--text) !important; }
[data-baseweb="input"] > div, [data-baseweb="base-input"] { background: transparent !important; }
textarea { font-family: 'Inter', sans-serif !important; font-size: 0.9rem !important; line-height: 1.55 !important; }

/* ---------- Buttons ---------- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  border-radius: 10px !important; font-weight: 600 !important; padding: 0.55rem 1.1rem !important;
  border: 1px solid var(--border-strong) !important; background: var(--surface-2) !important;
  color: var(--text) !important; transition: all .15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
  border-color: var(--accent) !important; color: #fff !important; transform: translateY(-1px);
}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"], .stFormSubmitButton > button,
[data-testid="stBaseButton-primary"] {
  background: var(--grad) !important; border: none !important; color: #0A0E1A !important;
  box-shadow: 0 8px 24px -10px rgba(124, 131, 255, 0.8);
}
.stButton > button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {
  filter: brightness(1.08); color: #0A0E1A !important;
}
.stButton > button[kind="primary"] p, [data-testid="stBaseButton-primary"] p, .stFormSubmitButton > button p { color: #0A0E1A !important; font-weight: 700 !important; }

.stLinkButton a, [data-testid^="stBaseLinkButton"] {
  border-radius: 10px !important; font-weight: 700 !important; padding: 0.55rem 1.1rem !important;
}
[data-testid="stBaseLinkButton-primary"], .stLinkButton a[kind="primary"] {
  background: var(--grad) !important; border: none !important; color: #0A0E1A !important;
  box-shadow: 0 8px 24px -10px rgba(124, 131, 255, 0.8);
}
[data-testid="stBaseLinkButton-primary"] p, .stLinkButton a[kind="primary"] p { color: #0A0E1A !important; font-weight: 700 !important; }
[data-testid="stBaseLinkButton-primary"]:hover { filter: brightness(1.08); }

/* ---------- Tabs ---------- */
[data-testid="stTabs"] [role="tablist"], [data-baseweb="tab-list"] {
  gap: 4px; background: var(--surface); padding: 4px; border-radius: 12px; border: 1px solid var(--border);
}
[data-testid="stTabs"] [role="tab"], [data-baseweb="tab"] {
  border-radius: 9px !important; padding: 8px 16px !important; height: auto !important;
  color: var(--muted) !important; background: transparent !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"], [data-baseweb="tab"][aria-selected="true"] { background: var(--surface-3) !important; color: var(--text) !important; }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"], [data-testid="stTabs"] .react-aria-SelectionIndicator { display: none !important; }
[data-testid="stTabs"] [role="tab"] p { font-weight: 600; font-size: 0.86rem; }
[data-testid="stTabs"] [role="tablist"] { width: fit-content; margin-bottom: 6px; }

/* ---------- Table, expanders, alerts ---------- */
[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
[data-testid="stExpander"] details { background: var(--surface); border: 1px solid var(--border) !important; border-radius: 12px !important; }
[data-testid="stExpander"] summary p { font-size: 0.85rem; color: var(--muted); font-weight: 600; }
[data-testid="stAlert"] { border-radius: 12px !important; border: 1px solid var(--border) !important; }
[data-testid="stCode"] pre, .stCode pre { background: var(--surface) !important; border: 1px solid var(--border); border-radius: 12px; }
hr { border-color: var(--border) !important; }

/* ================= Custom components ================= */
.pe-hero { display: flex; align-items: center; justify-content: space-between; gap: 24px; flex-wrap: wrap;
  padding: 6px 2px 22px 2px; margin-bottom: 18px; border-bottom: 1px solid var(--border); }
.pe-eyebrow { display: inline-flex; align-items: center; gap: 8px; font-size: 0.72rem; font-weight: 700;
  letter-spacing: 0.14em; text-transform: uppercase; color: var(--accent-2); margin-bottom: 8px; }
.pe-eyebrow .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--good); box-shadow: 0 0 0 4px rgba(52,211,153,.15); }
.pe-title { font-size: 2.05rem; font-weight: 800; letter-spacing: -0.035em; line-height: 1.1; margin: 0; color: var(--text); }
.pe-title span { background: var(--grad); -webkit-background-clip: text; background-clip: text; color: transparent; }
.pe-sub { color: var(--muted); font-size: 0.95rem; margin-top: 8px; max-width: 620px; }

.pe-stepper { display: flex; align-items: center; gap: 6px; background: var(--surface); border: 1px solid var(--border);
  border-radius: 999px; padding: 6px; }
.pe-step { display: flex; align-items: center; gap: 8px; padding: 7px 14px 7px 7px; border-radius: 999px;
  font-size: 0.82rem; font-weight: 600; color: var(--faint); white-space: nowrap; }
.pe-step .num { width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center; font-size: 0.72rem;
  font-weight: 700; border: 1px solid var(--border-strong); color: var(--faint); }
.pe-step.done { color: var(--muted); }
.pe-step.done .num { background: rgba(52,211,153,.14); border-color: rgba(52,211,153,.45); color: var(--good); }
.pe-step.active { background: var(--surface-3); color: var(--text); }
.pe-step.active .num { background: var(--grad); border: none; color: #0A0E1A; }
.pe-step-sep { width: 14px; height: 1px; background: var(--border-strong); }

.pe-section { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.pe-section .badge { width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center;
  background: var(--accent-soft); color: var(--accent); font-weight: 800; font-size: 0.85rem; border: 1px solid rgba(124,131,255,.3); }
.pe-section .t { font-size: 1.08rem; font-weight: 700; color: var(--text); line-height: 1.2; }
.pe-section .s { font-size: 0.82rem; color: var(--muted); margin-top: 2px; }

.pe-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.pe-chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; font-size: 0.76rem;
  font-weight: 600; background: var(--surface-3); color: var(--text); border: 1px solid var(--border); white-space: nowrap; }
.pe-chip.accent { background: var(--accent-soft); color: #B9BDFF; border-color: rgba(124,131,255,.3); }
.pe-chip.good { background: rgba(52,211,153,.12); color: var(--good); border-color: rgba(52,211,153,.3); }
.pe-chip.warn { background: rgba(251,191,36,.12); color: var(--warn); border-color: rgba(251,191,36,.3); }
.pe-chip.risk { background: rgba(251,146,60,.12); color: var(--risk); border-color: rgba(251,146,60,.3); }
.pe-chip.bad { background: rgba(248,113,113,.12); color: var(--bad); border-color: rgba(248,113,113,.3); }
.pe-chip.muted { background: transparent; color: var(--muted); }

.pe-vertical { display: flex; gap: 14px; align-items: flex-start; background: var(--surface); border: 1px dashed var(--border-strong);
  border-radius: 12px; padding: 12px 14px; margin: 2px 0 14px 0; }
.pe-vertical .lbl { font-size: 0.7rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--faint); margin-bottom: 6px; }

.pe-kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 4px 0 14px 0; }
.pe-kpi { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; }
.pe-kpi .v { font-size: 1.35rem; font-weight: 800; color: var(--text); letter-spacing: -0.02em; }
.pe-kpi .l { font-size: 0.72rem; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: .06em; }

.pe-selected { display: flex; align-items: center; justify-content: space-between; gap: 12px; background: var(--accent-soft);
  border: 1px solid rgba(124,131,255,.35); border-radius: 12px; padding: 12px 14px; margin: 14px 0 10px 0; }
.pe-selected .n { font-weight: 700; color: var(--text); }
.pe-selected .m { font-size: 0.8rem; color: var(--muted); margin-top: 2px; }
.pe-hint { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 0.86rem; background: var(--surface);
  border: 1px dashed var(--border-strong); border-radius: 12px; padding: 12px 14px; margin-top: 12px; }

.pe-empty { text-align: center; padding: 48px 24px 40px 24px; }
.pe-empty .t { font-size: 1.1rem; font-weight: 700; color: var(--text); margin-top: 14px; }
.pe-empty .s { font-size: 0.88rem; color: var(--muted); margin: 6px auto 20px auto; max-width: 360px; line-height: 1.5; }
.pe-empty ol { text-align: left; display: inline-block; margin: 0 auto; padding: 0; list-style: none; counter-reset: s; }
.pe-empty li { counter-increment: s; color: var(--muted); font-size: 0.86rem; margin: 8px 0; display: flex; align-items: center; gap: 10px; }
.pe-empty li::before { content: counter(s); width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center;
  background: var(--surface-3); border: 1px solid var(--border-strong); font-size: 0.72rem; font-weight: 700; color: var(--text); }

.pe-firm { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 14px; }
.pe-firm .name { font-size: 1.35rem; font-weight: 800; letter-spacing: -0.025em; color: var(--text); line-height: 1.2; }
.pe-firm .meta { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.pe-firm .blurb { color: var(--muted); font-size: 0.86rem; line-height: 1.5; margin-top: 10px; font-style: italic; }

.pe-grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px; }
@media (max-width: 1100px) { .pe-grid2 { grid-template-columns: 1fr; } .pe-kpis { grid-template-columns: 1fr 1fr 1fr; } }
.pe-panel { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 14px; margin-bottom: 10px; }
.pe-cols { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); gap: 0 18px; }
@media (max-width: 1250px) { .pe-cols { grid-template-columns: 1fr; } }
.pe-hook { margin-bottom: 10px; }
.pe-panel .h { font-size: 0.7rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--faint); margin-bottom: 10px; }

.pe-contact { display: flex; align-items: center; gap: 12px; }
.pe-avatar { width: 44px; height: 44px; border-radius: 12px; display: grid; place-items: center; font-weight: 800; font-size: 0.95rem;
  background: var(--grad); color: #0A0E1A; flex-shrink: 0; }
.pe-contact .n { font-weight: 700; font-size: 1.02rem; color: var(--text); }
.pe-contact .r { font-size: 0.8rem; color: var(--muted); margin-top: 2px; }

.pe-row { display: flex; align-items: center; gap: 10px; padding: 7px 0; border-top: 1px solid var(--border); font-size: 0.86rem; }
.pe-row:first-of-type { border-top: none; }
.pe-row svg { color: var(--accent-2); flex-shrink: 0; }
.pe-row a, .pe-row span { color: var(--text) !important; text-decoration: none; overflow-wrap: anywhere; }
.pe-row .tag { color: var(--faint) !important; white-space: nowrap; }
.pe-row a.trunc { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; overflow-wrap: normal; }
.pe-row a:hover { color: var(--accent-2) !important; }
.pe-row .tag { margin-left: auto; font-size: 0.68rem; color: var(--faint); font-weight: 600; text-transform: uppercase; letter-spacing: .05em; }
.pe-none { color: var(--faint); font-size: 0.84rem; font-style: italic; }

.pe-officer { display: flex; justify-content: space-between; gap: 8px; padding: 6px 0; border-top: 1px solid var(--border); font-size: 0.84rem; }
.pe-officer:first-of-type { border-top: none; }
.pe-officer .who { color: var(--text); font-weight: 600; }
.pe-officer .since { color: var(--faint); font-size: 0.76rem; white-space: nowrap; }

.pe-hook { background: linear-gradient(135deg, rgba(124,131,255,.12), rgba(56,214,245,.06)); border: 1px solid rgba(124,131,255,.28);
  border-radius: 12px; padding: 14px 16px; }
.pe-hook .h { font-size: 0.7rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: #B9BDFF; }
.pe-hook .t { font-weight: 700; color: var(--text); margin: 4px 0 10px 0; }
.pe-hook ul { margin: 0; padding-left: 0; list-style: none; }
.pe-hook li { font-size: 0.85rem; color: var(--text); padding: 4px 0 4px 24px; position: relative; }
.pe-hook li::before { content: ""; position: absolute; left: 4px; top: 10px; width: 8px; height: 8px; border-radius: 50%; background: var(--grad); }

/* Sidebar components */
.pe-brand { display: flex; align-items: center; gap: 12px; padding: 4px 0 18px 0; border-bottom: 1px solid var(--border); margin-bottom: 16px; }
.pe-logo { width: 40px; height: 40px; border-radius: 12px; background: var(--grad); display: grid; place-items: center; color: #0A0E1A;
  box-shadow: 0 10px 24px -10px rgba(124,131,255,.9); }
.pe-brand .n { font-weight: 800; font-size: 1.05rem; color: var(--text); letter-spacing: -0.02em; }
.pe-brand .s { font-size: 0.75rem; color: var(--muted); }
.pe-side-h { font-size: 0.68rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--faint); margin: 18px 0 8px 0; }
.pe-status { display: flex; align-items: center; justify-content: space-between; font-size: 0.84rem; color: var(--text); padding: 7px 0; }
.pe-status .st { display: inline-flex; align-items: center; gap: 6px; font-size: 0.76rem; font-weight: 600; }
.pe-status .st.ok { color: var(--good); } .pe-status .st.off { color: var(--bad); } .pe-status .st.idle { color: var(--muted); }
.pe-status .st::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.pe-stats { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
.pe-stat { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 10px; text-align: center; }
.pe-stat .v { font-weight: 800; font-size: 1.1rem; color: var(--text); }
.pe-stat .l { font-size: 0.64rem; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; font-weight: 600; margin-top: 2px; }

/* Login */
.pe-login-head { text-align: center; margin: 8vh 0 22px 0; }
.pe-login-head .pe-logo { width: 54px; height: 54px; margin: 0 auto 16px auto; border-radius: 16px; }
.pe-login-head .t { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.03em; color: var(--text); }
.pe-login-head .s { color: var(--muted); font-size: 0.92rem; margin-top: 6px; }
</style>
"""

_ICON_PATHS = {
    "mail": '<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/>',
    "phone": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    "pin": '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "check": '<polyline points="20 6 9 17 4 12"/>',
    "lock": '<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "pointer": '<path d="M3 3l7.07 16.97 2.51-7.39 7.39-2.51L3 3z"/>',
}


def _full_width_kwargs() -> Dict[str, Any]:
    """Full-width buttons: 'width' on Streamlit 1.46+, 'use_container_width' before that."""
    import inspect
    try:
        if "width" in inspect.signature(st.button).parameters:
            return {"width": "stretch"}
    except (TypeError, ValueError):
        pass
    return {"use_container_width": True}


FULL_WIDTH = _full_width_kwargs()


def icon(name: str, size: int = 16, stroke: float = 2) -> str:
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
        f' stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{_ICON_PATHS[name]}</svg>'
    )


def esc(value: Any) -> str:
    """Escapes scraped/registry text before it goes into HTML."""
    return html_lib.escape(str(value if value is not None else ""), quote=True)


def render_html(markup: str, target=None) -> None:
    """Renders HTML via markdown. Lines are flattened so markdown never treats indentation as code."""
    flat = "".join(line.strip() for line in markup.splitlines())
    (target or st).markdown(flat, unsafe_allow_html=True)


def inject_css() -> None:
    st.markdown(APP_CSS, unsafe_allow_html=True)


def chip(text: str, tone: str = "") -> str:
    return f'<span class="pe-chip {tone}">{esc(text)}</span>'


def section_header(num: str, title: str, subtitle: str = "") -> None:
    render_html(
        f'<div class="pe-section"><div class="badge">{num}</div><div>'
        f'<div class="t">{esc(title)}</div>'
        + (f'<div class="s">{esc(subtitle)}</div>' if subtitle else "")
        + "</div></div>"
    )


def hero_html(active_step: int) -> str:
    steps = ["Target", "Select", "Enrich", "Pitch"]
    parts = []
    for i, label in enumerate(steps, start=1):
        state = "done" if i < active_step else "active" if i == active_step else ""
        num = icon("check", 12, 3) if state == "done" else str(i)
        parts.append(f'<div class="pe-step {state}"><span class="num">{num}</span>{label}</div>')
    stepper = '<div class="pe-step-sep"></div>'.join(parts)
    return (
        '<div class="pe-hero"><div>'
        '<div class="pe-eyebrow"><span class="dot"></span>Live UK registry · Open web intelligence</div>'
        '<div class="pe-title">Prospect Discovery <span>&amp; Dossier Engine</span></div>'
        '<div class="pe-sub">Find active UK firms by sector, surface the decision-maker and their'
        ' direct channels, then generate a CRM-integration pitch and a one-page dossier.</div>'
        f'</div><div class="pe-stepper">{stepper}</div></div>'
    )


def confidence_chip(confidence: Optional[str]) -> str:
    tones = {
        "High": ("good", "High-confidence match"),
        "Medium": ("warn", "Medium-confidence match"),
        "Low": ("risk", "Low-confidence match"),
        "Manual": ("accent", "Website entered manually"),
    }
    tone, label = tones.get(confidence or "", ("bad", "Website not found"))
    return chip(label, tone)


def display_officer_name(raw: str) -> str:
    """'BYWATER, Paul James' -> 'Paul James Bywater'; company officers are just title-cased."""
    if "," in raw:
        surname, forenames = raw.split(",", 1)
        return f"{forenames.strip().title()} {surname.strip().title()}".strip()
    return raw.title()


def initials(name: str) -> str:
    words = [w for w in re.split(r"[\s&/]+", name or "") if w and w[0].isalpha()]
    return ("".join(w[0] for w in words[:2]) or "?").upper()


# ==========================================
# 0. PASSWORD GATEWAY (STREAMLIT SECRETS)
# ==========================================


def check_password() -> bool:
    # Fail CLOSED: if the secret is missing or misconfigured, nobody gets in.
    try:
        configured_password = st.secrets["APP_PASSWORD"]
    except Exception:
        configured_password = None
    if not configured_password:
        st.set_page_config(page_title=f"{APP_NAME} · Locked", page_icon="🎯", layout="centered")
        inject_css()
        render_html(
            f'<div class="pe-login-head"><div class="pe-logo">{icon("lock", 24, 2.2)}</div>'
            '<div class="t">App locked</div>'
            '<div class="s">APP_PASSWORD isn\'t set in Streamlit Secrets, so access is blocked.</div></div>'
        )
        st.error("Add APP_PASSWORD under App settings → Secrets, then reload.")
        return False

    def password_entered():
        if hmac.compare_digest(
            st.session_state.get("password", "").encode("utf-8"),
            str(configured_password).encode("utf-8"),
        ):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.set_page_config(page_title=f"{APP_NAME} · Sign in", page_icon="🎯", layout="centered")
    inject_css()
    _, mid, _ = st.columns([1, 2.2, 1])
    with mid:
        render_html(
            f'<div class="pe-login-head"><div class="pe-logo">{icon("target", 26, 2.2)}</div>'
            f'<div class="t">{APP_NAME}</div>'
            f'<div class="s">{APP_TAGLINE} · Authorised users only</div></div>'
        )
        with st.container(key="card-login"):
            with st.form("Credentials", border=False):
                st.text_input("Access password", type="password", key="password",
                              placeholder="Enter your password")
                st.form_submit_button("Sign in", on_click=password_entered,
                                      type="primary", **FULL_WIDTH)
            if (
                "password_correct" in st.session_state
                and not st.session_state["password_correct"]
            ):
                st.error("Incorrect password. Please try again.")

    return False


if not check_password():
    st.stop()

# ==========================================
# 1. VERTICALS, CRMS & PITCH PLAYBOOKS
# ==========================================

VERTICAL_PRESETS = {
    "Estate & Lettings Agents": {
        "sic_codes": ["68310"],
        "description": "Real estate agencies & letting operations",
        "search_hint": "Estate Agents",
        "crms": ["Street", "Alto", "Reapit", "Dezrez", "Jupix"],
        "primary_hook": "CRM Integration (Street / Alto / Reapit)",
        "fallback_greeting": "Lettings & Sales Team",
        "pitch_bullets": [
            "Screen pop-up of every client or landlord record the moment they call",
            "Automatic voice recording syncing directly to the property file",
            "Click to dial directly inside your CRM / property portal",
            "Every lead, missed call & call note tracked automatically",
        ],
        "default_cta": "Let me know how many phones or softphone users you have, and I'll send over a quote.",
    },
    "Dental Practices": {
        "sic_codes": ["86230"],
        "description": "Dental practice activities",
        "search_hint": "Dental Practice",
        "crms": ["Dentally", "EXACT", "Carestream R4"],
        "primary_hook": "PMS Integration (Dentally / EXACT / R4)",
        "fallback_greeting": "Practice Manager",
        "pitch_bullets": [
            "Patient records pop up on reception screens when the phone rings",
            "Calls log automatically against the right patient chart",
            "Missed calls are flagged instantly for follow up and recall retention",
            "Call recordings are stored compliantly against the patient file",
        ],
        "default_cta": "How many handsets does the practice currently use? I can send over a no obligation quote.",
    },
    "Solicitors & Legal Practices": {
        "sic_codes": ["69102"],
        "description": "Solicitors & legal service providers",
        "search_hint": "Solicitors",
        "crms": ["Clio", "LEAP", "Proclaim", "Actionstep"],
        "primary_hook": "Matter Management Integration (Clio / LEAP)",
        "fallback_greeting": "Practice Manager",
        "pitch_bullets": [
            "Dial straight from the active client or matter record",
            "Mobile & desktop softphone app so fee earners can take calls securely anywhere",
            "One unified system across reception, every fee earner and all branch offices",
            "Call recordings & billable duration synced back to the matter file",
        ],
        "default_cta": "Let me know which system you run and roughly how many users you have, and I'll send over a quote.",
    },
    "Accountants & Auditors": {
        "sic_codes": ["69201"],
        "description": "Accounting, bookkeeping & tax consultancy",
        "search_hint": "Accountants",
        "crms": ["Iris", "CCH", "TaxCalc", "Xero Practice Manager"],
        "primary_hook": "Client Portal & Time Tracking Integration",
        "fallback_greeting": "Practice Partner",
        "pitch_bullets": [
            "Client identification card pops on screen the moment they call",
            "Automatic call logging against client tax and year-end audit folders",
            "Seamless transfer between desk phones and laptop softphones for hybrid staff",
            "Consolidated line rental and cloud voice to reduce fixed telecom overheads",
        ],
        "default_cta": "Let me know your approximate team size and I can send over an indicative quote.",
    },
    "General Medical Clinics": {
        "sic_codes": ["86210"],
        "description": "General medical practice activities",
        "search_hint": "Clinic",
        "crms": ["EMIS Web", "SystmOne", "Semble", "Heydoc"],
        "primary_hook": "Clinical System Integration & Triage Routing",
        "fallback_greeting": "Clinic Manager",
        "pitch_bullets": [
            "Patient record screen-pop to accelerate inbound triage",
            "Automated call queueing & peak-time patient callback features",
            "Encrypted, compliant voice recordings stored per patient file",
            "Direct transfer lines between triage staff, clinicians, and administration",
        ],
        "default_cta": "How many lines or handsets do you operate? I can send over a no obligation overview.",
    },
}


class OfficerInfo(BaseModel):
    name: str
    role: str  # Friendly label, e.g. "Director"
    raw_role: str = ""  # Companies House value, e.g. "llp-designated-member"
    appointed_on: Optional[str] = None


class ScrapedLead(BaseModel):
    company_name: str
    company_number: Optional[str] = None
    sic_codes: List[str] = Field(default_factory=list)
    sector_guess: str = "General B2B"
    registered_address: Optional[str] = None
    website_url: Optional[str] = None
    phones_found: List[str] = Field(default_factory=list)
    emails_found: List[str] = Field(default_factory=list)
    officers: List[OfficerInfo] = Field(default_factory=list)
    site_meta_description: Optional[str] = None
    website_confidence: Optional[str] = None  # High / Medium / Low / Manual
    website_reasons: List[str] = Field(default_factory=list)
    discovery_notes: List[str] = Field(default_factory=list)
    other_emails: List[str] = Field(default_factory=list)  # Third-party addresses (agencies, regulators)
    pages_checked: List[str] = Field(default_factory=list)


# ==========================================
# 2. ENRICHMENT & SCRAPING ENGINE
# ==========================================


# ------------------------------------------------------------------
# Web discovery & extraction helpers
# ------------------------------------------------------------------

LEGAL_SUFFIX_WORDS = {
    "LTD", "LIMITED", "PLC", "LLP", "LP", "GROUP", "HOLDINGS", "UK", "(UK)",
    "CO", "COMPANY", "THE", "T/A", "INTERNATIONAL",
}

# Words too common to identify a firm on their own (kept for the full-name match)
GENERIC_NAME_WORDS = {
    "and", "the", "of", "dental", "dentist", "dentists", "practice", "practices",
    "surgery", "clinic", "clinics", "medical", "health", "healthcare", "care",
    "solicitors", "solicitor", "law", "legal", "lawyers", "partners", "partnership",
    "accountants", "accountancy", "accounting", "tax", "bookkeeping", "associates",
    "estate", "estates", "agents", "agency", "lettings", "letting", "property",
    "properties", "residential", "sales", "services", "consultants", "consultancy",
    "management", "uk", "ltd", "limited", "llp", "plc", "group", "holdings", "co",
}

# Directories, portals, social media, regulators and review sites — never a firm's own site.
BLOCKED_DOMAINS = {
    "company-information.service.gov.uk", "gov.uk", "companieshouse.gov.uk",
    "endole.co.uk", "duedil.com", "opencorporates.com", "companycheck.co.uk",
    "checkcompany.co.uk", "companiesintheuk.co.uk", "bizdb.co.uk", "companieslist.co.uk",
    "company-data.co.uk", "ukcompanieslist.com", "find-and-update.company-information.service.gov.uk",
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "youtube.com", "tiktok.com", "pinterest.com", "wikipedia.org",
    "yell.com", "thomsonlocal.com", "scoot.co.uk", "192.com", "cylex-uk.co.uk",
    "freeindex.co.uk", "hotfrog.co.uk", "yelp.co.uk", "yelp.com", "trustpilot.com",
    "google.com", "google.co.uk", "bing.com", "duckduckgo.com", "maps.apple.com",
    "rightmove.co.uk", "zoopla.co.uk", "onthemarket.com", "primelocation.com",
    "allagents.co.uk", "getagent.co.uk", "homipi.co.uk", "propertymark.co.uk",
    "whatclinic.com", "doctify.com", "topdoctors.co.uk", "cqc.org.uk", "gdc-uk.org",
    "lawsociety.org.uk", "solicitors.lawsociety.org.uk", "sra.org.uk",
    "reviewsolicitors.co.uk", "solicitors.guru", "icaew.com", "accaglobal.com",
    "checkatrade.com", "ratedpeople.com", "bark.com", "mybuilder.com",
    "indeed.com", "indeed.co.uk", "glassdoor.co.uk", "reed.co.uk", "totaljobs.com",
    "zoominfo.com", "rocketreach.co", "apollo.io", "dnb.com", "kompass.com",
    "crunchbase.com", "bloomberg.com", "misterwhat.co.uk", "brownbook.net",
    "fyple.co.uk", "opendi.co.uk", "tuugo.co.uk", "infobel.com", "cybo.com",
    "n49.com", "businessmagnet.co.uk", "streetcheck.co.uk", "amazon.co.uk",
    "ebay.co.uk", "gumtree.com", "tripadvisor.co.uk", "118118.com", "ukphonebook.com",
}
# Blocked only as the exact domain (their subdomains can be real practice sites, e.g. xyzsurgery.nhs.uk)
BLOCKED_EXACT_ONLY = {"nhs.uk"}

FREE_MAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "hotmail.com", "hotmail.co.uk", "outlook.com",
    "live.co.uk", "live.com", "yahoo.com", "yahoo.co.uk", "btinternet.com",
    "btconnect.com", "icloud.com", "me.com", "aol.com", "sky.com", "virginmedia.com",
    "talktalk.net", "nhs.net",
}

# Link hints for pages worth scraping, most useful first
CONTACT_PAGE_HINTS = [
    "contact", "get-in-touch", "get in touch", "getintouch", "find-us", "find us",
    "our-team", "our team", "meet-the-team", "meet the team", "team", "our-people",
    "people", "branches", "offices", "about",
]

JUNK_EMAIL_MARKERS = (
    "example.", "sentry", "wixpress", "domain.com", "yourname", "youremail",
    "email.com", "@2x", "noreply", "no-reply", "donotreply", "u003e", "godaddy",
    "wordpress", "schema.org", "@sentry", "@ingest", "test@",
)
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+'-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,24}")
PHONE_TEXT_RE = re.compile(
    r"(?:\+\s?44\s?(?:\(0\)\s?)?|0044\s?|\(?0)\d[\d \-\(\)]{7,14}\d"
)


def domain_of(url: str) -> Optional[str]:
    if not url:
        return None
    if "://" not in url:
        url = "https://" + url
    host = (urlparse(url).hostname or "").lower().strip(".")
    return host[4:] if host.startswith("www.") else host or None


def is_blocked_domain(domain: str) -> bool:
    domain = domain.lower()
    if domain in BLOCKED_EXACT_ONLY:
        return True
    return any(domain == b or domain.endswith("." + b) for b in BLOCKED_DOMAINS)


def domain_label(domain: str) -> str:
    """'www.hart-new-homes.co.uk' -> 'hartnewhomes'"""
    parts = domain.lower().split(".")
    for suffix_len in (3, 2, 1):  # handles .co.uk, .org.uk, .com etc
        tail = ".".join(parts[-suffix_len:])
        if tail in {"co.uk", "org.uk", "me.uk", "ltd.uk", "plc.uk", "nhs.uk", "net.uk"} and len(parts) > 2:
            return re.sub(r"[^a-z0-9]", "", parts[-3])
    return re.sub(r"[^a-z0-9]", "", parts[-2] if len(parts) >= 2 else parts[0])


def distinctive_name_tokens(company_name: str) -> List[str]:
    """'HART NEW HOMES (WALSALL) LIMITED' -> ['hart', 'new', 'homes', 'walsall']"""
    words = re.sub(r"[^a-z0-9 ]", " ", company_name.lower().replace("&", " and ")).split()
    words = [w for w in words if w.upper() not in LEGAL_SUFFIX_WORDS]
    distinct = [w for w in words if w not in GENERIC_NAME_WORDS]
    return distinct or words


def guess_domains(company_name: str) -> List[str]:
    """Likely domains straight from the name — a fallback when search engines block us."""
    words = [w for w in re.sub(r"[^a-z0-9& ]", " ", company_name.lower()).split()
             if w.upper() not in LEGAL_SUFFIX_WORDS and w != "&"]
    if not words:
        return []
    joined, hyphen = "".join(words), "-".join(words)
    distinct = [w for w in words if w not in GENERIC_NAME_WORDS]
    guesses = [f"{joined}.co.uk", f"{joined}.com", f"{hyphen}.co.uk", f"{joined}.uk"]
    if distinct and distinct != words:
        short = "".join(distinct)
        if len(short) >= 5:
            guesses.append(f"{short}.co.uk")
    return [g for g in dict.fromkeys(guesses) if len(g) <= 70]


def decode_cfemail(hex_string: str) -> Optional[str]:
    """Decodes Cloudflare's 'email protection' obfuscation."""
    try:
        data = bytes.fromhex(hex_string)
        key = data[0]
        return "".join(chr(b ^ key) for b in data[1:])
    except (ValueError, IndexError):
        return None


def clean_email(raw: str) -> Optional[str]:
    em = unquote(raw or "").strip().strip(".,;:()<>[]'\"").lower()
    em = em.split("?")[0]
    m = EMAIL_RE.fullmatch(em)
    if not m or len(em) > 80:
        return None
    if em.endswith(IMAGE_EXTS) or any(j in em for j in JUNK_EMAIL_MARKERS):
        return None
    return em


def extract_emails(soup: BeautifulSoup, html: str) -> Set[str]:
    found: Set[str] = set()
    # 1. mailto: links
    for a in soup.select('a[href^="mailto:" i]'):
        em = clean_email(a["href"].split(":", 1)[1])
        if em:
            found.add(em)
    # 2. Cloudflare-protected emails
    for el in soup.select("[data-cfemail]"):
        em = clean_email(decode_cfemail(el.get("data-cfemail", "")) or "")
        if em:
            found.add(em)
    for a in soup.select('a[href*="/cdn-cgi/l/email-protection#"]'):
        em = clean_email(decode_cfemail(a["href"].split("#", 1)[1]) or "")
        if em:
            found.add(em)
    # 3. Visible text, including "name [at] firm [dot] co.uk" style
    text = soup.get_text(" ")
    text = re.sub(r"\s*[\[\(\{]\s*at\s*[\]\)\}]\s*", "@", text, flags=re.I)
    text = re.sub(r"\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*", ".", text, flags=re.I)
    # 4. Structured data (JSON-LD "email": "...")
    for script in soup.find_all("script", type="application/ld+json"):
        text += " " + (script.string or "")
    for raw in EMAIL_RE.findall(text):
        em = clean_email(raw)
        if em:
            found.add(em)
    return found


def normalise_uk_phone(raw: str) -> Optional[str]:
    """Any UK format -> standard display format, e.g. '+44 (0)1922 123456' -> '01922 123456'."""
    if not raw:
        return None
    raw = unquote(raw).replace("(0)", "")
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("0044"):
        digits = "0" + digits[4:]
    elif digits.startswith("44") and len(digits) == 12:
        digits = "0" + digits[2:]
    if not digits.startswith("0") or len(digits) not in (10, 11) or digits[1] not in "123578":
        return None
    d = digits
    if len(d) == 10:
        return f"{d[:5]} {d[5:]}"
    if d.startswith("02"):
        return f"{d[:3]} {d[3:7]} {d[7:]}"            # 020 7946 0000
    if d.startswith(("03", "08")):
        return f"{d[:4]} {d[4:7]} {d[7:]}"            # 0800 123 4567
    if d.startswith("07"):
        return f"{d[:5]} {d[5:]}"                     # 07700 900123
    if d[2] == "1" or d[3] == "1":
        return f"{d[:4]} {d[4:7]} {d[7:]}"            # 0121 234 5678
    return f"{d[:5]} {d[5:]}"                         # 01922 123456


def extract_phones(soup: BeautifulSoup, html: str) -> List[Tuple[str, int]]:
    """Returns (phone, weight). Clickable tel: links count more than plain text."""
    out: List[Tuple[str, int]] = []
    for a in soup.select('a[href^="tel:" i], a[href^="callto:" i]'):
        ph = normalise_uk_phone(a["href"].split(":", 1)[1])
        if ph:
            out.append((ph, 3))
    for script in soup(["script", "style", "noscript"]):
        script.decompose()
    for raw in PHONE_TEXT_RE.findall(soup.get_text(" ")):
        ph = normalise_uk_phone(raw)
        if ph:
            out.append((ph, 1))
    return out


def _describe_ch_error(resp: requests.Response) -> str:
    """Turns a Companies House HTTP error into a plain-English message."""
    code = resp.status_code
    if code == 401:
        return "Companies House rejected the API key (401). Check COMPANIES_HOUSE_KEY in Secrets."
    if code == 403:
        return "Companies House refused access (403). The key may not be a REST API key."
    if code == 404:
        return "No matching companies found (404)."
    if code == 416:
        return "Too many results requested. Narrow the search and try again."
    if code == 429:
        return "Companies House rate limit hit (600 requests / 5 mins). Wait a few minutes and retry."
    if code >= 500:
        return f"Companies House is having problems right now ({code}). Try again shortly."
    return f"Companies House returned an unexpected error ({code})."



class LeadEnricher:

    def __init__(self, ch_api_key: Optional[str] = None):
        self.ch_api_key = ch_api_key.strip() if ch_api_key else None
        self.base_url = "https://api.company-information.service.gov.uk"
        self.headers = self._get_auth_headers()
        self.web_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
        }
        self.session = requests.Session()
        self.session.headers.update(self.web_headers)

    def _get_auth_headers(self) -> Dict[str, str]:
        if not self.ch_api_key:
            return {}
        token = base64.b64encode(f"{self.ch_api_key}:".encode("utf-8")).decode(
            "utf-8"
        )
        return {"Authorization": f"Basic {token}"}

    def browse_vertical(
        self,
        sic_codes: List[str],
        location_keyword: Optional[str] = None,
        company_name_includes: Optional[str] = None,
        limit: int = 25,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Returns (results, error_message). error_message is None on success."""
        if not self.ch_api_key:
            return [], "No Companies House API key configured."

        url = f"{self.base_url}/advanced-search/companies"
        params: Dict[str, Any] = {
            "sic_codes": ",".join(sic_codes),
            "company_status": "active",
            "size": limit,
        }

        if location_keyword and location_keyword.strip():
            params["location"] = location_keyword.strip()

        if company_name_includes and company_name_includes.strip():
            params["company_name_includes"] = company_name_includes.strip()

        try:
            resp = requests.get(
                url, headers=self.headers, params=params, timeout=12
            )
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                results = []
                for item in items:
                    addr = item.get("registered_office_address", {})
                    loc_parts = [
                        addr.get("locality"),
                        addr.get("postal_code"),
                    ]
                    location_str = ", ".join([p for p in loc_parts if p])
                    results.append(
                        {
                            "Company Name": item.get("company_name", ""),
                            "Company Number": item.get("company_number", ""),
                            "Incorporated": item.get(
                                "date_of_creation", "N/A"
                            ),
                            "Town / Postcode": location_str or "UK",
                            "Status": item.get("company_status", "").title(),
                            "Companies House": (
                                "https://find-and-update.company-information.service.gov.uk/company/"
                                + item.get("company_number", "")
                            ),
                        }
                    )
                return results, None
            if resp.status_code == 404:
                # Advanced search answers 404 when nothing matches.
                return [], None
            return [], _describe_ch_error(resp)
        except requests.exceptions.Timeout:
            return [], "Companies House didn't respond in time. Please try again."
        except requests.exceptions.RequestException as exc:
            return [], f"Couldn't reach Companies House ({exc.__class__.__name__})."
        except ValueError:
            return [], "Companies House returned an unreadable response."

    def get_company_details(self, company_number: str) -> Dict[str, Any]:
        if not self.ch_api_key:
            return {}
        url = f"{self.base_url}/company/{company_number}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return {}

    def get_officers(self, company_number: str) -> List[OfficerInfo]:
        if not self.ch_api_key:
            return []
        url = f"{self.base_url}/company/{company_number}/officers"
        officers = []
        self.last_officer_error = None
        try:
            # NB: don't send register_view=true. Companies House answers 400/404 for most firms,
            # which silently returned no directors. Resigned officers are filtered out below instead.
            resp = requests.get(
                url,
                headers=self.headers,
                params={"items_per_page": 100},
                timeout=10,
            )
            if resp.status_code == 429:  # Rate limited during a big batch: wait and retry once
                time.sleep(2)
                resp = requests.get(url, headers=self.headers, params={"items_per_page": 100}, timeout=10)
            if resp.status_code != 200:
                self.last_officer_error = f"Companies House officers lookup failed ({resp.status_code})"
            if resp.status_code == 200:
                for item in resp.json().get("items", []):
                    if not item.get("resigned_on"):
                        raw_role = (item.get("officer_role") or "").lower()
                        officers.append(
                            OfficerInfo(
                                name=item.get("name", "Unknown"),
                                role=format_role(raw_role),
                                raw_role=raw_role,
                                appointed_on=item.get("appointed_on"),
                            )
                        )
        except Exception as exc:
            self.last_officer_error = f"Companies House officers lookup failed ({exc.__class__.__name__})"
        return officers

    # ------------------------------------------------------------------
    # WEBSITE DISCOVERY (search results + domain guesses, verified & scored)
    # ------------------------------------------------------------------

    def _fetch_html(self, url: str, timeout: int = 7) -> Optional[Tuple[str, str]]:
        """GETs a page. Returns (final_url_after_redirects, html) or None."""
        try:
            resp = self.session.get(url, timeout=timeout, allow_redirects=True)
            ctype = resp.headers.get("Content-Type", "").lower()
            if resp.status_code == 200 and ("html" in ctype or not ctype):
                return resp.url, resp.text
        except requests.exceptions.RequestException:
            pass
        return None

    def _search_duckduckgo(self, query: str) -> Tuple[List[str], Optional[str]]:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        try:
            resp = self.session.get(url, timeout=7)
        except requests.exceptions.RequestException:
            return [], "DuckDuckGo unreachable"
        if resp.status_code != 200 or "anomaly" in resp.text.lower()[:5000]:
            return [], "DuckDuckGo blocked the request"
        soup = BeautifulSoup(resp.text, "html.parser")
        urls: List[str] = []
        for a in soup.select("a.result__a[href]"):
            href = a["href"]
            if "uddg=" in href:
                href = unquote(parse_qs(urlparse(href).query).get("uddg", [""])[0])
            if href.startswith("//"):
                href = "https:" + href
            urls.append(href)
        if not urls:  # Older markup: display URL only
            for span in soup.select(".result__url"):
                urls.append("https://" + span.get_text().strip())
        return urls, None

    def _search_bing(self, query: str) -> Tuple[List[str], Optional[str]]:
        url = f"https://www.bing.com/search?q={quote_plus(query)}&setlang=en-GB&cc=GB"
        try:
            resp = self.session.get(url, timeout=7)
        except requests.exceptions.RequestException:
            return [], "Bing unreachable"
        if resp.status_code != 200:
            return [], "Bing blocked the request"
        soup = BeautifulSoup(resp.text, "html.parser")
        urls: List[str] = []
        for a in soup.select("li.b_algo h2 a[href]"):
            href = a["href"]
            if "bing.com/ck/a" in href:  # Bing tracking wrapper: u=a1<base64url>
                u = parse_qs(urlparse(href).query).get("u", [""])[0]
                if u.startswith("a1"):
                    try:
                        b64 = u[2:] + "=" * (-len(u[2:]) % 4)
                        href = base64.urlsafe_b64decode(b64).decode("utf-8", "ignore")
                    except Exception:
                        continue
            urls.append(href)
        return urls, None

    def _score_candidate(
        self, domain: str, html: str, company_name: str,
        company_number: Optional[str], postcode: Optional[str], town: Optional[str],
    ) -> Tuple[int, List[str]]:
        """Scores how likely a site belongs to this company. Returns (score, reasons)."""
        score, reasons = 0, []
        tokens = distinctive_name_tokens(company_name)
        compact = "".join(tokens)
        label = domain_label(domain)

        # 1. Domain vs company name
        if compact and len(compact) >= 4 and (compact in label or (len(label) >= 5 and label in compact)):
            score += 45
            reasons.append("domain matches company name")
        else:
            hits = [t for t in tokens if len(t) >= 3 and t in label]
            if hits:
                score += min(15 * len(hits), 30)
                reasons.append(f"domain contains '{', '.join(hits)}'")

        soup = BeautifulSoup(html, "html.parser")
        title = (soup.title.get_text(" ", strip=True) if soup.title else "").lower()
        og = soup.find("meta", attrs={"property": "og:site_name"})
        if og and og.get("content"):
            title += " " + og["content"].lower()
        text = soup.get_text(" ", strip=True)
        text_l = text.lower()
        text_compact = re.sub(r"\s+", "", text_l)

        # 2. Page title / site name
        title_hits = [t for t in tokens if len(t) >= 3 and t in title]
        if title_hits:
            score += min(10 * len(title_hits), 20)
            reasons.append("name in page title")

        # 3. UK companies must show their registered number on their website
        if company_number:
            num = company_number.lstrip("0")
            if re.search(rf"(?<!\d)0*{re.escape(num)}(?!\d)", text_compact) and len(num) >= 5:
                score += 50
                reasons.append(f"company number {company_number} shown on site")

        # 4. Legal name / location on page
        legal = re.sub(r"\s+", " ", company_name.lower()).strip()
        if legal and legal in text_l:
            score += 20
            reasons.append("full legal name on site")
        if postcode and postcode.replace(" ", "").lower() in text_compact:
            score += 15
            reasons.append(f"registered postcode {postcode} on site")
        elif town and len(town) > 3 and town.lower() in text_l:
            score += 5
            reasons.append(f"mentions {town}")
        return score, reasons

    def auto_discover_website(
        self,
        company_name: str,
        location: Optional[str] = None,
        company_number: Optional[str] = None,
        postcode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Finds the firm's own website. Returns url, confidence, reasons and notes."""
        notes: List[str] = []
        clean_name = " ".join(w for w in re.sub(r"[^\w&' ]", " ", company_name).split()
                              if w.upper() not in LEGAL_SUFFIX_WORDS)
        query = f"{clean_name} {location or ''}".strip()

        # A. Search engines (DuckDuckGo, then Bing as a fallback)
        search_urls: List[str] = []
        for engine in (self._search_duckduckgo, self._search_bing):
            urls, err = engine(query)
            if err:
                notes.append(err)
            search_urls.extend(urls)
            if urls:
                break

        candidates: List[str] = []
        for u in search_urls:
            d = domain_of(u)
            if d and not is_blocked_domain(d) and d not in candidates:
                candidates.append(d)
        candidates = candidates[:6]

        # B. Domain guesses (works even when search engines block us)
        for guess in guess_domains(company_name):
            if guess not in candidates:
                candidates.append(guess)

        # C. Fetch & score candidates in parallel
        def check(domain: str):
            page = self._fetch_html(f"https://{domain}") or self._fetch_html(f"http://{domain}")
            if not page:
                return None
            final_url, html = page
            final_domain = domain_of(final_url) or domain
            if is_blocked_domain(final_domain):
                return None
            score, reasons = self._score_candidate(
                final_domain, html, company_name, company_number, postcode, location
            )
            return final_url, final_domain, score, reasons

        results = []
        with ThreadPoolExecutor(max_workers=6) as pool:
            for res in pool.map(check, candidates):
                if res:
                    results.append(res)

        if not results:
            notes.append("No candidate website responded")
            return {"url": None, "confidence": None, "reasons": [], "notes": notes}

        results.sort(key=lambda r: r[2], reverse=True)
        final_url, final_domain, score, reasons = results[0]
        if score < 35:
            notes.append(f"Best candidate {final_domain} scored too low to trust")
            return {"url": None, "confidence": None, "reasons": reasons, "notes": notes,
                    "rejected": final_domain}

        confidence = "High" if score >= 80 else "Medium" if score >= 55 else "Low"
        parsed = urlparse(final_url)
        return {
            "url": f"{parsed.scheme}://{parsed.netloc}",
            "confidence": confidence,
            "reasons": reasons,
            "notes": notes,
        }

    # ------------------------------------------------------------------
    # CONTACT SCRAPING (contact/about/team pages, hidden emails, clean phones)
    # ------------------------------------------------------------------

    def _find_contact_pages(self, soup: BeautifulSoup, root: str) -> List[str]:
        root_host = domain_of(root)
        ranked: List[Tuple[int, str]] = []
        for a in soup.find_all("a", href=True):
            href = urljoin(root + "/", a["href"].strip())
            if not href.startswith("http") or domain_of(href) != root_host:
                continue
            path_and_text = (urlparse(href).path + " " + a.get_text(" ", strip=True)).lower()
            for rank, hint in enumerate(CONTACT_PAGE_HINTS):
                if hint in path_and_text:
                    clean = href.split("#")[0].rstrip("/")
                    if clean != root.rstrip("/"):
                        ranked.append((rank, clean))
                    break
        seen, pages = set(), []
        for _, url in sorted(ranked):
            if url not in seen:
                seen.add(url)
                pages.append(url)
        return pages[:4]

    def scrape_contact_channels(self, base_url: str) -> Dict[str, Any]:
        empty = {"emails": [], "other_emails": [], "phones": [], "description": "",
                 "resolved_url": None, "pages_checked": []}
        if not base_url:
            return empty
        if not base_url.startswith("http"):
            base_url = f"https://{base_url}"

        home = self._fetch_html(base_url)
        if not home and base_url.startswith("https://"):
            home = self._fetch_html("http://" + base_url[len("https://"):])
        if not home:
            return {**empty, "resolved_url": base_url}

        final_url, home_html = home
        parsed = urlparse(final_url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        site_domain = domain_of(root)
        home_soup = BeautifulSoup(home_html, "html.parser")

        extra_pages = self._find_contact_pages(home_soup, root)
        if not extra_pages:
            extra_pages = [urljoin(root, p) for p in ("/contact", "/contact-us", "/about", "/about-us")]

        pages_html = [(final_url, home_html)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            for url, page in zip(extra_pages, pool.map(self._fetch_html, extra_pages)):
                if page:
                    pages_html.append((page[0], page[1]))

        email_hits: Dict[str, int] = {}
        phone_scores: Dict[str, int] = {}
        description = ""

        for _, html in pages_html:
            soup = BeautifulSoup(html, "html.parser")
            if not description:
                for attrs in ({"name": "description"}, {"property": "og:description"}):
                    tag = soup.find("meta", attrs=attrs)
                    if tag and tag.get("content"):
                        description = tag["content"].strip()
                        break
            for em in extract_emails(soup, html):
                email_hits[em] = email_hits.get(em, 0) + 1
            for ph, weight in extract_phones(soup, html):
                phone_scores[ph] = phone_scores.get(ph, 0) + weight

        own, freemail, other = [], [], []
        for em in email_hits:
            dom = em.split("@", 1)[1]
            if dom == site_domain or dom.endswith("." + site_domain) or site_domain.endswith("." + dom):
                own.append(em)
            elif dom in FREE_MAIL_DOMAINS:
                freemail.append(em)
            else:
                other.append(em)

        phones = sorted(phone_scores, key=lambda p: (-phone_scores[p], p))[:5]
        return {
            "emails": sorted(own) + sorted(freemail),
            "other_emails": sorted(other),
            "phones": phones,
            "description": description,
            "resolved_url": root,
            "pages_checked": [u for u, _ in pages_html],
        }

    def enrich_selected_company(
        self,
        company_number: str,
        sector_name: str,
        manual_website: Optional[str] = None,
    ) -> ScrapedLead:
        ch_data = self.get_company_details(company_number)
        company_name = ch_data.get("company_name", company_number)

        address_dict = ch_data.get("registered_office_address", {})
        address_parts = [
            address_dict.get(k)
            for k in [
                "premises",
                "address_line_1",
                "locality",
                "region",
                "postal_code",
            ]
            if address_dict.get(k)
        ]
        registered_address = (
            ", ".join(address_parts) if address_parts else None
        )
        town = address_dict.get("locality")
        postcode = address_dict.get("postal_code")

        officers = self.get_officers(company_number)

        target_website = manual_website.strip() if manual_website else None
        discovery: Dict[str, Any] = {"confidence": "Manual", "reasons": ["entered by you"], "notes": []}
        if not target_website:
            discovery = self.auto_discover_website(
                company_name,
                location=town or postcode,
                company_number=company_number,
                postcode=postcode,
            )
            target_website = discovery.get("url")

        site_contacts = (
            self.scrape_contact_channels(target_website)
            if target_website
            else {"emails": [], "other_emails": [], "phones": [], "description": "",
                  "resolved_url": None, "pages_checked": []}
        )
        notes = list(discovery.get("notes", []))
        if getattr(self, "last_officer_error", None):
            notes.append(self.last_officer_error)
        if target_website and not site_contacts.get("pages_checked"):
            notes.append("Website didn't respond when scraping contacts")

        return ScrapedLead(
            company_name=company_name,
            company_number=company_number,
            sic_codes=ch_data.get("sic_codes", []),
            sector_guess=sector_name,
            registered_address=registered_address,
            website_url=site_contacts.get("resolved_url") or target_website,
            phones_found=site_contacts["phones"],
            emails_found=site_contacts["emails"],
            officers=officers,
            site_meta_description=site_contacts["description"],
            website_confidence=discovery.get("confidence") if target_website else None,
            website_reasons=discovery.get("reasons", []),
            discovery_notes=notes,
            other_emails=site_contacts.get("other_emails", []),
            pages_checked=site_contacts.get("pages_checked", []),
        )


# ==========================================
# 3. PITCH SYNTHESIZER & PDF BUILDER
# ==========================================


def sanitize_pdf_text(text: str) -> str:
    """Replaces Unicode bullets, smart quotes, and dashes with Latin-1 equivalents for FPDF."""
    if not text:
        return ""
    replacements = {
        "\u2022": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u00a0": " ",
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "—": "-",
        "–": "-",
        "•": "-",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", errors="replace").decode("latin-1")


# Companies House officer_role values, best decision-maker first.
# Secretaries and all "corporate-*" roles (companies, not people) are excluded.
DECISION_MAKER_ROLES = [
    "director",
    "llp-designated-member",
    "llp-member",
    "managing-officer",
    "member",
]

ROLE_LABELS = {
    "director": "Director",
    "llp-designated-member": "Designated Member (LLP)",
    "llp-member": "Member (LLP)",
    "managing-officer": "Managing Officer",
    "member": "Member",
    "secretary": "Company Secretary",
    "nominee-director": "Nominee Director",
}

NAME_TITLES = {"mr", "mrs", "ms", "miss", "dr", "sir", "dame", "prof", "professor", "lord", "lady", "rev"}


def format_role(raw_role: str) -> str:
    raw_role = (raw_role or "").strip().lower()
    return ROLE_LABELS.get(raw_role, raw_role.replace("-", " ").title() or "Officer")


def first_name_from_officer(raw_name: str) -> Optional[str]:
    """Companies House lists people as 'SURNAME, Forename Middle'.
    Returns the forename, e.g. 'BYWATER, Paul James' -> 'Paul'."""
    if not raw_name:
        return None
    if "," in raw_name:
        forenames = raw_name.split(",", 1)[1]
    else:
        forenames = raw_name  # Rare 'Paul BYWATER' style: first word is the forename
    for token in forenames.replace(".", " ").split():
        clean = re.sub(r"[^A-Za-z'\-]", "", token)
        if clean and clean.lower() not in NAME_TITLES and len(clean) > 1:
            return "-".join(p[:1].upper() + p[1:].lower() for p in clean.split("-"))
    return None


def pick_decision_maker(officers: List["OfficerInfo"]) -> Optional["OfficerInfo"]:
    """Chooses the most senior active person (directors first, longest-serving first)."""
    for wanted in DECISION_MAKER_ROLES:
        matches = [o for o in officers if o.raw_role == wanted]
        if matches:
            return sorted(matches, key=lambda o: o.appointed_on or "9999")[0]
    return None


GENERIC_EMAIL_PREFIXES = {
    "info", "information", "enquiries", "enquiry", "enq", "sales", "lettings", "letting",
    "rentals", "lets", "office", "admin", "administration", "contact", "contactus",
    "mail", "post", "reception", "frontdesk", "support", "help", "hello", "hi", "team",
    "accounts", "account", "finance", "billing", "invoices", "payments", "bookings",
    "booking", "appointments", "appts", "careers", "jobs", "recruitment", "hr",
    "marketing", "newsletter", "news", "press", "media", "privacy", "dpo", "data",
    "gdpr", "complaints", "feedback", "service", "services", "customerservice",
    "customerservices", "general", "manager", "management", "partners", "property",
    "properties", "valuations", "valuation", "maintenance", "repairs", "lettingsteam",
    "salesteam", "dental", "dentist", "surgery", "practice", "practicemanager",
    "clinic", "patients", "patient", "law", "legal", "conveyancing", "probate",
    "family", "tax", "payroll", "bookkeeping", "audit", "web", "webmaster", "website",
    "it", "tech", "office1", "branch", "new", "newbusiness", "referrals", "clients",
}


def first_name_from_email(email: str) -> Optional[str]:
    """'david.mann@x.co.uk' -> 'David'. Returns None for inboxes like info@ or accounts@."""
    prefix = email.split("@", 1)[0].lower()
    compact = re.sub(r"[^a-z]", "", prefix)
    if not compact or compact in GENERIC_EMAIL_PREFIXES:
        return None
    first = re.split(r"[._\-]", prefix)[0]
    first = re.sub(r"[^a-z]", "", first)
    # Must look like a first name: letters only, 3-12 chars, not a generic word
    if 3 <= len(first) <= 12 and first not in GENERIC_EMAIL_PREFIXES and first.isalpha():
        # 'dmann' style (initial + surname) can't be trusted as a first name
        has_separator = any(sep in prefix for sep in "._-")
        if not has_separator:
            if len(first) > 8:
                return None
            # Two leading consonants that rarely start a first name = initial + surname ('dmann', 'pbywater')
            vowels = set("aeiouy")
            ok_clusters = {"br", "ch", "cl", "cr", "dr", "fl", "fr", "gl", "gr", "kr",
                           "ph", "pr", "sc", "sh", "st", "th", "tr", "bl", "chr", "sk"}
            if first[0] not in vowels and first[1] not in vowels and first[:2] not in ok_clusters:
                return None
        return first.capitalize()
    return None


def pick_primary_email(lead: "ScrapedLead", first_name: Optional[str] = None) -> Optional[str]:
    """The best single email for the dossier: the contact's own inbox, else the main inbox."""
    if not lead.emails_found:
        return None
    if first_name:
        for em in lead.emails_found:
            if em.split("@", 1)[0].lower().startswith(first_name.lower()):
                return em
    for preferred in ("info", "enquiries", "hello", "contact", "office", "reception"):
        for em in lead.emails_found:
            if em.split("@", 1)[0].lower() == preferred:
                return em
    return lead.emails_found[0]


def infer_contact_name_and_role(
    lead: ScrapedLead, vertical_key: str
) -> Tuple[str, str]:
    """Smart contact resolver: extracts personal names from officers or email prefixes."""
    vert_cfg = VERTICAL_PRESETS.get(
        vertical_key, VERTICAL_PRESETS["Estate & Lettings Agents"]
    )

    # 1. Primary Officer match — only real people in decision-making roles
    officer = pick_decision_maker(lead.officers)
    if officer:
        first_name = first_name_from_officer(officer.name)
        if first_name:
            return first_name, officer.role

    # 2. Email Prefix Extraction (e.g. sarah@firm.co.uk or david.mann@firm.co.uk -> Sarah / David)
    for em in lead.emails_found:
        name_candidate = first_name_from_email(em)
        if name_candidate:
            return name_candidate, f"Direct Contact ({em})"

    # 3. Fallback to vertical-specific role
    return vert_cfg["fallback_greeting"], "Team / Branch Management"


# ------------------------------------------------------------------
# SY Communications brand & sector copy (email + overview PDF)
# ------------------------------------------------------------------

SENDER_COMPANY = "SY Communications"
SENDER_DEFAULTS = {
    "name": "",
    "title": "Business Solutions Consultant",
    "phone": "01743 667419",
    "email": "hello@sycomms.co.uk",
    "website": "www.sycomms.co.uk",
    "address": "Suite C, Jupiter House, Shrewsbury SY2 6LG",
}
BRAND_PURPLE = (31, 20, 80)       # #1f1450
BRAND_PURPLE_2 = (45, 31, 110)    # #2d1f6e
BRAND_TEAL = (0, 181, 163)        # #00b5a3
SWITCHOVER_LINE = (
    "With BT's analogue phone network switching off by January 2027, it's a good moment to"
    " move to a system that actually works with your software."
)

# Per-sector copy. Keys match VERTICAL_PRESETS.
SECTOR_COPY: Dict[str, Dict[str, Any]] = {
    "Estate & Lettings Agents": {
        "sector_plural": "estate and lettings agents",
        "subject": "Stop missing applicant calls at {company}",
        "pain": "Most agencies still ask who's calling, then search {crms} while the caller waits. And calls missed during viewings often go to the agent down the road.",
        "cta": "Worth a quick 15-minute demo? Or just reply with which system you use and how many staff take calls, and I'll send an indicative quote.",
        "challenges": [
            ("Calls missed during viewings", "Applicants who can't get through rarely leave a message; they ring the next agent."),
            ("No caller context", "Staff answer blind, then search the CRM while the landlord or tenant waits."),
            ("No record of what was agreed", "Call notes live in people's heads, not on the property or tenancy file."),
        ],
        "outcomes": [
            ("Screen-pop on every call", "The landlord, vendor or applicant record opens the moment the phone rings."),
            ("Click-to-dial from your CRM", "Call straight from the property, applicant or tenancy record. No retyping numbers."),
            ("Calls logged automatically", "Every call, duration and recording saved against the right record for compliance and disputes."),
            ("Missed-call recovery", "Missed calls are flagged instantly with the caller's record, so no lead goes cold."),
        ],
    },
    "Dental Practices": {
        "sector_plural": "dental practices",
        "subject": "Fewer missed patient calls at {company}",
        "pain": "Reception gets swamped at 8.30am, patients who can't get through don't always call back, and staff search {crms} on every call.",
        "cta": "Worth a quick 15-minute demo? Or just reply with which system you use and how many handsets you have, and I'll send a no-obligation quote.",
        "challenges": [
            ("Morning call peaks", "Reception is overwhelmed at opening and patients give up or go elsewhere."),
            ("Lost recalls and bookings", "Missed calls mean missed appointments and gaps in the diary."),
            ("Searching while the patient waits", "Staff look up records manually on every call."),
        ],
        "outcomes": [
            ("Patient screen-pop", "The patient's record appears on the reception screen as the phone rings."),
            ("Call queueing & callbacks", "Smart queues and messages manage the morning rush without losing callers."),
            ("Missed-call follow-up", "Every missed call is flagged so reception can ring back and protect recalls."),
            ("Compliant call recording", "Recordings stored securely and linked to the patient record."),
        ],
    },
    "Solicitors & Legal Practices": {
        "sector_plural": "law firms",
        "subject": "Calls logged straight to the matter at {company}",
        "pain": "Fee earners are rarely at their desk, clients expect to reach the right person first time, and phone time often never reaches the matter in {crms}.",
        "cta": "Worth a quick 15-minute demo? Or just reply with which system you run and roughly how many users, and I'll send an indicative quote.",
        "challenges": [
            ("Fee earners away from the desk", "Calls bounce around the office or go to voicemail."),
            ("Unrecorded billable time", "Phone time isn't captured against the matter, so it's never billed."),
            ("Multiple offices, multiple systems", "Branches that can't transfer calls between each other easily."),
        ],
        "outcomes": [
            ("Dial from the matter", "Click-to-call from the client or matter record in your case management system."),
            ("Softphone anywhere", "Fee earners take calls on laptop or mobile securely, on the firm's number."),
            ("Duration & recordings on file", "Call time and recordings logged against the matter for billing and compliance."),
            ("One system, every office", "Reception, fee earners and branches on one platform with simple transfers."),
        ],
    },
    "Accountants & Auditors": {
        "sector_plural": "accountancy practices",
        "subject": "Client calls logged automatically at {company}",
        "pain": "Around deadlines the phones don't stop, clients expect you to know who they are, and call time rarely gets captured in {crms}.",
        "cta": "Worth a quick 15-minute demo? Or just reply with your team size and practice software, and I'll send an indicative quote.",
        "challenges": [
            ("Deadline call surges", "January and year-end bring call spikes the team can't keep up with."),
            ("Unbilled advice time", "Quick calls add up but rarely make it onto a timesheet."),
            ("Hybrid teams", "Staff split between home and office struggle to transfer calls smoothly."),
        ],
        "outcomes": [
            ("Client identified on arrival", "The client's details pop up before you say hello."),
            ("Automatic call logging", "Calls logged against the client record, with duration for time tracking."),
            ("Desk to laptop in one tap", "Seamless transfers between desk phones and softphones for hybrid staff."),
            ("Lower fixed costs", "Line rental and call costs consolidated onto one cloud platform."),
        ],
    },
    "General Medical Clinics": {
        "sector_plural": "clinics",
        "subject": "Shorter phone queues for patients at {company}",
        "pain": "Peak-hour queues put pressure on the front desk, and staff often have to search {crms} before they can help.",
        "cta": "Worth a quick 15-minute demo? Or just reply with how many lines or handsets you run, and I'll send a no-obligation overview.",
        "challenges": [
            ("Peak-hour queues", "The phones spike at opening and patients abandon the call."),
            ("Triage without context", "Staff answer without the patient's details in front of them."),
            ("Sensitive conversations", "Calls need to be recorded and stored securely."),
        ],
        "outcomes": [
            ("Patient screen-pop", "The patient's record appears as the call arrives to speed up triage."),
            ("Queueing & callbacks", "Patients hear their queue position or get a callback instead of an engaged tone."),
            ("Secure call recording", "Encrypted recordings stored against the patient record."),
            ("Easy internal transfers", "Direct routes between reception, clinicians and admin."),
        ],
    },
}

EVERYTHING_WE_DO = [
    "Cloud phone systems & softphones",
    "Desk, DECT & headset hardware",
    "Business broadband & connectivity",
    "Business mobiles",
    "Networking & Wi-Fi",
    "CCTV, security & access control",
]


def friendly_company_name(legal_name: str) -> str:
    """'HART NEW HOMES (WALSALL) LIMITED' -> 'Hart New Homes (Walsall)'."""
    name = re.sub(r"\b(LIMITED|LTD\.?|PLC|LLP|L\.L\.P\.)\s*$", "", legal_name.strip(), flags=re.I).strip(" ,.")
    if name.isupper():
        name = " ".join(
            w if (w in {"&", "UK"} or (len(w) <= 3 and not any(c in "AEIOU" for c in w) and w.isalpha()))
            else w.title()
            for w in name.split()
        )
    return name.replace(" And ", " and ").replace(" Of ", " of ").replace(" The ", " the ")


def get_sender() -> Dict[str, str]:
    sender = dict(SENDER_DEFAULTS)
    sender.update({k: v for k, v in st.session_state.get("sender_profile", {}).items() if v})
    return sender


def build_signature(sender: Dict[str, str]) -> str:
    lines = ["Kind regards,"]
    if sender.get("name"):
        lines.append("")
        lines.append(sender["name"])
        if sender.get("title"):
            lines.append(sender["title"])
    lines.append(SENDER_COMPANY)
    contact = " | ".join(x for x in (sender.get("phone"), sender.get("email")) if x)
    if contact:
        lines.append(contact)
    if sender.get("website"):
        lines.append(sender["website"])
    return "\n".join(lines)


def build_email_subject(lead: ScrapedLead, vertical_key: str) -> str:
    copy = SECTOR_COPY.get(vertical_key, SECTOR_COPY["Estate & Lettings Agents"])
    crms = VERTICAL_PRESETS.get(vertical_key, VERTICAL_PRESETS["Estate & Lettings Agents"])["crms"]
    return copy["subject"].format(company=friendly_company_name(lead.company_name), crm1=crms[0])


def build_email_pitch(
    lead: ScrapedLead,
    vertical_key: str,
    include_attachment_line: bool = True,
    include_switchover: bool = True,
) -> str:
    config = VERTICAL_PRESETS.get(vertical_key, VERTICAL_PRESETS["Estate & Lettings Agents"])
    copy = SECTOR_COPY.get(vertical_key, SECTOR_COPY["Estate & Lettings Agents"])
    sender = get_sender()
    first_name, _ = infer_contact_name_and_role(lead, vertical_key)
    greeting_name = first_name if first_name != config["fallback_greeting"] else "there"
    company = friendly_company_name(lead.company_name)
    crms = config["crms"]
    crms_str = ", ".join(crms[:2]) + f" or {crms[2]}" if len(crms) >= 3 else " or ".join(crms)

    who = f"I'm {sender['name']} from {SENDER_COMPANY}" if sender.get("name") else f"I'm getting in touch from {SENDER_COMPANY}"
    bullets = "\n".join(f"- {title}" for title, _ in copy["outcomes"][:4])

    parts = [
        f"Hi {greeting_name},",
        f"{who}. We help {copy['sector_plural']} like {company} connect their phones to the software they already use.",
        copy["pain"].format(crms=crms_str),
        "We connect your phones to whichever system you use, so you get:",
        bullets,
    ]
    if include_switchover:
        parts.append(SWITCHOVER_LINE)
    if include_attachment_line:
        parts.append(
            "I've attached a one-page overview of how it works."
        )
    parts.append(copy["cta"])
    parts.append(build_signature(sender))
    parts.append(
        "P.S. If this isn't relevant, just reply \"no thanks\" and I won't get in touch again."
    )
    return "\n\n".join(parts)


def _email_body_html(body: str) -> str:
    """Turns the plain-text email into simple, clean HTML (paragraphs, bullet list, signature)."""
    blocks, out = [b for b in body.replace("\r\n", "\n").split("\n\n")], []
    for block in blocks:
        lines = [l for l in block.split("\n") if l.strip() != ""] or [""]
        if all(l.lstrip().startswith("- ") for l in lines):
            items = "".join(f"<li>{html_lib.escape(l.lstrip()[2:])}</li>" for l in lines)
            out.append(f'<ul style="margin:0 0 14px 0;padding-left:20px">{items}</ul>')
        else:
            text = "<br>".join(html_lib.escape(l) for l in block.split("\n"))
            style = "margin:0 0 14px 0"
            if block.startswith("P.S."):
                style += ";color:#6b7280;font-size:12px"
            out.append(f'<p style="{style}">{text}</p>')
    return (
        '<html><body style="font-family:Calibri,Arial,sans-serif;font-size:14px;line-height:1.45;color:#1f2937">'
        + "".join(out) + "</body></html>"
    )


def build_eml_draft(
    to: str,
    subject: str,
    body: str,
    attachments: Optional[List[Tuple[str, bytes]]] = None,
) -> bytes:
    """A ready-to-send email draft (.eml) with attachments.

    Outlook for Windows opens it as an unsent draft (thanks to the X-Unsent header),
    with the To, Subject, formatted body and PDF already in place.
    """
    msg = EmailMessage()
    if to:
        msg["To"] = to
    msg["Subject"] = subject or ""
    msg["Date"] = formatdate(localtime=True)
    msg["X-Unsent"] = "1"  # Tells Outlook to open this as a new draft, not a received email
    msg.set_content(body.replace("\r\n", "\n"))
    msg.add_alternative(_email_body_html(body), subtype="html")
    for filename, data in attachments or []:
        msg.add_attachment(data, maintype="application", subtype="pdf", filename=filename)
    return msg.as_bytes()


def build_mailto(to: str, subject: str, body: str) -> str:
    """mailto: link that opens the user's default email app with everything filled in."""
    body_crlf = body.replace("\r\n", "\n").replace("\n", "\r\n")
    return (
        f"mailto:{quote(to or '', safe='@.+-_')}"
        f"?subject={quote(subject or '', safe='')}"
        f"&body={quote(body_crlf, safe='')}"
    )



# ------------------------------------------------------------------
# SY Communications sector overview (the "About us" email attachment)
# ------------------------------------------------------------------


def _box(pdf: FPDF, x: float, y: float, w: float, h: float, style: str = "F", radius: float = 2.5) -> None:
    try:
        pdf.rect(x, y, w, h, style=style, round_corners=True, corner_radius=radius)
    except TypeError:  # Older fpdf2 without rounded corners
        pdf.rect(x, y, w, h, style=style)


def create_sector_overview_pdf(lead: Optional[ScrapedLead], vertical_key: str) -> bytes:
    """One-page, branded SY Communications solutions overview, personalised to the prospect."""
    copy = SECTOR_COPY.get(vertical_key, SECTOR_COPY["Estate & Lettings Agents"])
    cfg = VERTICAL_PRESETS.get(vertical_key, VERTICAL_PRESETS["Estate & Lettings Agents"])
    sender = get_sender()
    T = sanitize_pdf_text
    purple, purple2, teal = BRAND_PURPLE, BRAND_PURPLE_2, BRAND_TEAL
    ink, grey, light = (30, 30, 46), (95, 100, 120), (244, 243, 250)

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(14, 14, 14)
    pdf.add_page()
    W = 210
    L, R = 14, 196
    CW = R - L

    # ---------- Header band ----------
    pdf.set_fill_color(*purple)
    pdf.rect(0, 0, W, 50, "F")
    pdf.set_fill_color(*purple2)
    pdf.rect(0, 46, W, 4, "F")
    pdf.set_fill_color(*teal)
    pdf.rect(0, 50, W, 1.2, "F")
    # Logo mark: teal circle with 'SY'
    pdf.set_fill_color(*teal)
    pdf.ellipse(L, 13, 14, 14, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_xy(L, 17.5)
    pdf.cell(14, 5, "SY", align="C")
    pdf.set_xy(L + 18, 13)
    pdf.set_font("Helvetica", "B", 17)
    pdf.cell(100, 8, "SY Communications")
    pdf.set_xy(L + 18, 21)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(190, 184, 230)
    pdf.cell(100, 5, "Business telecoms, connectivity & security")
    pdf.set_xy(L, 31)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(255, 255, 255)
    pdf.multi_cell(108, 6, T(f"Phone systems built for {copy['sector_plural']}"), align="L")
    # Prepared-for panel
    if lead:
        pdf.set_fill_color(*purple2)
        _box(pdf, 128, 11, 68, 26)
        pdf.set_xy(132, 14)
        pdf.set_font("Helvetica", "B", 6.5)
        pdf.set_text_color(*teal)
        pdf.cell(60, 4, "PREPARED FOR")
        pdf.set_xy(132, 19)
        pdf.set_font("Helvetica", "B", 10.5)
        pdf.set_text_color(255, 255, 255)
        pdf.multi_cell(61, 4.6, T(friendly_company_name(lead.company_name)[:60]), align="L")
        pdf.set_xy(132, 30.5)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(190, 184, 230)
        pdf.cell(60, 4, T(pd.Timestamp.now().strftime("%B %Y")))

    # ---------- Intro ----------
    crms = cfg["crms"]
    y = 58
    pdf.set_xy(L, y)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*ink)
    pdf.multi_cell(
        CW, 5.2,
        T(
            f"We connect your phone system directly to {', '.join(crms[:-1])} and {crms[-1]}, so every call"
            " arrives with context, gets logged automatically and never slips through the cracks."
        ),
        align="L",
    )

    def heading(text: str, yy: float) -> float:
        pdf.set_xy(L, yy)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*teal)
        pdf.cell(CW, 4, text.upper())
        pdf.set_draw_color(*teal)
        pdf.set_line_width(0.5)
        pdf.line(L, yy + 5.2, L + 10, yy + 5.2)
        return yy + 8

    # ---------- The challenge (3 cards) ----------
    y = heading("The challenge", pdf.get_y() + 4)
    gap = 4
    cw3 = (CW - 2 * gap) / 3
    for i, (title, desc) in enumerate(copy["challenges"][:3]):
        x = L + i * (cw3 + gap)
        pdf.set_fill_color(*light)
        _box(pdf, x, y, cw3, 24)
        pdf.set_xy(x + 4, y + 3.5)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*purple)
        pdf.multi_cell(cw3 - 8, 4.4, T(title), align="L")
        pdf.set_xy(x + 4, pdf.get_y() + 1)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*grey)
        pdf.multi_cell(cw3 - 8, 3.9, T(desc), align="L")
    y += 24 + 5

    # ---------- How we solve it ----------
    y = heading("How we solve it", y)
    pdf.set_xy(L, y)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*grey)
    pdf.cell(22, 6, "Integrates with:")
    x = L + 23
    pdf.set_font("Helvetica", "B", 8)
    for crm in crms:
        w = pdf.get_string_width(T(crm)) + 7
        pdf.set_draw_color(*teal)
        pdf.set_line_width(0.35)
        pdf.set_text_color(*purple)
        _box(pdf, x, y + 0.5, w, 5.2, style="D", radius=2.6)
        pdf.set_xy(x, y + 0.5)
        pdf.cell(w, 5.2, T(crm), align="C")
        x += w + 2.5
    y += 10
    cw2 = (CW - gap) / 2
    for i, (title, desc) in enumerate(copy["outcomes"][:4]):
        col, row = i % 2, i // 2
        x = L + col * (cw2 + gap)
        yy = y + row * 17
        pdf.set_fill_color(*teal)
        pdf.ellipse(x, yy + 0.5, 7, 7, "F")
        pdf.set_xy(x, yy + 1.8)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(7, 4.4, str(i + 1), align="C")
        pdf.set_xy(x + 10, yy)
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(*ink)
        pdf.cell(cw2 - 10, 5, T(title))
        pdf.set_xy(x + 10, yy + 5.5)
        pdf.set_font("Helvetica", "", 8.2)
        pdf.set_text_color(*grey)
        pdf.multi_cell(cw2 - 12, 4, T(desc), align="L")
    y += 2 * 17 + 1

    # ---------- Switchover callout ----------
    pdf.set_fill_color(230, 247, 245)
    _box(pdf, L, y, CW, 19)
    pdf.set_fill_color(*teal)
    pdf.rect(L, y, 1.6, 19, "F")
    pdf.set_xy(L + 6, y + 3)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.set_text_color(*purple)
    pdf.cell(CW - 10, 5, "The analogue switch-off is coming: January 2027")
    pdf.set_xy(L + 6, y + 8.5)
    pdf.set_font("Helvetica", "", 8.2)
    pdf.set_text_color(*grey)
    pdf.multi_cell(
        CW - 12, 4,
        "BT is retiring the traditional phone network. If you still rely on analogue or ISDN lines, moving now"
        " means you choose the timing, and you upgrade to a system that works with your software.",
        align="L",
    )
    y += 19 + 5

    # ---------- One partner + Why us (two columns) ----------
    y0 = y
    heading("One partner for your technology", y)
    yy = y + 8
    for i, item in enumerate(EVERYTHING_WE_DO):
        pdf.set_fill_color(*teal)
        pdf.ellipse(L, yy + i * 6 + 1.6, 2, 2, "F")
        pdf.set_xy(L + 4, yy + i * 6)
        pdf.set_font("Helvetica", "", 8.3)
        pdf.set_text_color(*ink)
        pdf.cell(80, 5, T(item))

    xw = L + CW / 2 + 4
    pdf.set_xy(xw, y0)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*teal)
    pdf.cell(80, 4, "WHY SY COMMUNICATIONS")
    pdf.set_draw_color(*teal)
    pdf.line(xw, y0 + 5.2, xw + 10, y0 + 5.2)
    why = [
        ("Local to you", "A Shrewsbury-based team you can actually speak to."),
        ("One point of contact", "From first survey through installation and aftercare."),
        ("Built around your software", "We set up the integration around how your team works."),
        ("Clear, no-obligation quotes", "Straightforward pricing before you commit to anything."),
    ]
    yy = y0 + 8
    for title, desc in why:
        pdf.set_xy(xw, yy)
        pdf.set_font("Helvetica", "B", 8.3)
        pdf.set_text_color(*ink)
        pdf.cell(80, 4.2, T(title))
        pdf.set_xy(xw, yy + 4.2)
        pdf.set_font("Helvetica", "", 7.8)
        pdf.set_text_color(*grey)
        pdf.cell(80, 4, T(desc))
        yy += 9
    y = max(yy, y0 + 8 + 6 * 6) + 3

    # ---------- Next steps ----------
    if y > 250:  # Safety: never collide with the footer
        y = 250
    y = heading("Next steps", y)
    steps = [
        ("15-minute call", "A quick chat about your team, lines and software."),
        ("Free review", "We look at your current setup and contracts."),
        ("Tailored quote", "A clear, no-obligation proposal."),
    ]
    for i, (title, desc) in enumerate(steps):
        x = L + i * (cw3 + gap)
        pdf.set_fill_color(*light)
        _box(pdf, x, y, cw3, 16)
        pdf.set_xy(x + 4, y + 3)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*purple)
        pdf.cell(cw3 - 8, 4.5, T(f"{i + 1}. {title}"))
        pdf.set_xy(x + 4, y + 8.3)
        pdf.set_font("Helvetica", "", 7.6)
        pdf.set_text_color(*grey)
        pdf.multi_cell(cw3 - 8, 3.6, T(desc), align="L")

    # ---------- Footer band ----------
    pdf.set_fill_color(*purple)
    pdf.rect(0, 272, W, 25, "F")
    pdf.set_fill_color(*teal)
    pdf.rect(0, 272, W, 1.2, "F")
    pdf.set_xy(L, 277)
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(255, 255, 255)
    contact_name = sender.get("name") or "Talk to our team"
    pdf.cell(90, 5, T(contact_name + (f"  |  {sender['title']}" if sender.get("name") and sender.get("title") else "")))
    pdf.set_xy(L, 283)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(190, 184, 230)
    pdf.cell(
        CW, 5,
        T("  |  ".join(x for x in (sender.get("phone"), sender.get("email"), sender.get("website")) if x)),
    )
    pdf.set_xy(L, 288.5)
    pdf.set_font("Helvetica", "", 7.2)
    pdf.cell(CW, 4, T(sender.get("address", "")))

    out = pdf.output()
    return bytes(out) if not isinstance(out, str) else out.encode("latin-1", errors="replace")


class LeadDossierPDF(FPDF):

    def header(self):
        self.set_fill_color(30, 41, 59)  # Dark slate header bar
        self.rect(0, 0, 210, 14, "F")
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 9)
        self.set_xy(12, 3)
        self.cell(
            0,
            8,
            "SY COMMUNICATIONS | CONFIDENTIAL LEAD RECORD",
            ln=0,
        )
        self.ln(14)

    def footer(self):
        self.set_y(-10)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(148, 163, 184)
        self.cell(
            0,
            6,
            "Confidential lead record - Generated for internal sales review",
            0,
            0,
            "C",
        )


def create_pdf_dossier(
    lead: ScrapedLead,
    vertical_name: str,
    pitch_text: str,
    target_crms: List[str],
) -> bytes:
    pdf = LeadDossierPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    contact_name, contact_role = infer_contact_name_and_role(
        lead, vertical_name
    )

    # 1. PRIMARY CONTACT CARD
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 4, "PRIMARY CONTACT", ln=True)

    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, sanitize_pdf_text(contact_name), ln=True)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(71, 85, 105)
    primary_email = pick_primary_email(lead, contact_name) or "Email TBD"
    primary_phone = (
        lead.phones_found[0] if lead.phones_found else "Phone TBD"
    )
    contact_sub = f"{contact_role} - {primary_email} - {primary_phone}"
    pdf.cell(0, 5, sanitize_pdf_text(contact_sub), ln=True)

    pdf.ln(3)

    # 2. FIRM CARD
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 4, "TARGET FIRM", ln=True)

    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, sanitize_pdf_text(lead.company_name[:55]), ln=True)

    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(71, 85, 105)
    addr_line = lead.registered_address or "Address not listed"
    site_line = lead.website_url or "Website not specified"
    pdf.cell(
        0,
        5,
        sanitize_pdf_text(
            f"{vertical_name} - {addr_line[:65]} - Company"
            f" #{lead.company_number or 'N/A'}"
        ),
        ln=True,
    )
    pdf.cell(0, 5, sanitize_pdf_text(f"Domain: {site_line}"), ln=True)

    if lead.site_meta_description:
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(100, 116, 139)
        pdf.multi_cell(
            190, 4, sanitize_pdf_text(f'"{lead.site_meta_description[:200]}"')
        )

    pdf.ln(2)
    pdf.set_draw_color(226, 232, 240)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # 3. CORE INTEGRATION HOOK
    vert_cfg = VERTICAL_PRESETS.get(
        vertical_name, VERTICAL_PRESETS["Estate & Lettings Agents"]
    )
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 4, "SYSTEM INTEGRATION HOOK", ln=True)

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(2, 132, 199)  # Highlighted blue
    crms_headline = f"{vert_cfg['primary_hook']} (confirm which)"
    pdf.cell(0, 5, sanitize_pdf_text(crms_headline), ln=True)

    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(51, 65, 85)
    for bullet in vert_cfg["pitch_bullets"]:
        pdf.cell(0, 4.5, sanitize_pdf_text(f"- {bullet}"), ln=True)

    pdf.ln(3)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # 4. TAILORED OUTREACH EMAIL DRAFT
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 4, "READY-TO-SEND OUTREACH EMAIL COPY", ln=True)

    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(203, 213, 225)
    pdf.set_font("Courier", "", 8)
    pdf.set_text_color(15, 23, 42)

    clean_pitch = sanitize_pdf_text(pitch_text)
    pdf.multi_cell(190, 4.2, clean_pitch, border=1, fill=True)

    output = pdf.output()
    if isinstance(output, str):
        return output.encode("latin-1", errors="replace")
    elif isinstance(output, bytearray):
        return bytes(output)
    return output


# ==========================================
# 3b. SENT LOG (remembers who's been emailed, across sessions)
# ==========================================


def _secret_value(key: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(key, default) or default)
    except Exception:
        return default


class SentLog:
    """Stores {company_number: record} of firms that have been emailed.

    Permanent: a JSON file in a private GitHub repo (set GITHUB_TOKEN + GITHUB_REPO in Secrets).
    Fallback: a local file, which Streamlit Cloud wipes whenever the app restarts or redeploys.
    """

    def __init__(self) -> None:
        self.token = _secret_value("GITHUB_TOKEN")
        self.repo = _secret_value("GITHUB_REPO")  # e.g. "sammyatt2010-hub/prospect-engine-data"
        self.branch = _secret_value("GITHUB_BRANCH", "main")
        self.path = _secret_value("GITHUB_LOG_PATH", "sent_log.json")
        self.backend = "github" if (self.token and self.repo) else "local"
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            base_dir = os.getcwd()
        self.local_path = os.path.join(base_dir, ".sent_log.json")
        self.last_error: Optional[str] = None

    # ---------- GitHub backend ----------
    def _url(self) -> str:
        return f"https://api.github.com/repos/{self.repo}/contents/{self.path}"

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _gh_read(self) -> Tuple[Dict[str, Any], Optional[str]]:
        resp = requests.get(self._url(), headers=self._headers(), params={"ref": self.branch}, timeout=10)
        if resp.status_code == 404:
            return {}, None  # File doesn't exist yet; first write creates it
        if resp.status_code != 200:
            raise RuntimeError(self._describe(resp.status_code))
        payload = resp.json()
        content = base64.b64decode(payload.get("content", "") or b"").decode("utf-8") or "{}"
        return json.loads(content), payload.get("sha")

    def _gh_write(self, data: Dict[str, Any], sha: Optional[str], message: str) -> int:
        body: Dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(json.dumps(data, indent=2, sort_keys=True).encode("utf-8")).decode("ascii"),
            "branch": self.branch,
        }
        if sha:
            body["sha"] = sha
        resp = requests.put(self._url(), headers=self._headers(), json=body, timeout=12)
        return resp.status_code

    @staticmethod
    def _describe(code: int) -> str:
        return {
            401: "GitHub rejected the token (401). Check GITHUB_TOKEN in Secrets.",
            403: "GitHub token lacks permission (403). It needs Contents: Read and write on the repo.",
            404: "GitHub repo not found (404). Check GITHUB_REPO in Secrets.",
        }.get(code, f"GitHub returned an error ({code}).")

    # ---------- Local backend ----------
    def _local_read(self) -> Dict[str, Any]:
        try:
            with open(self.local_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _local_write(self, data: Dict[str, Any]) -> None:
        tmp = self.local_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
        os.replace(tmp, self.local_path)

    # ---------- Public API ----------
    def load(self) -> Dict[str, Any]:
        self.last_error = None
        try:
            return self._gh_read()[0] if self.backend == "github" else self._local_read()
        except Exception as exc:  # Never let the log break the app
            self.last_error = str(exc) if isinstance(exc, RuntimeError) else f"Couldn't load sent log ({exc.__class__.__name__})."
            return {}

    def apply(self, changes: Dict[str, Optional[Dict[str, Any]]], message: str) -> Dict[str, Any]:
        """Applies {company_number: record or None (= un-mark)} and returns the latest full log.
        Re-reads before writing, so two people using the app at once don't overwrite each other."""
        self.last_error = None

        def merge(data: Dict[str, Any]) -> Dict[str, Any]:
            for key, record in changes.items():
                if record is None:
                    data.pop(key, None)
                else:
                    data[key] = record
            return data

        if self.backend == "local":
            data = merge(self._local_read())
            self._local_write(data)
            return data

        for _attempt in range(3):
            data, sha = self._gh_read()
            data = merge(data)
            status = self._gh_write(data, sha, message)
            if status in (200, 201):
                return data
            if status not in (409, 422):  # 409/422 = someone else saved first; re-read and retry
                raise RuntimeError(self._describe(status))
        raise RuntimeError("GitHub was busy saving the sent log. Please try again.")


def now_uk() -> datetime:
    try:
        return datetime.now(ZoneInfo("Europe/London"))
    except Exception:
        return datetime.now()


def sent_label(record: Optional[Dict[str, Any]]) -> str:
    """'✓ 25 Sep' for the tables."""
    if not record:
        return ""
    try:
        return "✓ " + datetime.fromisoformat(record.get("sent_at", "")).strftime("%d %b").lstrip("0")
    except ValueError:
        return "✓ Sent"


# ------------------------------------------------------------------
# Batch export: a zip of ready-to-send Outlook drafts
# ------------------------------------------------------------------


def draft_filename_part(company_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", friendly_company_name(company_name)).strip("_") or "firm"


def build_lead_list_csv(items: List[Dict[str, Any]], log: Dict[str, Any]) -> bytes:
    """Spreadsheet of every selected firm, including those with no email (for phoning)."""
    rows = []
    for item in items:
        lead: ScrapedLead = item["lead"]
        cn = lead.company_number or ""
        contact, role = infer_contact_name_and_role(lead, item["vertical"])
        directors = [display_officer_name(o.name) for o in lead.officers if o.raw_role in DECISION_MAKER_ROLES]
        rec = log.get(cn)
        rows.append({
            "Status": (f"{rec.get('status') or 'Emailed'} {sent_label(rec)[2:]}" if rec
                       else "Ready to email" if item.get("to") else "No email"),
            "Firm": lead.company_name,
            "Company number": cn,
            "Sector": item["vertical"],
            "Contact": contact,
            "Contact role": role,
            "Email": item.get("to", ""),
            "Other emails": "; ".join(e for e in lead.emails_found if e != item.get("to")),
            "Phone": (lead.phones_found or [""])[0],
            "Other phones": "; ".join(lead.phones_found[1:]),
            "Directors": "; ".join(directors),
            "Website": lead.website_url or "",
            "Website match": (lead.website_confidence or "") if lead.website_url else "Not found",
            "Registered office": lead.registered_address or "",
            "Email subject": item.get("subject", "") if item.get("to") else "",
        })
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")  # utf-8-sig = opens cleanly in Excel


def build_drafts_zip(items: List[Dict[str, Any]], attach_overview: bool) -> Tuple[bytes, int, List[str]]:
    """items: queue items with lead/vertical/to/subject/body. Returns (zip_bytes, drafts_written, skipped_names)."""
    buf = io.BytesIO()
    written, skipped = 0, []
    summary = io.StringIO()
    summary.write("Firm,Company number,To,Contact,Subject,Website,Website match\n")
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in items:
            lead: ScrapedLead = item["lead"]
            if not item.get("to"):
                skipped.append(friendly_company_name(lead.company_name))
                continue
            written += 1
            part = draft_filename_part(lead.company_name)
            attachments = None
            if attach_overview:
                sector_slug = re.sub(
                    r"[^A-Za-z0-9]+", "_",
                    SECTOR_COPY.get(item["vertical"], {}).get("sector_plural", "sector"),
                ).strip("_")
                attachments = [(
                    f"SY_Communications_{sector_slug}_overview_{part}.pdf",
                    create_sector_overview_pdf(lead, item["vertical"]),
                )]
            eml = build_eml_draft(item["to"], item["subject"], item["body"], attachments=attachments)
            zf.writestr(f"{written:02d}_{part}.eml", eml)
            contact, _ = infer_contact_name_and_role(lead, item["vertical"])
            row = [lead.company_name, lead.company_number or "", item["to"], contact,
                   item["subject"], lead.website_url or "", lead.website_confidence or "Not found"]
            summary.write(",".join('"' + str(v).replace('"', '""') + '"' for v in row) + "\n")
        zf.writestr("_summary.csv", summary.getvalue())
    return buf.getvalue(), written, skipped


# ==========================================
# 4. STREAMLIT APPLICATION
# ==========================================

def render_leads_table(df: pd.DataFrame, key: str):
    """Selectable company table with tidy columns. Works on old and new Streamlit versions."""
    column_config = {
        "Company Name": st.column_config.TextColumn("Company Name", width=200),
        "Contacted": st.column_config.TextColumn("Contacted", width=78, help="Already emailed (from the sent log)"),
        "Company Number": st.column_config.TextColumn("Co. #", width=74),
        "Incorporated": st.column_config.DateColumn("Since", format="MMM YYYY", width=78),
        "Town": st.column_config.TextColumn("Town", width=95),
        "Companies House": st.column_config.LinkColumn(
            "Registry", display_text="View ↗", width=62,
            help="Opens the company's Companies House page in a new tab",
        ),
    }
    column_order = [c for c in column_config if c in df.columns]
    table_height = min(38 + 35 * len(df), 420)  # Grows with rows, scrolls after ~11
    common = dict(
        hide_index=True,
        selection_mode="multi-row",
        on_select="rerun",
        column_config=column_config,
        column_order=column_order,
        height=table_height,
        key=key,
    )
    try:
        return st.dataframe(df, width="stretch", **common)  # Streamlit 1.46+
    except Exception:
        return st.dataframe(df, use_container_width=True, **common)  # Older Streamlit


st.set_page_config(
    page_title=f"{APP_NAME} · Prospect Discovery & Dossiers",
    page_icon="🎯",
    layout="wide",
)
inject_css()

for _k, _v in {"stat_searches": 0, "stat_firms": 0, "stat_dossiers": 0}.items():
    st.session_state.setdefault(_k, 0)

hero_slot = st.empty()  # Filled at the end so the progress stepper reflects this run's actions
MAX_BATCH = 25
SENT_LOG = SentLog()
for _k, _v in {"opt_attach": True, "opt_switch": True, "queue_editor_ver": 0, "sent_log_ver": 0}.items():
    st.session_state.setdefault(_k, _v)


def get_sent_log() -> Dict[str, Any]:
    """Loaded once per session; refreshed after every change (and by the sidebar Refresh button)."""
    if "sent_log_data" not in st.session_state:
        st.session_state["sent_log_data"] = SENT_LOG.load()
    return st.session_state["sent_log_data"]


def bump_queue_editor() -> None:
    st.session_state["queue_editor_ver"] = st.session_state.get("queue_editor_ver", 0) + 1


def record_sent(changes: Dict[str, Optional[Dict[str, Any]]]) -> None:
    """Saves sent ticks/unticks to the permanent log and refreshes every view of it."""
    local = dict(get_sent_log())
    try:
        n_on = sum(1 for v in changes.values() if v)
        latest = SENT_LOG.apply(changes, f"Prospect Engine: {n_on} marked sent, {len(changes) - n_on} unmarked")
        st.session_state["sent_log_data"] = latest
    except Exception as exc:
        for key, rec in changes.items():  # Keep this session correct even if saving failed
            if rec is None:
                local.pop(key, None)
            else:
                local[key] = rec
        st.session_state["sent_log_data"] = local
        st.session_state["sent_log_error"] = str(exc) if isinstance(exc, RuntimeError) else "Couldn't save the sent log."
    st.session_state["sent_log_ver"] = st.session_state.get("sent_log_ver", 0) + 1
    bump_queue_editor()


def sent_record(item: Dict[str, Any]) -> Dict[str, Any]:
    lead: ScrapedLead = item["lead"]
    return {
        "company_name": lead.company_name,
        "to": item.get("to", ""),
        "contact": infer_contact_name_and_role(lead, item["vertical"])[0],
        "vertical": item["vertical"],
        "subject": item.get("subject", ""),
        "sent_at": now_uk().isoformat(timespec="seconds"),
        "sent_by": get_sender().get("name", ""),
        "status": "Emailed" if item.get("to") else "Handled",
    }


def add_to_queue(lead: ScrapedLead, vertical: str) -> None:
    queue = st.session_state.setdefault("queue", {})
    order = st.session_state.setdefault("queue_order", [])
    cn = lead.company_number or lead.company_name
    contact, _ = infer_contact_name_and_role(lead, vertical)
    queue[cn] = {
        "lead": lead,
        "vertical": vertical,
        "include": True,
        "to": pick_primary_email(lead, contact) or "",
        "to_ver": queue.get(cn, {}).get("to_ver", 0) + 1,
        "subject": None,
        "body": None,
        "sig": None,
    }
    if cn not in order:
        order.append(cn)
    bump_queue_editor()


def ensure_draft(item: Dict[str, Any]) -> None:
    """(Re)builds a firm's subject/body when first needed or when options/signature change."""
    sig = (item["vertical"], st.session_state["opt_attach"], st.session_state["opt_switch"],
           tuple(sorted(get_sender().items())))
    if item.get("sig") != sig or item.get("body") is None:
        item["subject"] = build_email_subject(item["lead"], item["vertical"])
        item["body"] = build_email_pitch(
            item["lead"], item["vertical"],
            include_attachment_line=st.session_state["opt_attach"],
            include_switchover=st.session_state["opt_switch"],
        )
        item["sig"] = sig



try:
    secret_ch_key = st.secrets.get("COMPANIES_HOUSE_KEY", "")
except Exception:
    secret_ch_key = ""


def columns(spec, **kwargs):
    """st.columns with bottom alignment where supported (Streamlit 1.36+)."""
    try:
        return st.columns(spec, vertical_alignment="bottom", **kwargs)
    except TypeError:
        return st.columns(spec, **kwargs)


# ---------------- Sidebar ----------------
with st.sidebar:
    render_html(
        f'<div class="pe-brand"><div class="pe-logo">{icon("target", 22, 2.2)}</div>'
        f'<div><div class="n">{APP_NAME}</div><div class="s">{APP_TAGLINE}</div></div></div>'
    )
    render_html('<div class="pe-side-h">Connections</div>')
    if secret_ch_key:
        # Key stays server-side: never placed in a widget, so never sent to the browser.
        ch_api_key = secret_ch_key
    else:
        ch_api_key = st.text_input(
            "Companies House API key",
            type="password",
            help=(
                "Not found in Secrets. Paste a key for this session, or add"
                " COMPANIES_HOUSE_KEY to Streamlit Secrets."
            ),
        )
    ch_state = ('ok">Connected' if secret_ch_key else ('idle">Session key' if ch_api_key else 'off">No key'))
    render_html(
        f'<div class="pe-status">Companies House<span class="st {ch_state}</span></div>'
        '<div class="pe-status">Web discovery<span class="st ok">Ready</span></div>'
        '<div class="pe-status">PDF dossiers<span class="st ok">Ready</span></div>'
    )
    get_sent_log()
    if SENT_LOG.last_error or st.session_state.get("sent_log_error"):
        log_state = 'off">Error'
    elif SENT_LOG.backend == "github":
        log_state = 'ok">Saved to GitHub'
    else:
        log_state = 'idle">Temporary'
    render_html(f'<div class="pe-status">Sent log<span class="st {log_state}</span></div>')
    if SENT_LOG.last_error or st.session_state.get("sent_log_error"):
        st.caption("⚠️ " + (st.session_state.pop("sent_log_error", None) or SENT_LOG.last_error or ""))
    elif SENT_LOG.backend == "local":
        st.caption("Sent ticks reset when the app restarts. Add GITHUB_TOKEN & GITHUB_REPO to Secrets to keep them permanently.")
    if st.button("↻ Refresh sent log", **FULL_WIDTH, help="Pick up ticks made by colleagues since you opened the app."):
        st.session_state.pop("sent_log_data", None)
        st.session_state["sent_log_ver"] = st.session_state.get("sent_log_ver", 0) + 1
        bump_queue_editor()
        st.rerun()
    render_html('<div class="pe-side-h">This session</div>')
    sidebar_stats_slot = st.empty()
    render_html('<div class="pe-side-h">Your email signature</div>')
    with st.expander("Signature details", expanded=not st.session_state.get("sender_profile", {}).get("name")):
        def _secret(key: str, default: str) -> str:
            try:
                return str(st.secrets.get(key, default))
            except Exception:
                return default
        prof = st.session_state.setdefault("sender_profile", {
            "name": _secret("SENDER_NAME", ""),
            "title": _secret("SENDER_TITLE", SENDER_DEFAULTS["title"]),
            "phone": _secret("SENDER_PHONE", SENDER_DEFAULTS["phone"]),
            "email": _secret("SENDER_EMAIL", SENDER_DEFAULTS["email"]),
        })
        prof["name"] = st.text_input("Your name", value=prof.get("name", ""), placeholder="e.g. Sam")
        prof["title"] = st.text_input("Job title", value=prof.get("title", ""))
        prof["phone"] = st.text_input("Direct phone", value=prof.get("phone", ""))
        prof["email"] = st.text_input("Your email", value=prof.get("email", ""))
        st.session_state["sender_profile"] = prof
    render_html('<div class="pe-side-h">Account</div>')
    if st.button("Log out", **FULL_WIDTH):
        st.session_state["password_correct"] = False
        st.rerun()


col_left, col_right = st.columns([1.08, 0.92], gap="large")

# ---------------- Left: Target & Select ----------------
with col_left:
    with st.container(key="card-left"):
        section_header("01", "Target market", "Pick a sector and territory to pull live firms from Companies House.")

        selected_vertical_name = st.selectbox(
            "Industry vertical",
            options=list(VERTICAL_PRESETS.keys()),
            index=0,
        )
        vertical_config = VERTICAL_PRESETS[selected_vertical_name]
        render_html(
            '<div class="pe-vertical"><div style="flex:1">'
            '<div class="lbl">Systems we integrate with</div><div class="pe-chips">'
            + "".join(chip(c, "accent") for c in vertical_config["crms"])
            + '</div></div><div><div class="lbl">SIC</div><div class="pe-chips">'
            + "".join(chip(c) for c in vertical_config["sic_codes"])
            + "</div></div></div>"
        )

        f_col1, f_col2 = st.columns(2)
        with f_col1:
            location_input = st.text_input(
                "Town, city or county",
                placeholder="e.g. Walsall or West Midlands",
            )
        with f_col2:
            keyword_filter = st.text_input(
                "Name keyword (optional)",
                placeholder=f"e.g. {vertical_config['search_hint']}",
            )

        r_col1, r_col2 = columns([1, 2.2])
        with r_col1:
            result_limit = st.selectbox("Results", [25, 50, 100], index=0)
        with r_col2:
            browse_btn = st.button(
                "Find companies", type="primary", **FULL_WIDTH
            )
        target_row = None

        if browse_btn:
            if not ch_api_key:
                st.error("Please supply your Companies House API key in the sidebar.")
            else:
                with st.spinner("Querying the Companies House register…"):
                    enricher = LeadEnricher(ch_api_key=ch_api_key)
                    leads_list, search_error = enricher.browse_vertical(
                        sic_codes=vertical_config["sic_codes"],
                        location_keyword=location_input,
                        company_name_includes=keyword_filter,
                        limit=result_limit,
                    )
                st.session_state["discovered_leads"] = leads_list
                st.session_state["active_vertical_name"] = selected_vertical_name
                st.session_state["search_location"] = location_input.strip()
                st.session_state["selected_lead_row"] = None
                # New search = new table widget, so no stale row selection carries over.
                st.session_state["search_version"] = st.session_state.get("search_version", 0) + 1
                if not search_error:
                    st.session_state["stat_searches"] += 1
                    st.session_state["stat_firms"] += len(leads_list)
                if search_error:
                    st.error(search_error)
                elif not leads_list:
                    st.warning(
                        "No active companies matched. Try a broader location"
                        " (e.g. county instead of town) or remove the name keyword."
                    )

    if st.session_state.get("discovered_leads"):
        with st.container(key="card-select"):
            leads_data = st.session_state["discovered_leads"]
            where = st.session_state.get("search_location") or "the UK"
            log_now = get_sent_log()
            already = sum(1 for r in leads_data if r.get("Company Number") in log_now)
            section_header(
                "02", "Select firms",
                f"{len(leads_data)} active {'firm' if len(leads_data) == 1 else 'firms'} in {where}"
                f" · {st.session_state.get('active_vertical_name', '')}"
                + (f" · {already} already contacted" if already else ""),
            )

            df = pd.DataFrame(leads_data)
            df["Contacted"] = [sent_label(log_now.get(cn)) for cn in df["Company Number"]]
            if "Town / Postcode" in df.columns:
                df["Town"] = df["Town / Postcode"].astype(str).str.split(",").str[0]
            if "Incorporated" in df.columns:
                df["Incorporated"] = pd.to_datetime(df["Incorporated"], errors="coerce")

            table_event = render_leads_table(
                df, key=f"leads_table_{st.session_state.get('search_version', 0)}"
            )
            selected_rows = [i for i in (table_event.selection.rows if table_event else []) if i < len(leads_data)]
            selected = [leads_data[i] for i in selected_rows]
            st.session_state["selected_rows_data"] = selected

            if not selected:
                render_html(
                    f'<div class="pe-hint">{icon("pointer", 16)}'
                    "Tick one firm, or several to build a batch. Click a column header to sort.</div>"
                )
            else:
                n_sel = len(selected)
                names = ", ".join(esc(friendly_company_name(r["Company Name"])) for r in selected[:3])
                more = f" + {n_sel - 3} more" if n_sel > 3 else ""
                contacted_sel = [r for r in selected if r["Company Number"] in log_now]
                meta = (f'#{esc(selected[0]["Company Number"])} · {esc(selected[0]["Town / Postcode"])}'
                        if n_sel == 1 else f"{names}{more}")
                render_html(
                    f'<div class="pe-selected"><div><div class="n">'
                    f'{esc(selected[0]["Company Name"]) if n_sel == 1 else f"{n_sel} firms selected"}</div>'
                    f'<div class="m">{meta}</div></div>'
                    f'{chip(f"{n_sel} selected", "accent")}</div>'
                )
                if contacted_sel:
                    st.caption(
                        f"⚠️ {len(contacted_sel)} of these already contacted: "
                        + ", ".join(friendly_company_name(r["Company Name"]) for r in contacted_sel[:4])
                        + ("…" if len(contacted_sel) > 4 else "")
                    )
                if n_sel > MAX_BATCH:
                    st.warning(f"Batches are capped at {MAX_BATCH} firms. Only the first {MAX_BATCH} will be enriched.")

                website_override = ""
                if n_sel == 1:
                    e_col1, e_col2 = columns([1.6, 1])
                    with e_col1:
                        website_override = st.text_input(
                            "Website (optional)", placeholder="Leave blank to auto-discover",
                        )
                    with e_col2:
                        enrich_btn = st.button("Enrich & build dossier", type="primary", **FULL_WIDTH)
                else:
                    enrich_btn = st.button(
                        f"Enrich {min(n_sel, MAX_BATCH)} firms & add to review queue", type="primary", **FULL_WIDTH
                    )

                if enrich_btn:
                    batch = selected[:MAX_BATCH]
                    vertical_now = st.session_state.get("active_vertical_name", "Estate & Lettings Agents")
                    progress = st.progress(0.0, text="Starting enrichment…")

                    def _enrich(row: Dict[str, Any]) -> ScrapedLead:
                        return LeadEnricher(ch_api_key=ch_api_key).enrich_selected_company(
                            company_number=row["Company Number"],
                            sector_name=vertical_now,
                            manual_website=website_override if len(batch) == 1 else None,
                        )

                    results: Dict[str, ScrapedLead] = {}
                    failures: List[str] = []
                    with ThreadPoolExecutor(max_workers=min(4, len(batch))) as pool:
                        futures = {pool.submit(_enrich, row): row for row in batch}
                        for done, fut in enumerate(as_completed(futures), start=1):
                            row = futures[fut]
                            try:
                                results[row["Company Number"]] = fut.result()
                            except Exception:
                                failures.append(friendly_company_name(row["Company Name"]))
                            progress.progress(
                                done / len(batch),
                                text=f"Enriched {done} of {len(batch)} · {friendly_company_name(row['Company Name'])}",
                            )
                    progress.empty()

                    first_cn = None
                    for row in batch:  # Keep the table's order in the queue
                        cn = row["Company Number"]
                        if cn in results:
                            add_to_queue(results[cn], vertical_now)
                            first_cn = first_cn or cn
                    if first_cn:
                        st.session_state["current_cn"] = first_cn
                        st.session_state["current_cn_select"] = first_cn
                    st.session_state["stat_dossiers"] += len(results)
                    if failures:
                        st.warning("Couldn't enrich: " + ", ".join(failures))
                    if len(batch) > 1 and results:
                        st.success(f"{len(results)} firms added to the review queue below.")


# ---------------- Right: Dossier ----------------
queue: Dict[str, Dict[str, Any]] = st.session_state.setdefault("queue", {})
queue_order: List[str] = [cn for cn in st.session_state.setdefault("queue_order", []) if cn in queue]

with col_right:
    with st.container(key="card-right"):
        if not queue:
            render_html(
                f'<div class="pe-empty"><div style="color:var(--accent);display:inline-block;'
                f'padding:18px;border-radius:20px;background:var(--accent-soft);border:1px solid rgba(124,131,255,.3)">'
                f'{icon("target", 40, 1.6)}</div>'
                '<div class="t">Your dossier will appear here</div>'
                '<div class="s">Every enriched firm gets a contact card, verified channels,'
                ' a sector integration pitch and a one-page PDF.</div>'
                "<ol><li>Choose a sector &amp; territory</li><li>Tick one or more firms</li>"
                "<li>Hit <b>&nbsp;Enrich</b></li></ol></div>"
            )
        else:
            log_now = get_sent_log()
            if st.session_state.get("current_cn") not in queue:
                st.session_state["current_cn"] = queue_order[0]
            if len(queue_order) > 1:
                if st.session_state.get("current_cn_select") not in queue:
                    st.session_state["current_cn_select"] = st.session_state["current_cn"]
                st.selectbox(
                    f"Viewing firm ({len(queue_order)} in queue)",
                    options=queue_order,
                    key="current_cn_select",
                    format_func=lambda c: ("✓ " if c in log_now else "") + friendly_company_name(queue[c]["lead"].company_name),
                )
                st.session_state["current_cn"] = st.session_state["current_cn_select"]
            cn = st.session_state["current_cn"]
            item = queue[cn]
            lead: ScrapedLead = item["lead"]
            current_vert_name = item["vertical"]
            vert_cfg = VERTICAL_PRESETS[current_vert_name]
            contact_name, contact_role = infer_contact_name_and_role(lead, current_vert_name)
            primary_email = pick_primary_email(lead, contact_name)
            is_sent = cn in log_now

            section_header("03", "Lead dossier", "Review, tailor the pitch and send.")

            # Firm header
            meta = [chip(f"#{lead.company_number or 'N/A'}"), chip(current_vert_name, "accent")]
            meta += [chip(f"SIC {c}", "muted") for c in lead.sic_codes[:2]]
            meta.append(confidence_chip(lead.website_confidence if lead.website_url else None))
            if is_sent:
                meta.append(chip(f"Sent {sent_label(log_now[cn])[2:]}", "good"))
            blurb = (
                f'<div class="blurb">“{esc(lead.site_meta_description[:220])}'
                f'{"…" if len(lead.site_meta_description) > 220 else ""}”</div>'
                if lead.site_meta_description else ""
            )
            render_html(
                f'<div class="pe-firm"><div><div class="name">{esc(lead.company_name)}</div>'
                f'<div class="meta">{"".join(meta)}</div>{blurb}</div></div>'
            )

            if not lead.website_url:
                st.warning(
                    "Couldn't confidently find this firm's website. Tick just this firm on the left,"
                    " paste its website and re-run to pull contacts."
                )
            elif lead.website_confidence == "Low":
                st.warning(
                    "Weak website match. Check it's the right firm before sending, or tick just this"
                    " firm on the left, paste the correct website and re-run."
                )

            tab1, tab2 = st.tabs(["Overview", "Pitch & send"])

            with tab1:
                # Contact + channels
                email_rows = "".join(
                    f'<div class="pe-row">{icon("mail", 15)}<a class="trunc" title="{esc(e)}" href="mailto:{esc(e)}">{esc(e)}</a>'
                    + ('<span class="tag" title="Used in the email &amp; PDF">★ Primary</span>' if e == primary_email else "")
                    + "</div>"
                    for e in lead.emails_found[:5]
                ) or '<div class="pe-none">No emails found</div>'
                phone_rows = "".join(
                    f'<div class="pe-row">{icon("phone", 15)}'
                    f'<a href="tel:{esc(p.replace(" ", ""))}">{esc(p)}</a>'
                    + ('<span class="tag">Main</span>' if i == 0 else "")
                    + "</div>"
                    for i, p in enumerate(lead.phones_found[:4])
                ) or '<div class="pe-none">No phone numbers found</div>'
                site_row = (
                    f'<div class="pe-row">{icon("globe", 15)}<a href="{esc(lead.website_url)}" target="_blank">'
                    f'{esc(lead.website_url.replace("https://", "").replace("http://", ""))}</a></div>'
                    if lead.website_url else ""
                )
                addr_row = (
                    f'<div class="pe-row">{icon("pin", 15)}<span>{esc(lead.registered_address)}</span>'
                    '<span class="tag">Reg. office</span></div>'
                    if lead.registered_address else ""
                )
                render_html(
                    '<div class="pe-panel"><div class="h">Decision-maker</div>'
                    f'<div class="pe-contact"><div class="pe-avatar">{esc(initials(contact_name))}</div>'
                    f'<div><div class="n">{esc(contact_name)}</div><div class="r">{esc(contact_role)}</div></div></div>'
                    f'<div style="margin-top:12px">{site_row}{addr_row}</div></div>'
                    '<div class="pe-panel"><div class="h">Channels</div><div class="pe-cols">'
                    f'<div>{email_rows}</div><div>{phone_rows}</div></div></div>'
                )

                # Officers + integration hook
                officer_rows = "".join(
                    f'<div class="pe-officer"><span><span class="who">{esc(display_officer_name(o.name))}</span>'
                    f' <span style="color:var(--muted)">· {esc(o.role)}</span></span>'
                    f'<span class="since">since {esc((o.appointed_on or "N/A")[:4])}</span></div>'
                    for o in lead.officers[:6]
                ) or '<div class="pe-none">No active officers returned</div>'
                hook_items = "".join(f"<li>{esc(b)}</li>" for b in vert_cfg["pitch_bullets"])
                render_html(
                    f'<div class="pe-hook"><div class="h">Integration hook</div>'
                    f'<div class="t">{esc(vert_cfg["primary_hook"])}</div><ul>{hook_items}</ul></div>'
                    f'<div class="pe-panel"><div class="h">Registered officers ({len(lead.officers)})</div>{officer_rows}</div>'
                )

                if lead.website_reasons or lead.discovery_notes or lead.other_emails or lead.pages_checked:
                    with st.expander("How this was found"):
                        if lead.website_reasons:
                            st.markdown("**Website match:** " + "; ".join(lead.website_reasons))
                        for note in lead.discovery_notes:
                            st.markdown(f"- {note}")
                        if lead.other_emails:
                            st.markdown(
                                "**Third-party emails ignored** (agencies, regulators, portals): "
                                + ", ".join(f"`{e}`" for e in lead.other_emails)
                            )
                        if lead.pages_checked:
                            st.markdown("**Pages checked:** " + " · ".join(lead.pages_checked))

            with tab2:
                o1, o2 = st.columns(2)
                with o1:
                    st.session_state["opt_attach"] = st.toggle(
                        "Attach sector overview", value=st.session_state["opt_attach"], key="w_opt_attach",
                        help="Adds a line to the email and attaches the branded PDF to drafts.")
                with o2:
                    st.session_state["opt_switch"] = st.toggle(
                        "Mention Jan 2027 switch-off", value=st.session_state["opt_switch"], key="w_opt_switch")
                attach_overview = st.session_state["opt_attach"]

                ensure_draft(item)
                # Push this firm's saved draft into the editor when switching firms or after a rebuild
                widget_sig = (cn, item["sig"], item.get("to_ver", 0))
                if st.session_state.get("email_widget_sig") != widget_sig:
                    st.session_state["email_to"] = item["to"]
                    st.session_state["email_subject"] = item["subject"]
                    st.session_state["email_body"] = item["body"]
                    st.session_state["email_widget_sig"] = widget_sig

                email_to = st.text_input("To", key="email_to", placeholder="name@firm.co.uk")
                email_subject = st.text_input("Subject", key="email_subject")
                edited_pitch = st.text_area("Email body", key="email_body", height=380)
                if email_to != item["to"]:
                    bump_queue_editor()  # Keep the review table in step with the To box
                item.update(to=email_to, subject=email_subject, body=edited_pitch)
                if lead.emails_found and len(lead.emails_found) > 1:
                    st.caption("Other addresses found: " + ", ".join(e for e in lead.emails_found if e != email_to))

                mailto_url = build_mailto(email_to, email_subject, edited_pitch)
                friendly = draft_filename_part(lead.company_name)
                sector_slug = re.sub(r"[^A-Za-z0-9]+", "_", SECTOR_COPY.get(current_vert_name, {}).get("sector_plural", "sector")).strip("_")

                overview_name = f"SY_Communications_{sector_slug}_overview_{friendly}.pdf"
                overview_bytes = create_sector_overview_pdf(lead, current_vert_name) if attach_overview else None
                eml_bytes = build_eml_draft(
                    email_to, email_subject, edited_pitch,
                    attachments=[(overview_name, overview_bytes)] if overview_bytes else None,
                )
                st.download_button(
                    label=("📎  Email draft with PDF attached" if attach_overview else "📎  Email draft (.eml)"),
                    data=eml_bytes,
                    file_name=f"Email_to_{friendly}.eml",
                    mime="message/rfc822",
                    type="primary",
                    help="Downloads a ready-to-send draft. Click the downloaded file to open it in Outlook with the PDF attached.",
                    **FULL_WIDTH,
                )
                st.caption(
                    "Click the downloaded file to open it in Outlook as a new draft with the PDF attached,"
                    " then check it and hit Send. (Apple Mail: open it, then Message → Send Again.)"
                )
                b1, b2, b3 = st.columns(3)
                with b1:
                    st.link_button("✉️ Email only", mailto_url, **FULL_WIDTH,
                                   help="Opens your email app with the text filled in (no attachment). Handy for Gmail.")
                with b2:
                    if overview_bytes:
                        st.download_button(
                            label="⬇ Overview PDF",
                            data=overview_bytes,
                            file_name=overview_name,
                            mime="application/pdf",
                            **FULL_WIDTH,
                        )
                with b3:
                    st.download_button(
                        label="⬇ Lead dossier",
                        data=bytes(create_pdf_dossier(
                            lead=lead,
                            vertical_name=current_vert_name,
                            pitch_text=edited_pitch,
                            target_crms=vert_cfg["crms"],
                        )),
                        file_name=f"dossier_{friendly.lower()}.pdf",
                        mime="application/pdf",
                        **FULL_WIDTH,
                    )

                # Sent tick: saved to the permanent log, so it's there next time anyone opens the app
                sent_now = st.checkbox(
                    "✅  Handled: tick once this email has gone",
                    value=is_sent,
                    key=f"sent_chk_{cn}_{st.session_state.get('sent_log_ver', 0)}",
                    help="Saved permanently, and shows as Contacted in future searches.",
                )
                if sent_now != is_sent:
                    record_sent({cn: sent_record(item) if sent_now else None})
                    st.rerun()
                if is_sent:
                    rec = log_now[cn]
                    who = f" by {rec['sent_by']}" if rec.get("sent_by") else ""
                    st.caption(f"Marked sent{who} on {sent_label(rec)[2:]} to {rec.get('to') or 'unknown address'}.")

                tips = []
                if len(mailto_url) > 1900:
                    tips.append("This email is long, so the 'Email only' button may cut it short in some apps. The draft file isn't affected.")
                if not email_to:
                    tips.append("No email address found. Add one in the To box first.")
                for tip in tips:
                    st.caption("💡 " + tip)

                if st.toggle("Show copy-ready email", value=False, key="opt_copy"):
                    st.caption("Use the copy icon at the top-right of each box.")
                    st.code(email_subject, language=None)
                    st.code(edited_pitch, language=None)


# ---------------- Review queue (full width) ----------------
if queue:
    with st.container(key="card-queue"):
        log_now = get_sent_log()
        for c in queue_order:
            ensure_draft(queue[c])

        def queue_status(c: str) -> str:
            if c in log_now:
                label = log_now[c].get("status") or "Emailed"
                return f"✓ {label} {sent_label(log_now[c])[2:]}"
            if queue[c]["to"]:
                return "Ready to email"
            if queue[c]["lead"].phones_found:
                return "No email · call"
            return "No contact details"

        included = [c for c in queue_order if queue[c]["include"]]
        ready_ids = [c for c in included if queue[c]["to"] and c not in log_now]
        call_ids = [c for c in included if not queue[c]["to"] and queue[c]["lead"].phones_found and c not in log_now]
        open_ids = [c for c in included if c not in log_now]
        n_handled = sum(1 for c in queue_order if c in log_now)
        section_header(
            "04", "Review & send",
            f"{len(queue_order)} enriched · {len(ready_ids)} ready to email · {len(call_ids)} phone only"
            f" · {n_handled} handled",
        )

        # Quick selection
        q1, q2, q3, _ = st.columns([1, 1.25, 1, 1.6])
        quick = None
        with q1:
            if st.button("Select all", **FULL_WIDTH):
                quick = "all"
        with q2:
            if st.button("Only ready to email", **FULL_WIDTH):
                quick = "ready"
        with q3:
            if st.button("Select none", **FULL_WIDTH):
                quick = "none"
        if quick:
            for c in queue_order:
                queue[c]["include"] = (
                    quick == "all" or (quick == "ready" and bool(queue[c]["to"]) and c not in log_now)
                )
            bump_queue_editor()
            st.rerun()

        qdf = pd.DataFrame([
            {
                "cn": c,
                "Include": bool(queue[c]["include"]),
                "Handled": c in log_now,
                "Status": queue_status(c),
                "Firm": friendly_company_name(queue[c]["lead"].company_name),
                "Contact": infer_contact_name_and_role(queue[c]["lead"], queue[c]["vertical"])[0],
                "Email": queue[c]["to"] or "",
                "Phone": (queue[c]["lead"].phones_found or [""])[0],
                "Website match": (queue[c]["lead"].website_confidence or "Not found") if queue[c]["lead"].website_url else "Not found",
            }
            for c in queue_order
        ])
        editor_kwargs = dict(
            hide_index=True,
            num_rows="fixed",
            key=f"queue_editor_{st.session_state.get('queue_editor_ver', 0)}",
            column_order=["Include", "Handled", "Status", "Firm", "Contact", "Email", "Phone", "Website match"],
            disabled=["Status", "Firm", "Contact", "Phone", "Website match"],
            height=min(38 + 35 * len(qdf), 460),
            column_config={
                "Include": st.column_config.CheckboxColumn("Select", width="small", help="Selected firms are exported and can be bulk-marked as handled"),
                "Handled": st.column_config.CheckboxColumn("Handled ✓", width="small", help="Tick once emailed or dealt with. Saved permanently."),
                "Status": st.column_config.TextColumn("Status", width="small"),
                "Firm": st.column_config.TextColumn("Firm", width="medium"),
                "Contact": st.column_config.TextColumn("Contact", width="small"),
                "Email": st.column_config.TextColumn("Email (editable)", width="medium"),
                "Phone": st.column_config.TextColumn("Phone", width="small"),
                "Website match": st.column_config.TextColumn("Website", width="small"),
            },
        )
        try:
            edited = st.data_editor(qdf, width="stretch", **editor_kwargs)
        except Exception:
            edited = st.data_editor(qdf, use_container_width=True, **editor_kwargs)

        # Apply edits from the table
        sent_changes: Dict[str, Optional[Dict[str, Any]]] = {}
        for _, row in edited.iterrows():
            c = row["cn"]
            if c not in queue:
                continue
            queue[c]["include"] = bool(row["Include"])
            new_to = str(row["Email"] or "").strip()
            if new_to != queue[c]["to"]:
                queue[c]["to"] = new_to
                queue[c]["to_ver"] = queue[c].get("to_ver", 0) + 1
            if bool(row["Handled"]) != (c in log_now):
                sent_changes[c] = sent_record(queue[c]) if row["Handled"] else None
        if sent_changes:
            record_sent(sent_changes)
            st.rerun()

        # Recount after edits so the buttons match the table
        included = [c for c in queue_order if queue[c]["include"]]
        ready_ids = [c for c in included if queue[c]["to"] and c not in log_now]
        open_ids = [c for c in included if c not in log_now]
        no_email_ids = [c for c in open_ids if not queue[c]["to"]]
        stamp = now_uk().strftime("%Y-%m-%d_%H%M")

        a1, a2, a3, a4 = columns([1.5, 1.2, 1.2, 0.7])
        with a1:
            if ready_ids:
                zip_bytes, n_written, _skipped = build_drafts_zip([queue[c] for c in ready_ids], st.session_state["opt_attach"])
                st.download_button(
                    f"📦  {n_written} email {'draft' if n_written == 1 else 'drafts'} (.zip)",
                    data=zip_bytes,
                    file_name=f"SY_Communications_drafts_{stamp}.zip",
                    mime="application/zip",
                    type="primary",
                    help="One ready-to-send Outlook draft per selected firm that has an email address.",
                    **FULL_WIDTH,
                )
            else:
                st.button("📦  No emails to export", disabled=True, **FULL_WIDTH,
                          help="None of the selected firms has an email address yet.")
        with a2:
            st.download_button(
                f"📋  Lead list: {len(included)} {'firm' if len(included) == 1 else 'firms'} (.csv)",
                data=build_lead_list_csv([queue[c] for c in included], log_now),
                file_name=f"SY_Communications_lead_list_{stamp}.csv",
                mime="text/csv",
                disabled=not included,
                help="Every selected firm (with or without email): contacts, phones, directors, website. Opens in Excel.",
                **FULL_WIDTH,
            )
        with a3:
            pop_kwargs = dict(disabled=not open_ids, **FULL_WIDTH)
            try:  # A fresh key after each save closes the pop-up
                pop = st.popover(f"✅  Mark {len(open_ids)} as handled",
                                 key=f"pop_handled_{st.session_state.get('sent_log_ver', 0)}", **pop_kwargs)
            except TypeError:
                pop = st.popover(f"✅  Mark {len(open_ids)} as handled", **pop_kwargs)
            with pop:
                st.markdown(
                    f"Mark **{len(open_ids)} selected {'firm' if len(open_ids) == 1 else 'firms'}** as handled?"
                )
                st.caption(
                    f"{len(open_ids) - len(no_email_ids)} will be logged as *Emailed* and {len(no_email_ids)} as"
                    " *Handled* (no email). They'll show as contacted in future searches. You can untick any"
                    " of them in the table afterwards."
                )
                if st.button("Yes, mark as handled", type="primary", key="confirm_mark_handled", **FULL_WIDTH):
                    record_sent({c: sent_record(queue[c]) for c in open_ids})
                    st.rerun()
        with a4:
            if st.button("Clear", **FULL_WIDTH, help="Empty the review queue (handled ticks are kept)."):
                st.session_state["queue"] = {}
                st.session_state["queue_order"] = []
                bump_queue_editor()
                st.rerun()

        notes = [
            f"{len(included)} selected: {len(ready_ids)} can be emailed"
            + (f", {len(no_email_ids)} {'has' if len(no_email_ids) == 1 else 'have'} no email address"
               " (they're in the lead list, so you can phone them or add an email in the table)" if no_email_ids else "")
            + "."
        ]
        if ready_ids:
            notes.append(
                "The zip has one ready-to-send Outlook draft per firm"
                + (", each with its own personalised PDF attached" if st.session_state["opt_attach"] else "")
                + ". Open each draft, hit Send, then use Mark as handled."
            )
        for note in notes:
            st.caption("💡 " + note)


# ---------------- Late-rendered pieces (reflect this run's state) ----------------
if queue:
    active_step = 4
elif st.session_state.get("selected_rows_data"):
    active_step = 3
elif st.session_state.get("discovered_leads"):
    active_step = 2
else:
    active_step = 1
render_html(hero_html(active_step), target=hero_slot)
render_html(
    '<div class="pe-stats">'
    f'<div class="pe-stat"><div class="v">{st.session_state["stat_firms"]}</div><div class="l">Firms</div></div>'
    f'<div class="pe-stat"><div class="v">{len(queue)}</div><div class="l">Enriched</div></div>'
    f'<div class="pe-stat"><div class="v">{len(get_sent_log())}</div><div class="l">Handled</div></div>'
    "</div>",
    target=sidebar_stats_slot,
)
