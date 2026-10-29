import chromadb

client = chromadb.PersistentClient(
    path="data/chroma_db"
)

collection = client.get_or_create_collection(
    name="it_incidents"
)


def index_ticket(ticket, target_collection=None):
    """Upsert one ticket into the collection.

    Uses the stable ticket_id as the vector ID, so indexing the same ticket
    again (creation, update, or reindex) replaces its document instead of
    creating a duplicate. Pass ``target_collection`` to index into a different
    collection (defaults to the project's `it_incidents` collection).
    """
    chroma_collection = target_collection or collection

    document = f"""
    Title: {ticket.title}
    Description: {ticket.description}
    Category: {ticket.category}
    Priority: {ticket.priority}
    Status: {ticket.status}
    Affected Server: {ticket.affected_server or "Not specified"}
    Resolution Notes: {ticket.resolution_notes or "Not available"}
    """

    chroma_collection.upsert(
        ids=[ticket.ticket_id],
        documents=[document],
        metadatas=[
            {
                "ticket_id": ticket.ticket_id,
                "category": ticket.category,
                "priority": ticket.priority,
                "status": ticket.status,
            }
        ],
    )


def search_similar_tickets(query: str, limit: int = 5):
    results = collection.query(
        query_texts=[query],
        n_results=min(limit, collection.count()),
    )

    return results
