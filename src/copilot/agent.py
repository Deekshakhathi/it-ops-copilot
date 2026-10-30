"""IT Ops Copilot agent: routes questions to validated read-only tools.

Design:
1. A deterministic intent router handles common question shapes without the
   LLM, so basic queries keep working even with no provider configured.
2. When an LLM is configured, its job is strictly bounded: it either picks one
   of the predefined tools (validated by name and argument type/enum BEFORE
   execution) or turns tool-produced facts into a natural-language answer.
   The LLM never executes SQL, shell commands, or arbitrary Python, and it is
   instructed to use only the facts supplied by the application.
3. Without a provider, answers are rendered deterministically from the same
   tool facts — never presented as AI-generated.
"""
import json
import re
from typing import Optional

from src.copilot import llm
from src.copilot.llm import LLMConfig, LLMUnavailableError
from src.copilot import tools
from src.copilot.tools import (
    VALID_CATEGORIES,
    VALID_PRIORITIES,
    VALID_STATUSES,
)

TICKET_ID_FINDER = re.compile(r"\b[A-Z]{2,10}-\d+\b", re.IGNORECASE)
QUESTION_MAX_LENGTH = 1000
HISTORY_MAX_MESSAGES = 12

SYSTEM_RULES = """You are the IT Ops Copilot for an incident-management team.
You answer questions about incident tickets stored in this application.

Strict rules:
- Use ONLY the facts provided in the data block below. Never invent ticket IDs,
  counts, resolutions, servers, assignees, or historical incidents.
- When a claim relates to specific tickets, cite their ticket IDs inline, e.g. (INC-1024).
- Anything you generalize (causes, patterns, next steps) must be presented as
  a recommendation or inference, NOT as a verified fact. Mark such text with
  "Recommendation:" or "Inference:".
- Be concise and use short markdown bullets.
- If the data block is marked NOT_ENOUGH_DATA, say what additional information
  is needed instead of guessing.
"""


def answer_question(question: str, history: Optional[list] = None) -> dict:
    """Answer a user question. Returns {reply, mode, sources}.

    mode is one of:
      - "ai"      : composed by the configured LLM from tool facts
      - "fallback": deterministic formatting (no AI involved), either basic
                    query handling or a provider-unavailable notice
    """
    clean_question = (question or "").strip()[:QUESTION_MAX_LENGTH]
    history = _sanitize_history(history)

    if not clean_question:
        return {
            "reply": "Please type a question, for example: *Which critical tickets remain open?*",
            "mode": "fallback",
            "sources": [],
        }

    config = llm.get_llm_config()

    # Deterministic intent routing first.
    facts = _gather_facts(clean_question)

    if facts is not None and facts["kind"] != "unknown":
        if llm.is_provider_configured(config):
            ai_reply = _compose_reply(
                config, clean_question, facts, history, allow_tool_round=True
            )
            if ai_reply is not None:
                return {
                    "reply": ai_reply,
                    "mode": "ai",
                    "sources": facts.get("sources", []),
                }

        reply = _render_facts(facts)
        if facts.get("ai_note"):
            reply += f"\n\n---\nℹ️ {facts['ai_note']}"
        return {
            "reply": reply,
            "mode": "fallback",
            "sources": facts.get("sources", []),
        }

    facts = facts or {"kind": "unknown", "data": None, "sources": []}

    if llm.is_provider_configured(config):
        # Let the LLM choose a tool; args are validated before execution.
        try:
            tool, args = _llm_pick_tool(config, history, clean_question)
            if tool:
                result = tools.parse_tool_args(tool, args)
                tool_facts = {"kind": f"tool_{tool}", "data": result, "sources": _sources_from_result(tool, result)}
                ai_reply = _compose_reply(config, clean_question, tool_facts, history, allow_tool_round=False)
                if ai_reply is not None:
                    return {
                        "reply": ai_reply,
                        "mode": "ai",
                        "sources": tool_facts["sources"],
                    }
                return {
                    "reply": _render_facts(tool_facts),
                    "mode": "fallback",
                    "sources": tool_facts["sources"],
                }
        except (LLMUnavailableError, json.JSONDecodeError, ValueError, KeyError):
            pass

    return {
        "reply": (
            "I don't have a language model available right now, so I can only answer "
            "questions that match my built-in queries. Try one of these:\n"
            "- *Which critical tickets remain open?*\n"
            "- *What are the most common incident categories?*\n"
            "- *Which tickets have been open the longest?*\n"
            "- *Find incidents similar to INC-1001.*\n"
            "- *Suggest troubleshooting steps for INC-1005.*\n\n"
            "Tip: reference a ticket by its ID, or filter with phrases like "
            "“high priority network tickets assigned to Priya”."
        ),
        "mode": "fallback",
        "sources": [],
    }


