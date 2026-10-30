"""Read-only ticket tools for the IT Ops Copilot agent.

SQLite (via the existing SQLAlchemy model) is the authoritative source for all
structured ticket data. ChromaDB is used only for semantic retrieval; every
result is re-validated against SQLite before being shown to the user, so the
agent never reports incidents or IDs that are not backed by stored data.

Every function is read-only and parameterized — the LLM never executes SQL,
shell commands, or arbitrary Python; it can only request one of these
predefined functions with validated arguments.
"""
import re
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database.db import SessionLocal
from src.models.ticket import Ticket
from src.vector_store.chroma_db import collection

VALID_STATUSES = ["Open", "In Progress", "Resolved", "Closed"]
VALID_PRIORITIES = ["Low", "Medium", "High", "Critical"]
VALID_CATEGORIES = [
    "Infrastructure",
    "Application",
    "Database",
    "Network",
    "Security",
    "Performance",
    "Other",
]

# Ticket IDs look like `INC-1234` (the app auto-generates them). Accept any
# letters-digits prefix of the same shape so test/other pipelines work too.
TICKET_ID_RE = re.compile(r"^\s*[A-Z]{2,10}-\d+\s*$", re.IGNORECASE)

MAX_SIMILAR_LIMIT = 10


def ticket_to_brief(ticket: Ticket) -> dict:
    return {
        "ticket_id": ticket.ticket_id,
        "title": ticket.title,
        "category": ticket.category,
        "priority": ticket.priority,
        "status": ticket.status,
        "affected_server": ticket.affected_server,
        "assignee": ticket.assignee,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
    }


def ticket_to_full(ticket: Ticket) -> dict:
    data = ticket_to_brief(ticket)
    data.update(
        {
            "description": ticket.description,
            "resolution_notes": ticket.resolution_notes,
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        }
    )
    return data


def _collection_for(collection_override=None):
    return collection_override if collection_override is not None else collection


def get_ticket_summary(session: Optional[Session] = None) -> dict:
    """Counts of tickets broken down by status, priority, and category."""
    own_session = False
    if session is None:
        session = SessionLocal()
        own_session = True
    try:
        tickets = session.query(Ticket).all()
        summary = {
            "total": len(tickets),
            "by_status": {},
            "by_priority": {},
            "by_category": {},
            "open_count": 0,
            "critical_open_count": 0,
        }
        for ticket in tickets:
            summary["by_status"][ticket.status] = summary["by_status"].get(ticket.status, 0) + 1
            summary["by_priority"][ticket.priority] = (
                summary["by_priority"].get(ticket.priority, 0) + 1
            )
            summary["by_category"][ticket.category] = (
                summary["by_category"].get(ticket.category, 0) + 1
            )
            if ticket.status in ("Open", "In Progress"):
                summary["open_count"] += 1
                if ticket.priority == "Critical":
                    summary["critical_open_count"] += 1
        return summary
    finally:
        if own_session:
            session.close()


def search_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    assignee: Optional[str] = None,
    limit: int = 15,
    session: Optional[Session] = None,
) -> list:
    """Filter tickets by validated status/priority/category and assignee name."""
    own_session = False
    if session is None:
        session = SessionLocal()
        own_session = True
    try:
        query = session.query(Ticket).order_by(Ticket.created_at.desc())
        if status:
            query = query.filter(func.lower(Ticket.status) == status.strip().lower())
        if priority:
            query = query.filter(func.lower(Ticket.priority) == priority.strip().lower())
        if category:
            query = query.filter(func.lower(Ticket.category) == category.strip().lower())
        if assignee:
            query = query.filter(Ticket.assignee.ilike(f"%{assignee.strip()}%"))

        tickets = query.limit(min(int(limit), 50)).all()
        return [ticket_to_brief(t) for t in tickets]
    finally:
        if own_session:
            session.close()


def get_ticket(ticket_id: str, session: Optional[Session] = None) -> Optional[dict]:
    """Full details of a single ticket, or None when the ID is unknown."""
    clean = (ticket_id or "").strip().upper()
    if not TICKET_ID_RE.match(clean):
        return None

    own_session = False
    if session is None:
        session = SessionLocal()
        own_session = True
    try:
        ticket = session.query(Ticket).filter(Ticket.ticket_id == clean).first()
        return ticket_to_full(ticket) if ticket else None
    finally:
        if own_session:
            session.close()


def get_longest_open_tickets(limit: int = 5, session: Optional[Session] = None) -> list:
    """Tickets still being worked on, oldest first."""
    own_session = False
    if session is None:
        session = SessionLocal()
        own_session = True
    try:
        tickets = (
            session.query(Ticket)
            .filter(Ticket.status.in_(["Open", "In Progress"]))
            .order_by(Ticket.created_at.asc())
            .limit(min(int(limit), 20))
            .all()
        )
        return [ticket_to_brief(t) for t in tickets]
    finally:
        if own_session:
            session.close()


