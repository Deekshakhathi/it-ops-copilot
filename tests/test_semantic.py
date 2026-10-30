"""Tests for semantic retrieval: ChromaDB + SQLite verification."""
import pytest

from src.copilot import tools
from src.vector_store.chroma_db import index_ticket


def test_upsert_is_idempotent_no_duplicate_vectors(make_ticket, ephemeral_collection):
    ticket = make_ticket()

    index_ticket(ticket, target_collection=ephemeral_collection)
    index_ticket(ticket, target_collection=ephemeral_collection)

    assert ephemeral_collection.count() == 1
    assert set(ephemeral_collection.get(include=[]).get("ids", [])) == {ticket.ticket_id}


def test_search_similar_tickets_returns_matching_ticket_first(
    make_ticket, ephemeral_collection
):
    target_source = make_ticket(
        title="Database connection pool exhausted",
        description="Pool saturation at 100% with client wait times above 30 seconds.",
    )
    index_ticket(target_source, target_collection=ephemeral_collection)
    distractor = make_ticket(
        title="Cafeteria printer out of paper",
        description="The printer in the cafeteria needs a paper refill.",
    )
    index_ticket(distractor, target_collection=ephemeral_collection)

    results = tools.find_similar_tickets(
        "database connection pool exhausted timeouts",
        limit=2,
        collection_override=ephemeral_collection,
    )

    assert results, "expected at least one similar ticket"
    assert results[0]["ticket_id"] == target_source.ticket_id
    assert results[0]["score_rank"] == 1


def test_find_similar_tickets_returns_only_sqlite_backed_tickets(make_ticket, ephemeral_collection):
    ticket = make_ticket()
    index_ticket(ticket, target_collection=ephemeral_collection)

    # Inject an orphan vector that points to a ticket NOT present in SQLite.
    ephemeral_collection.upsert(
        ids=["TST-ORPHAN"],
        documents=["Title: ghost ticket from a stale index"],
        metadatas=[{"ticket_id": "TST-ORPHAN", "category": "Other"}],
    )

    results = tools.find_similar_tickets(
        ticket.title, limit=5, collection_override=ephemeral_collection
    )

    ids = {t["ticket_id"] for t in results}
    assert "TST-ORPHAN" not in ids, "orphan vector must not surface as a ticket"
    assert ticket.ticket_id in ids


def test_find_similar_to_ticket_excludes_itself(make_ticket, ephemeral_collection):
    ticket = make_ticket()
    index_ticket(ticket, target_collection=ephemeral_collection)

    result = tools.find_similar_to_ticket(
        ticket.ticket_id, limit=5, collection_override=ephemeral_collection
    )

    assert result["ticket"]["ticket_id"] == ticket.ticket_id
    assert ticket.ticket_id not in {s["ticket_id"] for s in result["similar"]}


def test_find_similar_to_ticket_unknown_id(make_ticket, ephemeral_collection):
    result = tools.find_similar_to_ticket(
        "INC-9876543", limit=5, collection_override=ephemeral_collection
    )
    assert result == {"ticket": None, "similar": []}


def test_empty_collection_returns_no_results(make_ticket, ephemeral_collection):
    results = tools.find_similar_tickets("anything", limit=5, collection_override=ephemeral_collection)
    assert results == []
