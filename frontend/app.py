import requests
import pandas as pd
import streamlit as st
from datetime import datetime
from html import escape

# ── Config ──────────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000/api/tickets"

PRIORITY_COLORS = {
    "Critical": "#C9372C",
    "High":     "#E56910",
    "Medium":   "#946F00",
    "Low":      "#1F845A",
}

STATUS_COLORS = {
    "Open":        "#505F79",
    "In Progress": "#0C66E4",
    "Resolved":    "#1F845A",
    "Closed":      "#6B778C",
}

CATEGORY_ICONS = {
    "Infrastructure": "🖥️",
    "Application":    "📦",
    "Database":       "🗄️",
    "Network":        "🌐",
    "Security":       "🔒",
    "Performance":    "⚡",
    "Other":          "🔧",
}

CATEGORIES = list(CATEGORY_ICONS.keys())
PRIORITIES = ["Low", "Medium", "High", "Critical"]
STATUSES   = ["Open", "In Progress", "Resolved", "Closed"]

BLUES = ["#0C66E4", "#1D7AFC", "#388BFF", "#579DFF", "#85B8FF", "#09326C", "#0055CC"]

# ── Page setup ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IT Ops Copilot",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS (modern Atlassian-style: blue + white) ────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --ink: #172B4D;  --ink-2: #44546F;  --ink-3: #6B778C;
    --line: #DCE1EA; --surface: #FFFFFF; --canvas: #F4F7FB;
    --brand: #0C66E4; --brand-hover: #0055CC; --brand-deep: #09326C;
    --tint-1: #E9F2FF; --tint-2: #CCE0FF; --focus: #388BFF;
    --shadow: 0 1px 2px rgba(9,30,66,0.08), 0 4px 14px rgba(9,30,66,0.05);
}

html, body, [class*="css"], .stApp {
    font-family: 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif;
}
.stApp { background: var(--canvas); color: var(--ink); }
.stApp p, .stApp label, .stApp li, .stApp span, .stApp h1, .stApp h2, .stApp h3 { color: var(--ink); }
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }

/* Top bar */
[data-testid="stHeader"] {
    background: rgba(255,255,255,0.9) !important;
    backdrop-filter: blur(8px);
    border-bottom: 1px solid var(--line);
    height: 3.2rem;
}
[data-testid="stHeader"] button, [data-testid="stHeader"] svg { color: var(--ink-2) !important; }
.block-container { padding-top: 5rem; max-width: 1400px; }