# ── Deterministic intent routing ─────────────────────────────────────────────

def _gather_facts(question: str) -> Optional[dict]:
    lower = question.lower()
    ticket_ids = [m.upper() for m in TICKET_ID_FINDER.findall(question)]
    first_ticket = ticket_ids[0] if ticket_ids else None

    # Direct ticket lookup
    if first_ticket and _any(lower, ["details", "tell me about", "show me ticket", "show ticket", "what is", "status of"]):
        ticket = tools.get_ticket(first_ticket)
        if ticket:
            return {"kind": "ticket_detail", "data": ticket, "sources": [first_ticket]}
        return {"kind": "ticket_not_found", "data": first_ticket, "sources": []}

    # Similar tickets
    if first_ticket and _any(lower, ["similar", "same as", "like ticket", "duplicate risk", "related"]):
        data = tools.find_similar_to_ticket(first_ticket)
        if data["ticket"] is None:
            return {"kind": "ticket_not_found", "data": first_ticket, "sources": []}
        ids = [s["ticket_id"] for s in data["similar"]]
        return {"kind": "similar_to_ticket", "data": data, "sources": [first_ticket] + ids}

    # Troubleshooting recommendations
    if first_ticket and _any(lower, ["troubleshoot", "troubleshooting", "suggest", "suggestion", "recommend", "remediat", "how to fix", "fix"]):
        data = tools.recommend_troubleshooting(first_ticket)
        if data["ticket"] is None:
            return {"kind": "ticket_not_found", "data": first_ticket, "sources": []}
        ids = [r["ticket_id"] for r in data["recommendations"]]
        return {
            "kind": "troubleshooting",
            "data": data,
            "sources": [first_ticket] + ids,
            "is_recommendation": True,
        }

    # Longest open
    if _any(lower, ["longest", "oldest", "been open the longest", "waiting the longest", "stale"]):
        data = tools.get_longest_open_tickets()
        return {"kind": "longest_open", "data": data, "sources": [t["ticket_id"] for t in data]}

    # Recurring patterns
    if _any(lower, ["recurring", "pattern", "repeat", "frequent", "chronic"]):
        data = tools.find_recurring_patterns()
        ids = [t["ticket_id"] for p in data for t in p["tickets"]]
        return {"kind": "patterns", "data": data, "sources": ids}

    # Most common categories
    if _any(lower, ["common", "categories", "category", "trending", "topics", "many tickets"]):
        summary = tools.get_ticket_summary()
        return {"kind": "summary", "data": summary, "sources": []}

    # Open critical tickets
    if _any(lower, ["critical"]) and _any(lower, ["open", "unresolved", "still"]):
        data = tools.search_tickets(status="Open", priority="Critical", limit=15)
        data += [t for t in tools.search_tickets(status="In Progress", priority="Critical", limit=15) if t not in data]
        return {
            "kind": "search_results",
            "data": {"tickets": data, "filters": {"status": "Open/In Progress", "priority": "Critical"}},
            "sources": [t["ticket_id"] for t in data],
        }

    # Ticket summary / counts
    if _any(lower, ["summary", "overview", "how many", "count", "dashboard"]):
        summary = tools.get_ticket_summary()
        return {"kind": "summary", "data": summary, "sources": []}

    # Filter-based search attempts
    filters = _extract_search_filters(question)
    if filters is not None:
        data = tools.search_tickets(**filters)
        return {
            "kind": "search_results",
            "data": {"tickets": data, "filters": {k: v for k, v in filters.items() if v}},
            "sources": [t["ticket_id"] for t in data],
        }

    return {"kind": "unknown", "data": None, "sources": []}


