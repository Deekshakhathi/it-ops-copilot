"""Right-side, independently scrolling chat drawer for IT Ops Copilot.

Connected to the backend agent at POST /api/copilot/chat:
- conversation history is kept for the session,
- every reply shows its mode badge (AI-composed vs deterministic),
- factual answers list the supporting ticket IDs,
- suggested questions act as one-click prompts,
- if the backend or the AI provider is unavailable, the error is shown
  honestly and the agent's built-in deterministic queries are used instead.
"""
import requests
import streamlit as st

TICKETS_API_BASE = "http://localhost:8000/api/tickets"
COPILOT_API_BASE = "http://localhost:8000/api/copilot"

SUGGESTED_QUESTIONS = [
    "Which critical tickets remain open?",
    "What are the most common incident categories?",
    "Which tickets have been open the longest?",
]

MODE_BADGES = {
    "ai": '<span class="badge" style="background:#1F845A1F;color:#1F845A">AI reply</span>',
    "fallback": '<span class="badge" style="background:#0C66E41F;color:#0C66E4">Deterministic reply</span>',
    "error": '<span class="badge" style="background:#C9372C1F;color:#C9372C">Error</span>',
}


def _ask_agent(question: str, history: list):
    try:
        response = requests.post(
            f"{COPILOT_API_BASE}/chat",
            json={"question": question, "history": history},
            timeout=60,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.ConnectionError:
        return None, "Cannot connect to the agent API. Is the backend running on port 8000?"
    except requests.Timeout:
        return None, "The agent took too long to respond. Try again."
    except requests.HTTPError as exc:
        detail = str(exc)
        try:
            detail = exc.response.json().get("detail", detail)
        except Exception:
            pass
        return None, detail
    except Exception as exc:
        return None, str(exc)


@st.cache_data(ttl=30)
def _load_ticket_options():
    """Ticket IDs for the 'similar to a selected ticket' pickers."""
    try:
        response = requests.get(TICKETS_API_BASE, timeout=6)
        response.raise_for_status()
        tickets = response.json()
        return [
            f"{t['ticket_id']} — {t['title']} ({t['status']})"
            for t in tickets
            if t.get("ticket_id")
        ]
    except Exception:
        return None


def render_chat_panel() -> None:
    """Render a fixed drawer with a persistent header and visible close button."""
    if "agent_chat_messages" not in st.session_state:
        st.session_state.agent_chat_messages = []
    if "agent_pending_question" not in st.session_state:
        st.session_state.agent_pending_question = None

    # Keep the title and close control visible at the top of the drawer.
    with st.container(key="agent_chat_header"):
        title_col, close_col = st.columns([5, 1], vertical_alignment="center")
        with title_col:
            st.markdown(
                '<div class="chat-drawer-title">✦ IT Ops Copilot AI</div>'
                '<div class="chat-drawer-subtitle">Your incident-management assistant</div>',
                unsafe_allow_html=True,
            )
        with close_col:
            if st.button("✕", key="close_agent_chat", help="Close chat panel", use_container_width=True):
                st.session_state.show_chat_panel = False
                st.rerun()
        st.markdown('<div class="chat-drawer-divider"></div>', unsafe_allow_html=True)

    if not st.session_state.agent_chat_messages:
        st.markdown(
            '<div class="chat-drawer-welcome"><strong>How can I help?</strong><br>'
            "Ask about incidents, tickets, priorities, or system trends. Answers are "
            "grounded in the ticket database and vector search — supporting ticket "
            'IDs are always shown.</div>',
            unsafe_allow_html=True,
        )

    # ── Suggested questions ────────────────────────────────────────────────
    chip1, chip2, chip3 = st.columns(3)
    with chip1:
        chip_critical = st.button(
            "🚨 Which critical tickets remain open?", key="chip_critical", use_container_width=True
        )
    with chip2:
        chip_categories = st.button(
            "📊 What are the most common incident categories?", key="chip_categories", use_container_width=True
        )
    with chip3:
        chip_longest = st.button(
            "⏳ Which tickets have been open the longest?", key="chip_longest", use_container_width=True
        )

    ticket_options = _load_ticket_options()

    chip_similar = chip_troubleshoot = False
    chip4, sel_row = st.columns([2.2, 2.6])

    with chip4:
        st.caption("Pick a ticket to compare or troubleshoot:")
    with sel_row:
        chosen_ticket = st.selectbox(
            "Select ticket",
            ticket_options if ticket_options else ["(backend unavailable)"],
            label_visibility="collapsed",
            key="agent_ticket_selector",
        )

    sel1, sel2 = st.columns(2)
    with sel1:
        chip_similar = st.button(
            "🔎 Find similar incidents", key="chip_similar", use_container_width=True
        )
    with sel2:
        chip_troubleshoot = st.button(
            "🧭 Suggest troubleshooting steps", key="chip_troubleshoot", use_container_width=True
        )

    if ticket_options is None:
        st.caption("⚠️ Ticket list unavailable — start the backend on port 8000 to use ticket pickers.")

    selected_id = chosen_ticket.split(" — ")[0] if chosen_ticket and " — " in chosen_ticket else ""
    if chip_critical:
        st.session_state.agent_pending_question = SUGGESTED_QUESTIONS[0]
        st.rerun()
    elif chip_categories:
        st.session_state.agent_pending_question = SUGGESTED_QUESTIONS[1]
        st.rerun()
    elif chip_longest:
        st.session_state.agent_pending_question = SUGGESTED_QUESTIONS[2]
        st.rerun()
    elif chip_similar:
        if selected_id:
            st.session_state.agent_pending_question = f"Find incidents similar to {selected_id}."
            st.rerun()
        else:
            st.warning("Select a ticket first.")
    elif chip_troubleshoot:
        if selected_id:
            st.session_state.agent_pending_question = f"Suggest troubleshooting steps for {selected_id}."
            st.rerun()
        else:
            st.warning("Select a ticket first.")

    # ── Conversation ───────────────────────────────────────────────────────
    with st.container(height=400, border=False):
        for message in st.session_state.agent_chat_messages:
            if message["role"] == "assistant":
                with st.chat_message("assistant"):
                    st.markdown(message["content"])
                    badge = MODE_BADGES.get(message.get("mode"), MODE_BADGES["error"])
                    caption = badge
                    if message.get("sources"):
                        caption += ' <span style="font-size:0.72rem;color:#6B778C"> · Sources: ' + \
                            ", ".join(message["sources"][:10]) + "</span>"
                    st.markdown(caption, unsafe_allow_html=True)
            else:
                with st.chat_message("user"):
                    st.markdown(message["content"])

    # ── Composer ───────────────────────────────────────────────────────────
    with st.form("agent_chat_form", clear_on_submit=True):
        prompt = st.text_area(
            "Message the agent",
            placeholder="Ask about incidents, tickets, or system trends…",
            height=82,
            label_visibility="collapsed",
            key="agent_chat_prompt",
        )
        send = st.form_submit_button("Send message  ➤", use_container_width=True)

    if send:
        clean_prompt = (prompt or "").strip()[:1000]
        if not clean_prompt:
            st.warning("Enter a message before sending.")
        else:
            st.session_state.agent_chat_messages.append({"role": "user", "content": clean_prompt})
            st.session_state.agent_pending_question = clean_prompt
            st.rerun()

    # ── Answer the pending question exactly once per turn ──────────────────
    pending = st.session_state.agent_pending_question
    if pending:
        st.session_state.agent_pending_question = None
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.agent_chat_messages
            if m["role"] in ("user", "assistant") and m.get("content")
        ][-12:]

        with st.spinner("Thinking…"):
            data, err = _ask_agent(pending, history)

        if err:
            st.session_state.agent_chat_messages.append(
                {"role": "assistant", "content": f"⚠️ {err}", "mode": "error", "sources": []}
            )
        else:
            st.session_state.agent_chat_messages.append(
                {
                    "role": "assistant",
                    "content": data.get("reply", "(empty reply)"),
                    "mode": data.get("mode", "fallback"),
                    "sources": data.get("sources", []),
                }
            )
        st.rerun()

    if st.session_state.agent_chat_messages:
        st.caption(
            "Chat history is kept for this session. Facts come from the ticket database; "
            "suggestions are labeled recommendations, not verified fixes."
        )