/* ── Sidebar ─────────────────────────────────────────────── */
.stApp [data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0B55C4 0%, #09326C 100%);
    border-right: none;
}
.stApp [data-testid="stSidebar"] p,
.stApp [data-testid="stSidebar"] span,
.stApp [data-testid="stSidebar"] label,
.stApp [data-testid="stSidebar"] div { color: #DCE9FF; }
.stApp [data-testid="stSidebar"] button,
.stApp [data-testid="stSidebar"] button svg { color: #fff !important; fill: #fff; }
.stApp [data-testid="stSidebar"] hr { border-top: 1px solid rgba(255,255,255,0.18) !important; }

.stApp .brand { display:flex; align-items:center; gap:12px; padding:6px 0 4px; }
.stApp .brand-logo {
    width:36px; height:36px; border-radius:9px; background:#fff;
    display:flex; align-items:center; justify-content:center; font-size:1.1rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}
.stApp .brand-name { font-weight:700; font-size:1.05rem; color:#fff; line-height:1.15; }
.stApp .brand-sub  { font-size:0.74rem; color:#A9C7F5; }

.stApp [data-testid="stSidebar"] [role="radiogroup"] { gap: 4px; }
.stApp [data-testid="stSidebar"] [role="radiogroup"] label {
    padding: 9px 12px; border-radius: 8px; width: 100%; cursor: pointer;
    transition: background 0.15s;
}
/* hide the radio dot, keep only the text block */
.stApp [data-testid="stSidebar"] [role="radiogroup"] label > div:not(:has([data-testid="stMarkdownContainer"])) { display: none !important; }
.stApp [data-testid="stSidebar"] [role="radiogroup"] label p { color: #CFE0FF; font-weight: 500; font-size: 0.93rem; }
.stApp [data-testid="stSidebar"] [role="radiogroup"] label:hover { background: rgba(255,255,255,0.09); }
.stApp [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
    background: rgba(255,255,255,0.17);
    box-shadow: inset 3px 0 0 #fff;
}
.stApp [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p { color: #fff; font-weight: 600; }

/* line icons for nav items */
.stApp [data-testid="stSidebar"] [role="radiogroup"] label p::before {
    content: ""; display: inline-block; width: 18px; height: 18px; margin-right: 11px;
    vertical-align: -4px; background: currentColor;
    -webkit-mask: var(--ico) center / contain no-repeat; mask: var(--ico) center / contain no-repeat;
}
.stApp [data-testid="stSidebar"] [role="radiogroup"] label:nth-of-type(1) { --ico: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='3' width='7' height='9'/%3E%3Crect x='14' y='3' width='7' height='5'/%3E%3Crect x='14' y='12' width='7' height='9'/%3E%3Crect x='3' y='16' width='7' height='5'/%3E%3C/svg%3E"); }
.stApp [data-testid="stSidebar"] [role="radiogroup"] label:nth-of-type(2) { --ico: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 8a2 2 0 0 0 0 8v3h18v-3a2 2 0 0 1 0-8V5H3z'/%3E%3Cpath d='M13 5v14' stroke-dasharray='2 3'/%3E%3C/svg%3E"); }
.stApp [data-testid="stSidebar"] [role="radiogroup"] label:nth-of-type(3) { --ico: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 5v14M5 12h14'/%3E%3C/svg%3E"); }
.stApp [data-testid="stSidebar"] [role="radiogroup"] label:nth-of-type(4) { --ico: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z'/%3E%3C/svg%3E"); }
.stApp [data-testid="stSidebar"] [role="radiogroup"] label:nth-of-type(5) { --ico: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6'/%3E%3C/svg%3E"); }

.stApp .side-title { font-size:0.78rem; font-weight:600; color:#A9C7F5; margin-bottom:8px; }
.stApp .api-pill {
    display:flex; align-items:center; gap:9px; padding:9px 12px; border-radius:8px;
    background: rgba(255,255,255,0.12); color:#fff; font-size:0.88rem; font-weight:500;
}
.stApp .api-pill .dot { width:9px; height:9px; border-radius:50%; flex:none; }
.stApp .api-note { margin-top:8px; font-size:0.76rem; color:#A9C7F5; word-break:break-word; }

/* ── Page header ─────────────────────────────────────────── */
.stApp .crumb { font-size:0.8rem; color:var(--ink-3); margin-bottom:6px; }
.stApp .page-title { font-size:1.75rem; font-weight:700; color:var(--ink); line-height:1.2; letter-spacing:-0.015em; }
.stApp .page-sub { color:var(--ink-3); margin:6px 0 0; font-size:0.92rem; }
hr { border: none !important; border-top: 1px solid var(--line) !important; margin: 1.3rem 0 !important; }

/* ── KPI metrics ─────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--line);
    border-top: 4px solid var(--brand);
    border-radius: 10px;
    padding: 1rem 1.25rem;
    box-shadow: var(--shadow);
}
[data-testid="stColumn"]:nth-child(1) [data-testid="stMetric"] { border-top-color: #09326C; }
[data-testid="stColumn"]:nth-child(2) [data-testid="stMetric"] { border-top-color: #0C66E4; }
[data-testid="stColumn"]:nth-child(3) [data-testid="stMetric"] { border-top-color: #579DFF; }
[data-testid="stColumn"]:nth-child(4) [data-testid="stMetric"] { border-top-color: #C9372C; }
[data-testid="stColumn"]:nth-child(5) [data-testid="stMetric"] { border-top-color: #1F845A; }
[data-testid="stMetricLabel"] p { color: var(--ink-3) !important; font-size: 0.82rem !important; font-weight: 500; }
[data-testid="stMetricValue"]   { color: var(--ink) !important; font-size: 2rem !important; font-weight: 700 !important; }

/* ── Buttons ─────────────────────────────────────────────── */
.stButton > button,
[data-testid="stFormSubmitButton"] > button {
    background: var(--brand);
    color: #fff;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 0.55rem 1.2rem;
    box-shadow: 0 1px 2px rgba(9,30,66,0.2);
    transition: background 0.15s, box-shadow 0.15s;
}
.stButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {
    background: var(--brand-hover); color:#fff;
    box-shadow: 0 4px 12px rgba(12,102,228,0.35);
}
.stButton > button p, [data-testid="stFormSubmitButton"] > button p { color:#fff; }
.stButton > button:disabled { background: #E9EBEF; box-shadow: none; }
.stButton > button:disabled p { color: #8993A4; }

/* ── Forms & inputs ──────────────────────────────────────── */
[data-testid="stForm"] {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 1.6rem;
    box-shadow: var(--shadow);
}
.stTextInput input, .stTextArea textarea, [data-baseweb="select"] > div {
    background: #fff !important;
    border: 1px solid #C1CAD9 !important;
    border-radius: 8px !important;
    color: var(--ink) !important;
    transition: border-color 0.15s, box-shadow 0.15s;
}
[data-baseweb="select"] div, [data-baseweb="select"] span { color: var(--ink) !important; }
.stTextInput input::placeholder, .stTextArea textarea::placeholder { color: #8993A4 !important; }
.stTextInput input:hover, .stTextArea textarea:hover, [data-baseweb="select"] > div:hover { border-color: #8590A2 !important; }
.stTextInput input:focus, .stTextArea textarea:focus, [data-baseweb="select"] > div:focus-within {
    border-color: var(--focus) !important;
    box-shadow: 0 0 0 3px rgba(56,139,255,0.25) !important;
}
[data-testid="stWidgetLabel"] p { font-size: 0.84rem; font-weight: 600; color: var(--ink-2); }
[data-baseweb="popover"] [role="listbox"], [data-baseweb="popover"] ul, [data-baseweb="menu"] {
    background: #fff !important; border-radius: 8px;
}
[data-baseweb="popover"] li, [data-baseweb="popover"] li * { color: var(--ink) !important; background: transparent; }
[data-baseweb="popover"] li:hover, [data-baseweb="popover"] li[aria-selected="true"] { background: var(--tint-1) !important; }

/* ── Expanders & alerts ──────────────────────────────────── */
[data-testid="stExpander"] {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 10px;
    box-shadow: var(--shadow);
    overflow: hidden;
}
[data-testid="stExpander"] summary:hover { background: var(--tint-1); }
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { color: var(--ink) !important; font-weight: 600; }
[data-testid="stAlert"] { border-radius: 8px; }

/* ── Lozenges ────────────────────────────────────────────── */
.stApp .badge {
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 0.68rem; font-weight: 700; letter-spacing: 0.3px;
    text-transform: uppercase; vertical-align: middle;
}

/* ── Ticket cards ────────────────────────────────────────── */
.stApp .ticket-card {
    background: var(--surface);
    border: 1px solid var(--line);
    border-left: 4px solid var(--brand);
    border-radius: 10px;
    padding: 1rem 1.3rem;
    margin-bottom: 0.7rem;
    box-shadow: var(--shadow);
    transition: box-shadow 0.15s, border-color 0.15s;
}
.stApp .ticket-card:hover { box-shadow: 0 6px 20px rgba(9,30,66,0.12); }
.stApp .ticket-key { color: var(--brand); font-size: 0.84rem; font-weight: 600; }
.stApp .ticket-meta { color: var(--ink-3); font-size: 0.8rem; }
.stApp .ticket-title { margin-top: 0.45rem; color: var(--ink); font-weight: 600; font-size: 1rem; }
.stApp .section-header { font-size: 1.02rem; font-weight: 600; color: var(--ink); margin-bottom: 0.8rem; }

/* ── Dashboard panels & bar lists ────────────────────────── */
.stApp .panel {
    background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
    padding: 1.1rem 1.3rem 0.8rem; box-shadow: var(--shadow); height: 100%;
}
.stApp .bar-row { display:grid; grid-template-columns: 105px 1fr 30px; align-items:center; gap:12px; margin-bottom:14px; }
.stApp .bar-label { font-size:0.84rem; color:var(--ink-2); font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.stApp .bar-track { height:10px; background:var(--tint-1); border-radius:6px; overflow:hidden; }
.stApp .bar-fill  { height:100%; border-radius:6px; }
.stApp .bar-count { font-size:0.88rem; font-weight:700; color:var(--ink); text-align:right; }

/* ── Tables ──────────────────────────────────────────────── */
.stApp .tbl-wrap { background:var(--surface); border:1px solid var(--line); border-radius:12px; overflow-x:auto; box-shadow:var(--shadow); }
.stApp .tbl { width:100%; border-collapse:collapse; font-size:0.87rem; }
.stApp .tbl th {
    text-align:left; padding:11px 16px; background:#F7F8FA; color:var(--ink-3);
    font-weight:600; font-size:0.78rem; border-bottom:2px solid var(--line); white-space:nowrap;
}
.stApp .tbl td { padding:12px 16px; border-bottom:1px solid #EEF1F6; color:var(--ink); }
.stApp .tbl tbody tr:hover { background:#F1F6FF; }
.stApp .tbl tbody tr:last-child td { border-bottom:none; }
.stApp .tbl td.mx-key { font-weight:600; color:var(--ink-2); }
.stApp .tbl td.mx-cell { text-align:center; font-weight:600; }
</style>
""", unsafe_allow_html=True)


# ── API helpers ──────────────────────────────────────────────────────────────

def api_get(path="", params=None):
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=6)
        r.raise_for_status()
        return r.json(), None
    except requests.ConnectionError:
        return None, "Cannot connect to API. Is the backend running on port 8000?"
    except Exception as e:
        return None, str(e)


def api_post(data: dict):
    try:
        r = requests.post(f"{API_BASE}/", json=data, timeout=6)
        r.raise_for_status()
        return r.json(), None
    except requests.HTTPError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return None, detail
    except Exception as e:
        return None, str(e)


def api_patch(ticket_id: str, data: dict):
    try:
        r = requests.patch(f"{API_BASE}/{ticket_id}", json=data, timeout=6)
        r.raise_for_status()
        return r.json(), None
    except requests.HTTPError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return None, detail
    except Exception as e:
        return None, str(e)


def api_delete(ticket_id: str):
    try:
        r = requests.delete(f"{API_BASE}/{ticket_id}", timeout=6)
        r.raise_for_status()
        return True, None
    except requests.HTTPError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return False, detail
    except Exception as e:
        return False, str(e)


def fmt_dt(iso_str: str) -> str:
    try:
        return datetime.fromisoformat(iso_str).strftime("%d %b %Y, %H:%M")
    except Exception:
        return iso_str


def priority_badge(p: str) -> str:
    c = PRIORITY_COLORS.get(p, "#6B778C")
    return f'<span class="badge" style="background:{c}1F;color:{c}">{p}</span>'


def status_badge(s: str) -> str:
    c = STATUS_COLORS.get(s, "#6B778C")
    return f'<span class="badge" style="background:{c}1F;color:{c}">{s}</span>'


# ── Display-only helpers (HTML rendering) ────────────────────────────────────

def page_header(title: str, subtitle: str):
    st.markdown(
        f'<div class="crumb">Projects / IT Ops / {title}</div>'
        f'<div class="page-title">{title}</div>'
        f'<p class="page-sub">{subtitle}</p>',
        unsafe_allow_html=True,
    )
    st.markdown("---")


def bar_panel(title: str, counts: pd.DataFrame, label_col: str, color_for):
    top = max(int(counts["Count"].max()), 1)
    rows = ""
    for _, r in counts.iterrows():
        pct = int(r["Count"]) / top * 100
        rows += (
            f'<div class="bar-row"><div class="bar-label">{escape(str(r[label_col]))}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct:.0f}%;background:{color_for(r[label_col])}"></div></div>'
            f'<div class="bar-count">{int(r["Count"])}</div></div>'
        )
    st.markdown(
        f'<div class="panel"><div class="section-header">{title}</div>{rows}</div>',
        unsafe_allow_html=True,
    )


def matrix_table(m: pd.DataFrame):
    peak = max(int(m.values.max()), 1)
    head = "<th></th>" + "".join(f"<th style='text-align:center'>{c}</th>" for c in m.columns)
    body = ""
    for idx, row in m.iterrows():
        cells = ""
        for v in row:
            v = int(v)
            a = 0.0 if v == 0 else 0.12 + 0.78 * v / peak
            fg = "#fff" if a > 0.5 else "#172B4D"
            cells += f'<td class="mx-cell" style="background:rgba(12,102,228,{a:.2f});color:{fg}">{v}</td>'
        body += f'<tr><td class="mx-key">{idx}</td>{cells}</tr>'
    st.markdown(
        f'<div class="tbl-wrap"><table class="tbl"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>',
        unsafe_allow_html=True,
    )


def ticket_table(d: pd.DataFrame):
    head = "".join(f"<th>{c}</th>" for c in d.columns)
    body = ""
    for _, r in d.iterrows():
        tds = ""
        for c in d.columns:
            v = r[c]
            empty = v is None or v == "" or (isinstance(v, float) and pd.isna(v))
            v = "—" if empty else str(v)
            if c == "ID":
                tds += f'<td><span class="ticket-key">{escape(v)}</span></td>'
            elif c == "Priority" and not empty:
                tds += f"<td>{priority_badge(v)}</td>"
            elif c == "Status" and not empty:
                tds += f"<td>{status_badge(v)}</td>"
            else:
                tds += f"<td>{escape(v)}</td>"
        body += f"<tr>{tds}</tr>"
    st.markdown(
        f'<div class="tbl-wrap"><table class="tbl"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>',
        unsafe_allow_html=True,
    )


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div class="brand"><div class="brand-logo">🛡️</div>'
        '<div><div class="brand-name">IT Ops Copilot</div>'
        '<div class="brand-sub">Service management</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown("---")
    page = st.radio(
        "Navigate",
        ["📊 Dashboard", "🎫 All Tickets", "➕ New Ticket", "✏️ Update Ticket", "🗑️ Delete Ticket"],
        label_visibility="collapsed",
        format_func=lambda x: x.split(" ", 1)[1],
    )
    st.markdown("---")
    st.markdown('<div class="side-title">API status</div>', unsafe_allow_html=True)
    tickets_probe, probe_err = api_get("", params={})
    if probe_err:
        st.markdown(
            '<div class="api-pill"><span class="dot" style="background:#FF8F73"></span>Backend offline</div>'
            f'<div class="api-note">{escape(str(probe_err))}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="api-pill"><span class="dot" style="background:#4ADE80"></span>Backend online</div>'
            '<div class="api-note">http://localhost:8000</div>',
            unsafe_allow_html=True,
        )
    st.markdown("---")
    st.caption("Built with FastAPI + Streamlit")


# ── Fetch all tickets (cached per run) ───────────────────────────────────────
@st.cache_data(ttl=10)
def fetch_all_tickets():
    data, err = api_get("", params={})
    return data or [], err


# ════════════════════════════════════════════════════════════════════════════
# PAGE: Dashboard
# ════════════════════════════════════════════════════════════════════════════
if page == "📊 Dashboard":
    page_header("Dashboard", "Real-time overview of all IT incidents and tickets")

    tickets, err = fetch_all_tickets()

    if err:
        st.error(f"⚠️ {err}")
        st.stop()

    if not tickets:
        st.info("No tickets yet. Create one using **➕ New Ticket** in the sidebar.")
        st.stop()

    df = pd.DataFrame(tickets)

    total    = len(df)
    open_cnt = len(df[df["status"] == "Open"])
    crit_cnt = len(df[df["priority"] == "Critical"])
    res_cnt  = len(df[df["status"] == "Resolved"])
    inp_cnt  = len(df[df["status"] == "In Progress"])

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total tickets", total)
    c2.metric("Open",          open_cnt)
    c3.metric("In progress",   inp_cnt)
    c4.metric("Critical",      crit_cnt)
    c5.metric("Resolved",      res_cnt)

    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        cat_counts = df["category"].value_counts().reset_index()
        cat_counts.columns = ["Category", "Count"]
        bar_panel("By category", cat_counts, "Category",
                  lambda k: BLUES[CATEGORIES.index(k) % len(BLUES)] if k in CATEGORIES else BLUES[0])

    with col_b:
        pri_counts = df["priority"].value_counts().reset_index()
        pri_counts.columns = ["Priority", "Count"]
        bar_panel("By priority", pri_counts, "Priority", lambda k: PRIORITY_COLORS.get(k, "#6B778C"))

    with col_c:
        st_counts = df["status"].value_counts().reset_index()
        st_counts.columns = ["Status", "Count"]
        bar_panel("By status", st_counts, "Status", lambda k: STATUS_COLORS.get(k, "#6B778C"))

    st.markdown("---")
    st.markdown('<div class="section-header">Recent incidents</div>', unsafe_allow_html=True)
    recent = df.head(8)
    for _, row in recent.iterrows():
        icon = CATEGORY_ICONS.get(row["category"], "🔧")
        st.markdown(f"""
        <div class="ticket-card" style="border-left-color:{PRIORITY_COLORS.get(row['priority'], '#0C66E4')}">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <span class="ticket-key">{row['ticket_id']}</span>
                    &nbsp;&nbsp;
                    {priority_badge(row['priority'])}
                    &nbsp;
                    {status_badge(row['status'])}
                </div>
                <span class="ticket-meta">{fmt_dt(row['created_at'])}</span>
            </div>
            <div class="ticket-title">
                {icon} {row['title']}
            </div>
            <div class="ticket-meta" style="margin-top:0.3rem">
                📂 {row['category']}
                {"&nbsp;&nbsp;🖥️ " + str(row['affected_server']) if row.get('affected_server') else ""}
                {"&nbsp;&nbsp;👤 " + str(row['assignee']) if row.get('assignee') else ""}
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="section-header">Priority × status matrix</div>', unsafe_allow_html=True)
    if not df.empty:
        matrix = pd.crosstab(df["priority"], df["status"]).reindex(
            index=PRIORITIES, columns=STATUSES, fill_value=0
        ).fillna(0).astype(int)
        matrix_table(matrix)


# ════════════════════════════════════════════════════════════════════════════
# PAGE: All Tickets
# ════════════════════════════════════════════════════════════════════════════
elif page == "🎫 All Tickets":
    page_header("All Tickets", "Browse, filter and inspect every incident ticket")

    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        f_status = st.selectbox("Status", ["All"] + STATUSES)
    with fc2:
        f_priority = st.selectbox("Priority", ["All"] + PRIORITIES)
    with fc3:
        f_category = st.selectbox("Category", ["All"] + CATEGORIES)
    with fc4:
        f_search = st.text_input("🔍 Search title / ID")

    params = {}
    if f_status   != "All": params["status"]   = f_status
    if f_priority != "All": params["priority"] = f_priority
    if f_category != "All": params["category"] = f_category

    tickets, err = api_get("", params=params)
    if err:
        st.error(f"⚠️ {err}")
        st.stop()

    tickets = tickets or []

    if f_search:
        q = f_search.lower()
        tickets = [t for t in tickets if q in t["title"].lower() or q in t["ticket_id"].lower()]

    st.markdown(f"**{len(tickets)} ticket(s) found**")

    if not tickets:
        st.info("No tickets match your filters.")
    else:
        view_mode = st.radio("View", ["Cards", "Table"], horizontal=True)

        if view_mode == "Table":
            display_cols = ["ticket_id", "title", "category", "priority", "status", "assignee", "affected_server", "created_at"]
            df_view = pd.DataFrame(tickets)[display_cols].copy()
            df_view["created_at"] = df_view["created_at"].apply(fmt_dt)
            df_view.columns = ["ID", "Title", "Category", "Priority", "Status", "Assignee", "Server", "Created"]
            ticket_table(df_view)
        else:
            for t in tickets:
                icon = CATEGORY_ICONS.get(t["category"], "🔧")
                with st.expander(f"{t['ticket_id']} — {t['title']}", expanded=False):
                    st.markdown(
                        f"{priority_badge(t['priority'])}&nbsp;{status_badge(t['status'])}",
                        unsafe_allow_html=True,
                    )
                    r1, r2, r3 = st.columns(3)
                    r1.markdown(f"**Category:** {icon} {t['category']}")
                    r2.markdown(f"**Priority:** {t['priority']}")
                    r3.markdown(f"**Status:** {t['status']}")

                    r4, r5, r6 = st.columns(3)
                    r4.markdown(f"**Server:** {t.get('affected_server') or '—'}")
                    r5.markdown(f"**Assignee:** {t.get('assignee') or '—'}")
                    r6.markdown(f"**Created:** {fmt_dt(t['created_at'])}")

                    st.markdown("**Description:**")
                    st.markdown(f"> {t['description']}")

                    if t.get("resolution_notes"):
                        st.success(f"**Resolution:** {t['resolution_notes']}")


# ════════════════════════════════════════════════════════════════════════════
# PAGE: New Ticket
# ════════════════════════════════════════════════════════════════════════════
elif page == "➕ New Ticket":
    page_header("Create Ticket", "Log a new IT incident or support request")

    with st.form("create_ticket_form", clear_on_submit=True):
        st.markdown('<div class="section-header">Ticket details</div>', unsafe_allow_html=True)

        f1, f2 = st.columns(2)
        with f1:
            title = st.text_input("Title *", placeholder="e.g. Database connection pool exhausted")
        with f2:
            category = st.selectbox("Category *", CATEGORIES)

        description = st.text_area(
            "Description *",
            placeholder="Describe the incident in detail...",
            height=120,
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            priority = st.selectbox("Priority", PRIORITIES, index=1)
        with c2:
            affected_server = st.text_input("Affected Server", placeholder="e.g. prod-db-01")
        with c3:
            assignee = st.text_input("Assignee", placeholder="e.g. alice@corp.com")

        submitted = st.form_submit_button("Create ticket", use_container_width=True)

    if submitted:
        if not title or not description:
            st.error("Title and Description are required.")
        else:
            payload = {
                "title": title,
                "description": description,
                "category": category,
                "priority": priority,
                "affected_server": affected_server or None,
                "assignee": assignee or None,
            }
            result, err = api_post(payload)
            if err:
                st.error(f"❌ Failed to create ticket: {err}")
            else:
                st.success(f"✅ Ticket **{result['ticket_id']}** created successfully!")
                st.markdown(f"""
                <div class="ticket-card" style="margin-top:1rem;border-left-color:{PRIORITY_COLORS.get(result['priority'], '#0C66E4')}">
                    <div class="ticket-key">{result['ticket_id']}</div>
                    <div class="ticket-title" style="font-size:1.05rem">{result['title']}</div>
                    <div style="margin-top:0.5rem">
                        {priority_badge(result['priority'])}
                        &nbsp;
                        {status_badge(result['status'])}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.cache_data.clear()


# ════════════════════════════════════════════════════════════════════════════
# PAGE: Update Ticket
# ════════════════════════════════════════════════════════════════════════════
elif page == "✏️ Update Ticket":
    page_header("Update Ticket", "Modify status, assignee, resolution and more")

    all_tickets, err = fetch_all_tickets()
    if err:
        st.error(f"⚠️ {err}")
        st.stop()

    if not all_tickets:
        st.info("No tickets found. Create one first.")
        st.stop()

    ticket_options = {f"{t['ticket_id']} — {t['title']}": t for t in all_tickets}
    selected_label = st.selectbox("Select Ticket", list(ticket_options.keys()))
    selected = ticket_options[selected_label]

    st.markdown("---")

    with st.expander("Current ticket details", expanded=True):
        pc1, pc2, pc3 = st.columns(3)
        pc1.markdown(f"**Status:** {selected['status']}")
        pc2.markdown(f"**Priority:** {selected['priority']}")
        pc3.markdown(f"**Category:** {selected['category']}")
        st.markdown(f"**Description:** {selected['description']}")
        if selected.get("resolution_notes"):
            st.info(f"**Current resolution:** {selected['resolution_notes']}")

    st.markdown("---")
    st.markdown('<div class="section-header">Apply changes</div>', unsafe_allow_html=True)

    with st.form("update_ticket_form"):
        u1, u2, u3 = st.columns(3)
        with u1:
            new_status = st.selectbox("Status", STATUSES, index=STATUSES.index(selected["status"]))
        with u2:
            new_priority = st.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(selected["priority"]))
        with u3:
            new_category = st.selectbox("Category", CATEGORIES, index=CATEGORIES.index(selected["category"]))

        u4, u5 = st.columns(2)
        with u4:
            new_server = st.text_input("Affected Server", value=selected.get("affected_server") or "")
        with u5:
            new_assignee = st.text_input("Assignee", value=selected.get("assignee") or "")

        new_title = st.text_input("Title", value=selected["title"])
        new_description = st.text_area("Description", value=selected["description"], height=100)
        new_resolution = st.text_area(
            "Resolution Notes",
            value=selected.get("resolution_notes") or "",
            placeholder="Required when resolving a ticket",
            height=80,
        )

        update_btn = st.form_submit_button("Save changes", use_container_width=True)

    if update_btn:
        payload = {
            "title":            new_title,
            "description":      new_description,
            "status":           new_status,
            "priority":         new_priority,
            "category":         new_category,
            "affected_server":  new_server or None,
            "assignee":         new_assignee or None,
            "resolution_notes": new_resolution or None,
        }
        result, err = api_patch(selected["ticket_id"], payload)
        if err:
            st.error(f"❌ Update failed: {err}")
        else:
            st.success(f"✅ Ticket **{result['ticket_id']}** updated — Status: **{result['status']}**")
            st.cache_data.clear()


# ════════════════════════════════════════════════════════════════════════════
# PAGE: Delete Ticket
# ════════════════════════════════════════════════════════════════════════════
elif page == "🗑️ Delete Ticket":
    page_header("Delete Ticket", "Permanently remove a ticket from the system")

    all_tickets, err = fetch_all_tickets()
    if err:
        st.error(f"⚠️ {err}")
        st.stop()

    if not all_tickets:
        st.info("No tickets found.")
        st.stop()

    ticket_options = {f"{t['ticket_id']} — {t['title']}": t for t in all_tickets}
    selected_label = st.selectbox("Select Ticket to Delete", list(ticket_options.keys()))
    selected = ticket_options[selected_label]

    st.markdown("---")
    st.markdown(f"""
    <div class="ticket-card" style="border-left-color:#C9372C">
        <div style="display:flex;justify-content:space-between">
            <div>
                <span class="ticket-key" style="color:#C9372C">{selected['ticket_id']}</span>
                &nbsp;&nbsp;
                {priority_badge(selected['priority'])}
                &nbsp;
                {status_badge(selected['status'])}
            </div>
        </div>
        <div class="ticket-title" style="font-size:1.05rem">
            {CATEGORY_ICONS.get(selected['category'], '🔧')} {selected['title']}
        </div>
        <div class="ticket-meta" style="margin-top:0.3rem">
            {selected['description'][:150]}{'...' if len(selected['description']) > 150 else ''}
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.warning("⚠️ This action is **permanent** and cannot be undone.")

    confirm = st.checkbox(f"I confirm I want to delete **{selected['ticket_id']}**")
    if st.button("Delete ticket", disabled=not confirm):
        ok, err = api_delete(selected["ticket_id"])
        if err:
            st.error(f"❌ Delete failed: {err}")
        else:
            st.success(f"✅ Ticket **{selected['ticket_id']}** has been deleted.")
            st.cache_data.clear()
            st.rerun()
