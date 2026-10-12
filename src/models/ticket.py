from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from src.database.db import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)

    ticket_id = Column(
        String(20),
        unique=True,
        nullable=False,
        index=True
    )

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)

    category = Column(String(50), nullable=False)
    priority = Column(String(20), default="Medium", nullable=False)
    status = Column(String(20), default="Open", nullable=False)

    affected_server = Column(String(100), nullable=True)
    assignee = Column(String(100), nullable=True)

    resolution_notes = Column(Text, nullable=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
