import requests
import pandas as pd
import streamlit as st
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000/api/tickets"

PRIORITY_COLORS = {
    "Critical": "#ff4757",
    "High":     "#ffa502",
    "Medium":   "#eccc68",
    "Low":      "#2ed573",
}

STATUS_COLORS = {
    "Open":        "#ff4757",
    "In Progress": "#ffa502",
    "Resolved":    "#2ed573",
    "Closed":      "#747d8c",
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

# ── Page setup ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IT Ops Copilot",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp {
    background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
    min-height: 100vh;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #161b22 0%, #0d1117 100%);
    border-right: 1px solid rgba(99,179,237,0.15);
}

[data-testid="stMetric"] {
    background: rgba(22,27,34,0.8);
    border: 1px solid rgba(99,179,237,0.2);
    border-radius: 16px;
    padding: 1.2rem 1.5rem;
    backdrop-filter: blur(10px);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 30px rgba(99,179,237,0.15);
}
[data-testid="stMetricLabel"] { color: #8b949e !important; font-size: 0.85rem !important; }
[data-testid="stMetricValue"] { color: #e6edf3 !important; font-size: 2rem !important; font-weight: 700 !important; }

.stButton > button {
    background: linear-gradient(135deg, #1f6feb 0%, #388bfd 100%);
    color: white;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    padding: 0.5rem 1.4rem;
    transition: all 0.2s ease;
    box-shadow: 0 4px 15px rgba(31,111,235,0.3);
}
.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(31,111,235,0.5);
}

[data-testid="stForm"] {
    background: rgba(22,27,34,0.9);
    border: 1px solid rgba(99,179,237,0.2);
    border-radius: 16px;
    padding: 1.5rem;
    backdrop-filter: blur(12px);
}

.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div {
    background: rgba(13,17,23,0.8) !important;
    border: 1px solid rgba(99,179,237,0.25) !important;
    border-radius: 10px !important;
    color: #e6edf3 !important;
}

.stTabs [data-baseweb="tab-list"] {
    background: rgba(22,27,34,0.8);
    border-radius: 12px;
    gap: 4px;
    padding: 4px;
    border: 1px solid rgba(99,179,237,0.15);
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: #8b949e;
    border-radius: 8px;
    font-weight: 500;
    transition: all 0.2s;
}
.stTabs [aria-selected="true"] {
    background: rgba(31,111,235,0.25) !important;
    color: #63b3ed !important;
}

hr { border-color: rgba(99,179,237,0.15) !important; }

.badge {
    display: inline-block;
    padding: 2px 12px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.4px;
}

.ticket-card {
    background: rgba(22,27,34,0.85);
    border: 1px solid rgba(99,179,237,0.18);
    border-radius: 14px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 0.8rem;
    backdrop-filter: blur(10px);
    transition: transform 0.2s, box-shadow 0.2s;
}
.ticket-card:hover {
    transform: translateX(4px);
    box-shadow: 0 4px 20px rgba(99,179,237,0.12);
    border-color: rgba(99,179,237,0.35);
}

.section-header {
    font-size: 1.3rem;
    font-weight: 700;
    color: #e6edf3;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid rgba(31,111,235,0.4);
}
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
    c = PRIORITY_COLORS.get(p, "#aaa")
    return f'<span class="badge" style="background:{c}22;color:{c};border:1px solid {c}55">{p}</span>'


def status_badge(s: str) -> str:
    c = STATUS_COLORS.get(s, "#aaa")
    return f'<span class="badge" style="background:{c}22;color:{c};border:1px solid {c}55">{s}</span>'


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛡️ IT Ops Copilot")
    st.markdown("---")
    page = st.radio(
        "Navigate",
        ["📊 Dashboard", "🎫 All Tickets", "➕ New Ticket", "✏️ Update Ticket", "🗑️ Delete Ticket"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("### 🔌 API Status")
    tickets_probe, probe_err = api_get("", params={})
    if probe_err:
        st.error("⚠️ Backend Offline")
        st.caption(probe_err)
    else:
        st.success("✅ Backend Online")
        st.caption("http://localhost:8000")
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
    st.markdown('<h1 style="color:#e6edf3;font-size:2.2rem;font-weight:800;margin-bottom:0">📊 Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color:#8b949e;margin-top:0.2rem">Real-time overview of all IT incidents & tickets</p>', unsafe_allow_html=True)
    st.markdown("---")

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
    c1.metric("Total Tickets",  total)
    c2.metric("🔴 Open",         open_cnt)
    c3.metric("🟠 In Progress",  inp_cnt)
    c4.metric("🚨 Critical",     crit_cnt)
    c5.metric("✅ Resolved",     res_cnt)

    st.markdown("---")

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.markdown('<div class="section-header">🗂️ By Category</div>', unsafe_allow_html=True)
        cat_counts = df["category"].value_counts().reset_index()
        cat_counts.columns = ["Category", "Count"]
        st.bar_chart(cat_counts.set_index("Category"), color="#1f6feb")

    with col_b:
        st.markdown('<div class="section-header">🚦 By Priority</div>', unsafe_allow_html=True)
        pri_counts = df["priority"].value_counts().reset_index()
        pri_counts.columns = ["Priority", "Count"]
        st.bar_chart(pri_counts.set_index("Priority"), color="#ffa502")

    with col_c:
        st.markdown('<div class="section-header">📋 By Status</div>', unsafe_allow_html=True)
        st_counts = df["status"].value_counts().reset_index()
        st_counts.columns = ["Status", "Count"]
        st.bar_chart(st_counts.set_index("Status"), color="#2ed573")

    st.markdown("---")
    st.markdown('<div class="section-header">🕐 Recent Incidents</div>', unsafe_allow_html=True)
    recent = df.head(8)
    for _, row in recent.iterrows():
        icon = CATEGORY_ICONS.get(row["category"], "🔧")
        st.markdown(f"""
        <div class="ticket-card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <span style="color:#8b949e;font-size:0.8rem;font-weight:600">{row['ticket_id']}</span>
                    &nbsp;&nbsp;
                    {priority_badge(row['priority'])}
                    &nbsp;
                    {status_badge(row['status'])}
                </div>
                <span style="color:#8b949e;font-size:0.8rem">{fmt_dt(row['created_at'])}</span>
            </div>
            <div style="margin-top:0.5rem;color:#e6edf3;font-weight:600;font-size:1rem">
                {icon} {row['title']}
            </div>
            <div style="margin-top:0.3rem;color:#8b949e;font-size:0.85rem">
                📂 {row['category']}
                {"&nbsp;&nbsp;🖥️ " + str(row['affected_server']) if row.get('affected_server') else ""}
                {"&nbsp;&nbsp;👤 " + str(row['assignee']) if row.get('assignee') else ""}
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="section-header">📈 Priority × Status Matrix</div>', unsafe_allow_html=True)
    if not df.empty:
        matrix = pd.crosstab(df["priority"], df["status"]).reindex(
            index=PRIORITIES, columns=STATUSES, fill_value=0
        ).fillna(0).astype(int)
        st.dataframe(matrix, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# PAGE: All Tickets
# ════════════════════════════════════════════════════════════════════════════
elif page == "🎫 All Tickets":
    st.markdown('<h1 style="color:#e6edf3;font-size:2.2rem;font-weight:800;margin-bottom:0">🎫 All Tickets</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color:#8b949e;margin-top:0.2rem">Browse, filter and inspect every incident ticket</p>', unsafe_allow_html=True)
    st.markdown("---")

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
            st.dataframe(df_view, use_container_width=True, hide_index=True)
        else:
            for t in tickets:
                icon = CATEGORY_ICONS.get(t["category"], "🔧")
                with st.expander(f"{t['ticket_id']} — {t['title']}", expanded=False):
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
    st.markdown('<h1 style="color:#e6edf3;font-size:2.2rem;font-weight:800;margin-bottom:0">➕ Create New Ticket</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color:#8b949e;margin-top:0.2rem">Log a new IT incident or support request</p>', unsafe_allow_html=True)
    st.markdown("---")

    with st.form("create_ticket_form", clear_on_submit=True):
        st.markdown('<div class="section-header">📝 Ticket Details</div>', unsafe_allow_html=True)

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

        submitted = st.form_submit_button("🚀 Create Ticket", use_container_width=True)

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
                <div class="ticket-card" style="margin-top:1rem">
                    <div style="color:#8b949e;font-size:0.8rem">{result['ticket_id']}</div>
                    <div style="color:#e6edf3;font-weight:700;font-size:1.1rem;margin-top:0.3rem">{result['title']}</div>
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
    st.markdown('<h1 style="color:#e6edf3;font-size:2.2rem;font-weight:800;margin-bottom:0">✏️ Update Ticket</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color:#8b949e;margin-top:0.2rem">Modify status, assignee, resolution and more</p>', unsafe_allow_html=True)
    st.markdown("---")

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

    with st.expander("📄 Current Ticket Details", expanded=True):
        pc1, pc2, pc3 = st.columns(3)
        pc1.markdown(f"**Status:** {selected['status']}")
        pc2.markdown(f"**Priority:** {selected['priority']}")
        pc3.markdown(f"**Category:** {selected['category']}")
        st.markdown(f"**Description:** {selected['description']}")
        if selected.get("resolution_notes"):
            st.info(f"**Current resolution:** {selected['resolution_notes']}")

    st.markdown("---")
    st.markdown('<div class="section-header">🔧 Apply Changes</div>', unsafe_allow_html=True)

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

        update_btn = st.form_submit_button("💾 Save Changes", use_container_width=True)

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
    st.markdown('<h1 style="color:#e6edf3;font-size:2.2rem;font-weight:800;margin-bottom:0">🗑️ Delete Ticket</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color:#8b949e;margin-top:0.2rem">Permanently remove a ticket from the system</p>', unsafe_allow_html=True)
    st.markdown("---")

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
    <div class="ticket-card" style="border-color:rgba(255,71,87,0.35)">
        <div style="display:flex;justify-content:space-between">
            <div>
                <span style="color:#ff4757;font-weight:700">{selected['ticket_id']}</span>
                &nbsp;&nbsp;
                {priority_badge(selected['priority'])}
                &nbsp;
                {status_badge(selected['status'])}
            </div>
        </div>
        <div style="color:#e6edf3;font-weight:600;margin-top:0.5rem;font-size:1.05rem">
            {CATEGORY_ICONS.get(selected['category'], '🔧')} {selected['title']}
        </div>
        <div style="color:#8b949e;font-size:0.85rem;margin-top:0.3rem">
            {selected['description'][:150]}{'...' if len(selected['description']) > 150 else ''}
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.warning("⚠️ This action is **permanent** and cannot be undone.")

    confirm = st.checkbox(f"I confirm I want to delete **{selected['ticket_id']}**")
    if st.button("🗑️ Delete Ticket", disabled=not confirm):
        ok, err = api_delete(selected["ticket_id"])
        if err:
            st.error(f"❌ Delete failed: {err}")
        else:
            st.success(f"✅ Ticket **{selected['ticket_id']}** has been deleted.")
            st.cache_data.clear()
            st.rerun()