def _extract_search_filters(question: str) -> Optional[dict]:
    """Detect plain searches like 'high priority network tickets assigned to Alex'."""
    lower = question.lower()
    if not _any(lower, ["ticket", "incident", "issue", "case"]):
        return None

    status = priority = category = assignee = None
    if _any(lower, ["open"]) and ("status" in lower or "open only" in lower):
        status = "Open"
    for candidate in VALID_PRIORITIES:
        if candidate.lower() in lower:
            priority = candidate
            break
    for candidate in VALID_CATEGORIES:
        if candidate.lower() in lower:
            category = candidate
            break
    if priority is None and category is None:
        return None

    match = re.search(r"assigned to ([\w@.-]+)", lower)
    if match:
        assignee = match.group(1)

    return {
        "status": status,
        "priority": priority,
        "category": category,
        "assignee": assignee,
        "limit": 15,
    }


def _any(text: str, keywords) -> bool:
    return any(word in text for word in keywords)


# ── LLM tool selection (validated strictly) ──────────────────────────────────

def _llm_pick_tool(config: LLMConfig, history: list, question: str):
    tool_catalog = json.dumps(tools.TOOL_SPECS, indent=2)
    messages = [
        {"role": "system", "content": (
            "You coordinate read-only tools for an incident-management copilot.\n"
            "Respond with STRICT JSON only, no prose or code fences, in either form:\n"
            '{"tool": "<name>", "args": {...}}\n'
            '{"tool": "none", "answer_text": "<short direct answer>"}}\n'
            "Allowed tools and arg shapes:\n" + tool_catalog
        )},
        *history,
        {"role": "user", "content": question},
    ]
    raw = llm.chat(config, messages, max_tokens=300)
    # Strip accidental markdown fences.
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    parsed = json.loads(raw)
    tool = parsed.get("tool")
    if tool in (None, "none"):
        return None, None

    names = {spec["tool"] for spec in tools.TOOL_SPECS}
    if tool not in names:
        raise ValueError(f"Model requested a tool that is not allowed: {tool}")

    args = parsed.get("args") or {}
    if not isinstance(args, dict):
        raise ValueError("Tool args must be a JSON object")
    args = {k: v for k, v in args.items() if isinstance(v, (str, int, float))}
    return tool, args


def _compose_reply(config, question, facts, history, allow_tool_round: bool):
    block = json.dumps(
        {"intended_answer_kind": facts["kind"], "facts": facts.get("data")}, indent=2, default=str
    )
    context = f"DATA FROM THE APPLICATION (authoritative):\n{block}"

    prompt = (
        "Write the final answer to the user question using only the data above.\n"
        "Rules:\n"
        "- Cite supporting ticket IDs inline where a statement depends on them.\n"
        "- Troubleshooting ideas, causes and patterns must be labeled as "
        "recommendations or inferences, not verified facts.\n"
        "- Do not invent data. If the facts are empty, say so."
    )
    messages = [
        {"role": "system", "content": SYSTEM_RULES},
        *history,
        {"role": "user", "content": f"{context}\n\n{prompt}\n\nUSER QUESTION: {question}"},
    ]
    try:
        return llm.chat(config, messages, max_tokens=900)
    except (LLMUnavailableError, ValueError):
        return None


# ── Deterministic formatting ─────────────────────────────────────────────────

