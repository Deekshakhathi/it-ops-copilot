from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.db import SessionLocal
from src.models.ticket import Ticket

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


class TicketCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3)
    category: Literal[
        "Infrastructure",
        "Application",
        "Database",
        "Network",
        "Security",
        "Performance",
        "Other",
    ]
    priority: Literal["Low", "Medium", "High", "Critical"] = "Medium"
    affected_server: Optional[str] = None
    assignee: Optional[str] = None


class TicketUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    description: Optional[str] = None
    category: Optional[Literal[
        "Infrastructure",
        "Application",
        "Database",
        "Network",
        "Security",
        "Performance",
        "Other",
    ]] = None
    priority: Optional[Literal["Low", "Medium", "High", "Critical"]] = None
    status: Optional[Literal["Open", "In Progress", "Resolved", "Closed"]] = None
    affected_server: Optional[str] = None
    assignee: Optional[str] = None
    resolution_notes: Optional[str] = None


def ticket_to_dict(ticket: Ticket):
    return {
        "ticket_id": ticket.ticket_id,
        "title": ticket.title,
        "description": ticket.description,
        "category": ticket.category,
        "priority": ticket.priority,
        "status": ticket.status,
        "affected_server": ticket.affected_server,
        "assignee": ticket.assignee,
        "resolution_notes": ticket.resolution_notes,
        "created_at": ticket.created_at.isoformat(),
        "updated_at": ticket.updated_at.isoformat(),
    }


@router.post("/", status_code=201)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
    last_ticket = (
        db.query(Ticket)
        .order_by(Ticket.id.desc())
        .first()
    )

    next_number = 1001 if last_ticket is None else last_ticket.id + 1001

    ticket = Ticket(
        ticket_id=f"INC-{next_number}",
        title=payload.title,
        description=payload.description,
        category=payload.category,
        priority=payload.priority,
        status="Open",
        affected_server=payload.affected_server,
        assignee=payload.assignee,
    )

    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return ticket_to_dict(ticket)


@router.get("/")
def list_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Ticket)

    if status:
        query = query.filter(Ticket.status == status)

    if priority:
        query = query.filter(Ticket.priority == priority)

    if category:
        query = query.filter(Ticket.category == category)

    tickets = query.order_by(Ticket.created_at.desc()).all()

    return [ticket_to_dict(ticket) for ticket in tickets]


@router.get("/{ticket_id}")
def get_ticket(ticket_id: str, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(
        Ticket.ticket_id == ticket_id
    ).first()

    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return ticket_to_dict(ticket)


@router.patch("/{ticket_id}")
def update_ticket(
    ticket_id: str,
    payload: TicketUpdate,
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(
        Ticket.ticket_id == ticket_id
    ).first()

    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    updates = payload.model_dump(exclude_unset=True)

    if updates.get("status") == "Resolved" and not updates.get(
        "resolution_notes", ticket.resolution_notes
    ):
        raise HTTPException(
            status_code=400,
            detail="Add resolution notes before resolving the ticket"
        )

    for field, value in updates.items():
        setattr(ticket, field, value)

    ticket.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(ticket)

    return ticket_to_dict(ticket)


@router.delete("/{ticket_id}", status_code=204)
def delete_ticket(ticket_id: str, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(
        Ticket.ticket_id == ticket_id
    ).first()

    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    db.delete(ticket)
    db.commit()
