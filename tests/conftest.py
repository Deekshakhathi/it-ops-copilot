"""Shared fixtures for copilot tests.

Tests reuse the project's existing SQLAlchemy model and SQLite engine (no
second database and no schema duplication). Ticket rows created by tests use
a unique `TST-` prefix so cleanup can remove exactly what was added, leaving
real data untouched.
"""
import shutil
import tempfile
import uuid
from pathlib import Path

import chromadb
import pytest

from src.database.db import SessionLocal, engine, Base
from src.models.ticket import Ticket


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    created_ids = []
    try:
        yield session, created_ids
    finally:
        session.rollback()
        if created_ids:
            session.query(Ticket).filter(Ticket.ticket_id.in_(created_ids)).delete(
                synchronize_session=False
            )
            session.commit()
        session.close()


@pytest.fixture()
def make_ticket(db_session):
    """Factory fixture: make_ticket(**fields) -> Ticket row.

    The factory tracks every row it inserts in the session fixture's cleanup
    list, so tests never need to (and cannot) forget to register a row.
    IDs use a random numeric base (format `INC-####`-style letters-digits so
    they satisfy ID validation) reserved for this test run, e.g. TST-43210.
    """
    session, created_ids = db_session
    counter = {"n": 0}
    run_base = 90000 + int(uuid.uuid4().hex[:4], 16) % 30000

    def _factory(**fields):
        counter["n"] += 1
        defaults = {
            "ticket_id": f"TST-{run_base + counter['n']}",
            "title": f"Test ticket {counter['n']}",
            "description": "Synthetic ticket created by the automated test suite.",
            "category": "Database",
            "priority": "High",
            "status": "Open",
            "affected_server": "test-db-host-01",
            "assignee": None,
            "resolution_notes": None,
        }
        defaults.update(fields)
        ticket = Ticket(**defaults)
        session.add(ticket)
        session.commit()
        session.refresh(ticket)
        created_ids.append(ticket.ticket_id)
        return ticket

    return _factory


@pytest.fixture()
def ephemeral_collection():
    """An isolated Chroma collection in a temp dir, so tests don't touch the
    project's real `it_incidents` collection."""
    tmpdir = tempfile.mkdtemp(prefix="copilot-test-chroma-")
    client = chromadb.PersistentClient(path=tmpdir)
    collection = client.get_or_create_collection(name="it_incidents_test")
    yield collection
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture()
def indexed_ticket(make_ticket):
    from src.vector_store.chroma_db import index_ticket

    def _make(**fields):
        ticket = make_ticket(**fields)
        index_ticket(ticket)
        return ticket

    return _make