def _render_facts(facts: dict) -> str:
    kind = facts["kind"]
    data = facts.get("data")

    if kind == "ticket_not_found":
        return f"I could not find a ticket with ID **{data}** in the database. Double-check the ID (format: `INC-1234`)."

    if kind == "ticket_detail":
        return _render_ticket_detail(data)

    if kind == "similar_to_ticket":
        lines = [
            f"Tickets semantically similar to **{data['ticket']['ticket_id']}** "
            f"(· {data['ticket']['title']}) — ranked by vector similarity:"
        ]
        lines.extend(_render_ticket_lines(data["similar"]))
        return "\n".join(lines)

    if kind == "troubleshooting":
        recs = data["recommendations"]
        if not recs:
            return (
                f"No resolution notes exist for tickets similar to "
                f"**{data['ticket']['ticket_id']}**, so I can't derive troubleshooting "
                "steps from real past resolutions."
            )
        lines = [
            f"**Recommendations for {data['ticket']['ticket_id']}** — these are "
            "*suggestions inferred from resolution notes of similar past tickets*, "
            "not verified fixes:"
        ]
        for rec in recs:
            lines.append(f"\n**Recommendation:** consider actions resembling {rec['ticket_id']} — *{rec['title']}* ({rec['status']})")
            lines.append(f"> {rec['resolution_notes']}")
        return "\n".join(lines)

    if kind == "longest_open":
        lines = ["Tickets that have been **open/in progress the longest** (from the ticket database):"]
        lines.extend(_render_ticket_lines(data))
        return "\n".join(lines)

    if kind == "patterns":
        if not data:
            return "No repeated incident patterns found in the ticket database."
        lines = ["Repeated incident patterns (same server + category, from stored tickets):"]
        for pattern in data:
            ids = ", ".join(t["ticket_id"] for t in pattern["tickets"])
            lines.append(
                f"- **{pattern['affected_server']}** ({pattern['category']}) — "
                f"{pattern['incident_count']} incidents ({ids})"
            )
        lines.append("*These are counts of stored tickets; root causes are an inference, not verified facts.*")
        return "\n".join(lines)

    if kind == "summary":
        s = data
        lines = [
            f"**Ticket summary** — {s['total']} tickets total.",
            "",
            "By status: " + ", ".join(f"{k}: {v}" for k, v in sorted(s["by_status"].items())),
            "By priority: " + ", ".join(f"{k}: {v}" for k, v in sorted(s["by_priority"].items())),
            "Most common categories: " + ", ".join(
                f"{k}: {v}" for k, v in sorted(s["by_category"].items(), key=lambda x: -x[1])[:5]
            ),
            f"Currently open or in progress: {s['open_count']} "
            f"(critical: {s['critical_open_count']})",
        ]
        return "\n".join(lines)

    if kind == "search_results":
        tickets = data["tickets"]
        filters = data.get("filters") or {}
        filter_text = ", ".join(f"{k}: {v}" for k, v in filters.items()) or "no filters"
        if not tickets:
            return f"No tickets match these filters ({filter_text})."
        if len(tickets) == 1 and "title" in tickets[0] and "description" in tickets[0]:
            return _render_ticket_detail(tickets[0])
        lines = [f"{len(tickets)} ticket(s) matching {filter_text}:"]
        lines.extend(_render_ticket_lines(tickets))
        return "\n".join(lines)

    return facts.get("ai_note") or "No data available for this question."


def _render_ticket_lines(tickets: list) -> list:
    lines = []
    for t in tickets:
        assignee = f" · 👤 {t['assignee']}" if t.get("assignee") else ""
        server = f" · 🖥️ {t['affected_server']}" if t.get("affected_server") else ""
        lines.append(
            f"- **{t['ticket_id']}** — {t['title']} "
            f"({t['priority']}, {t['status']}, {t['category']}{server}{assignee})"
        )
    return lines


def _render_ticket_detail(ticket: dict) -> str:
    lines = [
        f"### {ticket['ticket_id']} — {ticket['title']}",
        f"**Status:** {ticket['status']} · **Priority:** {ticket['priority']} · "
        f"**Category:** {ticket['category']}",
    ]
    if ticket.get("affected_server"):
        lines.append(f"**Affected server:** {ticket['affected_server']}")
    if ticket.get("assignee"):
        lines.append(f"**Assignee:** {ticket['assignee']}")
    lines.append(f"**Created:** {ticket.get('created_at') or '—'}")
    lines.append(f"\n{ticket.get('description') or ''}")
    if ticket.get("resolution_notes"):
        lines.append(f"\n**Resolution notes:** {ticket['resolution_notes']}")
    return "\n".join(lines)


def _sources_from_result(tool: str, result) -> list:
    ids: list = []
    try:
        if tool == "get_ticket" and result:
            ids.append(result["ticket_id"])
        elif tool == "get_ticket_summary":
            pass
        elif tool == "search_tickets" and result:
            ids = [t["ticket_id"] for t in result]
        elif tool == "find_similar_tickets" and result:
            ids = [t["ticket_id"] for t in result]
        elif tool == "find_similar_to_ticket" and result:
            ids = [result["ticket"]["ticket_id"]] + [s["ticket_id"] for s in result["similar"]]
        elif tool == "get_longest_open_tickets" and result:
            ids = [t["ticket_id"] for t in result]
        elif tool == "find_recurring_patterns" and result:
            ids = [t["ticket_id"] for p in result for t in p["tickets"]]
        elif tool == "suggest_troubleshooting" and result:
            ids = [result["ticket"]["ticket_id"]] + [r["ticket_id"] for r in result["recommendations"]]
    except (KeyError, TypeError):
        pass
    return ids


def _sanitize_history(history: Optional[list]) -> list:
    if not history:
        return []
    sanitized = []
    for item in history[-HISTORY_MAX_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        content = content.strip()[:2000]
        if content:
            sanitized.append({"role": role, "content": content})
    return sanitized
