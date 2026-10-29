"""Full reindex of SQLite tickets into the ChromaDB `it_incidents` collection.

Run from the project root:

    python -m src.ingestion.sync_index

How synchronization works
-------------------------
- SQLite (`it_ops.db`) is the authoritative source.
- ChromaDB documents use the stable, human ticket_id (`INC-1234`) as the
  vector ID, and every write is an UPSERT — so reindexing never duplicates
  vectors and updates replace stale documents/metadata in place.
- This CLI also removes orphan vectors whose ticket no longer exists in
  SQLite (e.g. a DB row deleted while the vector store was offline).
- During normal operation, the FastAPI ticket endpoints call the same
  upsert/remove helpers, so single-ticket changes stay synchronized
  automatically; this CLI is for bootstrap and repair.
"""
from src.database.db import SessionLocal
from src.models.ticket import Ticket
from src.vector_store.chroma_db import collection, index_ticket


def reindex_all() -> dict:
    session = SessionLocal()
    try:
        all_tickets = session.query(Ticket).all()
    finally:
        session.close()

    live_ids = {ticket.ticket_id for ticket in all_tickets}

    upserted = 0
    errors = []
    for ticket in all_tickets:
        try:
            index_ticket(ticket)
            upserted += 1
        except Exception as exc:
            errors.append(f"{ticket.ticket_id}: {exc}")

    # Drop vectors for tickets that no longer exist in SQLite.
    vector_ids = set(collection.get(include=[]).get("ids", []))
    orphans = sorted(vector_ids - live_ids)
    removed = 0
    if orphans:
        collection.delete(ids=orphans)
        removed = len(orphans)

    return {
        "sqlite_count": len(all_tickets),
        "chroma_count": collection.count(),
        "upserted": upserted,
        "removed_orphans": removed,
        "errors": errors,
    }


def main():
    report = reindex_all()
    print()
    print("=" * 60)
    print("IT OPS COPILOT - VECTOR INDEX SYNC")
    print("=" * 60)
    print(f"Tickets in SQLite            : {report['sqlite_count']}")
    print(f"Documents in ChromaDB        : {report['chroma_count']}")
    print(f"Tickets upserted this run    : {report['upserted']}")
    print(f"Orphan vectors removed       : {report['removed_orphans']}")
    print(f"Errors                       : {len(report['errors'])}")
    if report["errors"]:
        for error in report["errors"]:
            print(f"  ERROR: {error}")
    print()
    print("It is safe to run this repeatedly; indexing is idempotent.")


if __name__ == "__main__":
    main()