def _query_similar(query_text: str, limit: int, collection_override=None) -> list:
    """Raw ChromaDB similarity query returning ordered ticket_id strings."""
    chroma = _collection_for(collection_override)
    count = int(chroma.count() or 0)
    if count == 0 or not (query_text or "").strip():
        return []
    results = chroma.query(query_texts=[query_text], n_results=min(count, limit))
    ids = (results.get("ids") or [[]])[0]
    return [str(i) for i in ids if i]


def find_similar_tickets(
    query_text: str,
    limit: int = 5,
    session: Optional[Session] = None,
    collection_override=None,
) -> list:
    """Tickets semantically similar to a free-text description (SQLite-verified)."""
    limit = max(1, min(int(limit), MAX_SIMILAR_LIMIT))
    ids = _query_similar(query_text[:500], limit, collection_override)
    if not ids:
        return []

    own_session = False
    if session is None:
        session = SessionLocal()
        own_session = True
    try:
        tickets = (
            session.query(Ticket)
            .filter(Ticket.ticket_id.in_(ids))
            .all()
        )
        order = {tid: rank for rank, tid in enumerate(ids)}
        ordered = sorted(tickets, key=lambda t: order.get(t.ticket_id, len(order)))
        return [
            {
                "ticket_id": t.ticket_id,
                "title": t.title,
                "category": t.category,
                "priority": t.priority,
                "status": t.status,
                "affected_server": t.affected_server,
                "score_rank": position + 1,
            }
            for position, t in enumerate(ordered)
        ]
    finally:
        if own_session:
            session.close()


def find_similar_to_ticket(
    ticket_id: str,
    limit: int = 5,
    session: Optional[Session] = None,
    collection_override=None,
) -> dict:
    """Tickets most similar to an existing ticket (by its indexed text)."""
    ticket = get_ticket(ticket_id, session)
    if ticket is None:
        return {"ticket": None, "similar": []}

    query_text = (
        f"{ticket['title']} {ticket['description']} category: {ticket['category']} "
        f"server: {ticket.get('affected_server') or 'unspecified'}"
    )
    similar = find_similar_tickets(query_text, limit, session, collection_override)
    similar = [
        s for s in similar if s["ticket_id"] != ticket["ticket_id"]
    ][:limit]
    return {"ticket": ticket, "similar": similar}


def find_recurring_patterns(limit: int = 8, session: Optional[Session] = None) -> list:
    """Category/server combinations with repeated incidents (from real data)."""
    own_session = False
    if session is None:
        session = SessionLocal()
        own_session = True
    try:
        grouped = (
            session.query(
                Ticket.affected_server,
                Ticket.category,
                func.count(Ticket.ticket_id),
            )
            .filter(Ticket.affected_server.isnot(None))
            .group_by(Ticket.affected_server, Ticket.category)
            .having(func.count(Ticket.ticket_id) >= 2)
            .order_by(func.count(Ticket.ticket_id).desc())
            .limit(max(1, min(int(limit), 50)))
            .all()
        )

        patterns = []
        for server, category, count in grouped:
            ids = (
                session.query(Ticket.ticket_id, Ticket.title, Ticket.status)
                .filter(
                    Ticket.affected_server == server,
                    Ticket.category == category,
                )
                .order_by(Ticket.created_at.desc())
                .all()
            )
            patterns.append(
                {
                    "affected_server": server,
                    "category": category,
                    "incident_count": int(count),
                    "tickets": [
                        {"ticket_id": tid, "title": title, "status": status}
                        for tid, title, status in ids
                    ],
                }
            )
        return patterns
    finally:
        if own_session:
            session.close()


def recommend_troubleshooting(
    ticket_id: str,
    limit: int = 5,
    session: Optional[Session] = None,
    collection_override=None,
) -> dict:
    """Troubleshooting ideas derived ONLY from real resolution notes of
    historically similar tickets. Returned data is explicitly labeled as
    recommendations, never as verified facts.

    Returns {"ticket": <ticket or None>, "recommendations": [...]} where each
    recommendation carries the supporting ticket ID and its actual resolution
    notes copied verbatim from SQLite.
    """
    similar = find_similar_to_ticket(ticket_id, limit, session, collection_override)
    if similar["ticket"] is None:
        return {"ticket": None, "recommendations": []}

    ids = [s["ticket_id"] for s in similar["similar"]]
    recommendations = []
    if ids:
        own_session = False
        if session is None:
            session = SessionLocal()
            own_session = True
        try:
            resolved_rows = (
                session.query(Ticket)
                .filter(
                    Ticket.ticket_id.in_(ids),
                    Ticket.status.in_(["Resolved", "Closed"]),
                    Ticket.resolution_notes.isnot(None),
                )
                .order_by(Ticket.updated_at.desc())
                .all()
            )
            for row in resolved_rows:
                recommendations.append(
                    {
                        "ticket_id": row.ticket_id,
                        "title": row.title,
                        "status": row.status,
                        "resolution_notes": row.resolution_notes,
                    }
                )
        finally:
            if own_session:
                session.close()

    return {"ticket": similar["ticket"], "recommendations": recommendations, "similar": similar["similar"]}


