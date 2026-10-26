"""Right-side, independently scrolling chat drawer for IT Ops Copilot."""
import streamlit as st


def render_chat_panel() -> None:
    """Render a fixed drawer with a persistent header and visible close button."""
    if "agent_chat_messages" not in st.session_state:
        st.session_state.agent_chat_messages = []

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
            'Ask about incidents, tickets, priorities, or system trends. '
            'The chat UI is ready; live AI replies require connecting the project agent endpoint.</div>',
            unsafe_allow_html=True,
        )

    # Conversation scrolls independently; composer remains at the bottom of the drawer.
    with st.container(height=400, border=False):
        for message in st.session_state.agent_chat_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

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
        clean_prompt = (prompt or "").strip()
        if not clean_prompt:
            st.warning("Enter a message before sending.")
        else:
            st.session_state.agent_chat_messages.append({"role": "user", "content": clean_prompt})
            st.rerun()

    if st.session_state.agent_chat_messages:
        st.caption("Chat history is kept for this session. AI responses are not connected yet.")
