"""Tests for the read-only database tools (SQLite as source of truth)."""
from src.copilot import tools


def test_get_ticket_summary_returns_real_counts(db_session):
    session, _ = db_session
    db_total = session.query(tools.Ticket).count()

    summary = tools.get_ticket_summary(session)

    assert summary["total"] == db_total
    assert sum(summary["by_status"].values()) == db_total
    assert sum(summary["by_priority"].values()) == db_total
    assert sum(summary["by_category"].values()) == db_total
    assert set(summary) == {
        "total", "by_status", "by_priority", "by_category",
        "open_count", "critical_open_count",
    }


def test_search_tickets_filters_by_priority_status_category(make_ticket):
    t1 = make_ticket(priority="High", status="Open", category="Network")
    t2 = make_ticket(priority="Critical", status="Open", category="Network")
    make_ticket(priority="Low", status="Resolved", category="Database")

    results = tools.search_tickets(status="Open", category="network")

    ids = {t["ticket_id"] for t in results}
    assert t1.ticket_id in ids and t2.ticket_id in ids
    assert all(t["status"] == "Open" for t in results)
    assert all(t["category"] == "Network" for t in results)

    high_only = tools.search_tickets(status="Open", priority="high")
    assert {t["ticket_id"] for t in high_only} & {t1.ticket_id, t2.ticket_id} == {t1.ticket_id}
    resolved_only = tools.search_tickets(status="Resolved", category="Database")
    assert all(t["status"] == "Resolved" and t["category"] == "Database" for t in resolved_only)


def test_search_tickets_filters_by_assignee_substring(make_ticket):
    mine = make_ticket(assignee="Test Runner Xavier")
    make_ticket(assignee="Someone Else")

    results = tools.search_tickets(assignee="runner xavier")

    assert [t["ticket_id"] for t in results] == [mine.ticket_id]


def test_get_ticket_returns_full_details(make_ticket):
    ticket = make_ticket(
        description="Detailed description for retrieval.",
        resolution_notes="Fixed by restarting the test service.",
        status="Resolved",
    )

    fetched = tools.get_ticket(ticket.ticket_id)

    assert fetched["ticket_id"] == ticket.ticket_id
    assert fetched["description"] == "Detailed description for retrieval."
    assert fetched["resolution_notes"] == "Fixed by restarting the test service."
    assert "created_at" in fetched and "updated_at" in fetched


def test_get_ticket_rejects_unknown_or_malformed_ids():
    assert tools.get_ticket("INC-99999999") is None
    assert tools.get_ticket("nope") is None
    assert tools.get_ticket("") is None


def test_get_longest_open_tickets_oldest_first(make_ticket):
    import datetime as dt

    now = dt.datetime.utcnow()
    newer = make_ticket(status="In Progress", created_at=now - dt.timedelta(days=150))
    older = make_ticket(status="Open", created_at=now - dt.timedelta(days=200))

    results = tools.get_longest_open_tickets(limit=50)

    ids = [t["ticket_id"] for t in results]
    assert older.ticket_id in ids and newer.ticket_id in ids
    assert ids.index(older.ticket_id) < ids.index(newer.ticket_id)
    assert all(t["status"] in ("Open", "In Progress") for t in results)


def test_find_recurring_patterns_groups_by_server_and_category(make_ticket):
    a = make_ticket(affected_server="dup-host-01", category="Database")
    b = make_ticket(affected_server="dup-host-01", category="Database")
    make_ticket(affected_server="solo-host-01", category="Network")

    patterns = tools.find_recurring_patterns(limit=50)

    checked = [p for p in patterns if p["affected_server"] == "dup-host-01"]
    assert checked, "expected a repeated pattern on dup-host-01"
    pattern = checked[0]
    assert pattern["category"] == "Database"
    assert pattern["incident_count"] >= 2
    ids = {t["ticket_id"] for t in pattern["tickets"]}
    assert a.ticket_id in ids and b.ticket_id in ids


def test_recommend_troubleshooting_uses_real_resolution_notes(
    make_ticket, indexed_ticket
):

    target = make_ticket(
        title="Database connection pool exhausted on prod",
        description="Cannot connect, pool saturation at 100%, connection timeouts everywhere.",
    )
    resolved = indexed_ticket(
        title="Database connection pool exhausted",
        description="Pool saturation at 100% with client wait times above 30 seconds.",
        status="Resolved",
        resolution_notes="Killed stale connections and patched the connection leak in the reporting service.",
    )
    indexed_ticket(
        title="Brand new laptop provisioning request",
        description="A new employee needs a laptop provisioned for onboarding next week.",
        status="Open",
    )

    result = tools.recommend_troubleshooting(target.ticket_id, limit=5)

    assert result["ticket"]["ticket_id"] == target.ticket_id
    assert result["recommendations"], "expected at least one recommendation from the resolved similar ticket"
    for rec in result["recommendations"]:
        assert rec["resolution_notes"].strip(), "suggestions must carry real resolution notes"
        assert rec["status"] in ("Resolved", "Closed")


def test_parse_tool_args_ignores_invalid_enum_values():
    summary = tools.parse_tool_args("get_ticket_summary", {})
    assert isinstance(summary, dict)

    results = tools.parse_tool_args(
        "search_tickets", {"status": "Nonsense", "priority": "critical"}
    )
    assert all(t["priority"] == "Critical" for t in results)


def test_parse_tool_args_rejects_unknown_tools():
    try:
        tools.parse_tool_args("delete_all_tickets", {})
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