# Predefined tool registry exposed to the LLM. Only these (validated, read-only)
# functions can be invoked by the agent.
TOOL_SPECS = [
    {
        "tool": "get_ticket_summary",
        "description": "Counts of tickets by status, priority, and category.",
        "args": {},
    },
    {
        "tool": "search_tickets",
        "description": "Search tickets with optional filters.",
        "args": {
            "status": "Open | In Progress | Resolved | Closed (optional)",
            "priority": "Low | Medium | High | Critical (optional)",
            "category": "Infrastructure | Application | Database | Network | Security | Performance | Other (optional)",
            "assignee": "partial assignee name (optional)",
            "limit": "int 1-20 (optional)",
        },
    },
    {
        "tool": "get_ticket",
        "description": "Details of one ticket by ID, e.g. INC-1001.",
        "args": {"ticket_id": "INC-####"},
    },
    {
        "tool": "find_similar_tickets",
        "description": "Tickets similar to a free-text incident description.",
        "args": {"query": "text", "limit": "int 1-10 (optional)"},
    },
    {
        "tool": "find_similar_to_ticket",
        "description": "Tickets similar to an existing ticket ID.",
        "args": {"ticket_id": "INC-####", "limit": "int 1-10 (optional)"},
    },
    {
        "tool": "find_recurring_patterns",
        "description": "Servers/categories with repeated incidents.",
        "args": {"limit": "int 1-50 (optional)"},
    },
    {
        "tool": "suggest_troubleshooting",
        "description": "Recommendations drawn from resolution notes of similar past tickets.",
        "args": {"ticket_id": "INC-####"},
    },
]


def parse_tool_args(tool: str, args: dict, session: Optional[Session] = None):
    """Execute a validated predefined tool. Only whitelisted tools run here."""
    args = args or {}
    if tool == "get_ticket_summary":
        return get_ticket_summary(session)
    if tool == "search_tickets":
        return search_tickets(
            status=_validate_enum(args.get("status"), VALID_STATUSES),
            priority=_validate_enum(args.get("priority"), VALID_PRIORITIES),
            category=_validate_enum(args.get("category"), VALID_CATEGORIES),
            assignee=_clean_str(args.get("assignee"), 100),
            limit=_validate_limit(args.get("limit"), default=15, maximum=20),
            session=session,
        )
    if tool == "get_ticket":
        return get_ticket(_clean_str(args.get("ticket_id"), 20) or "", session)
    if tool == "find_similar_tickets":
        return find_similar_tickets(
            _clean_str(args.get("query"), 500) or "",
            _validate_limit(args.get("limit"), default=5, maximum=MAX_SIMILAR_LIMIT),
            session,
        )
    if tool == "find_similar_to_ticket":
        return find_similar_to_ticket(
            _clean_str(args.get("ticket_id"), 20) or "",
            _validate_limit(args.get("limit"), default=5, maximum=MAX_SIMILAR_LIMIT),
            session,
        )
    if tool == "get_longest_open_tickets":
        return get_longest_open_tickets(
            _validate_limit(args.get("limit"), default=5, maximum=20),
            session,
        )
    if tool == "find_recurring_patterns":
        return find_recurring_patterns(
            _validate_limit(args.get("limit"), default=8, maximum=50),
            session,
        )
    if tool == "suggest_troubleshooting":
        return recommend_troubleshooting(
            _clean_str(args.get("ticket_id"), 20) or "",
            _validate_limit(args.get("limit"), default=5, maximum=MAX_SIMILAR_LIMIT),
            session,
        )
    raise ValueError(f"Unknown tool: {tool}")


def _validate_enum(value, allowed) -> Optional[str]:
    if not value:
        return None
    value = str(value).strip().lower()
    for candidate in allowed:
        if candidate.lower() == value:
            return candidate
    return None


def _clean_str(value, max_length: int) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value[:max_length] if value else None


def _validate_limit(value, default: int, maximum: int) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(limit, maximum))
