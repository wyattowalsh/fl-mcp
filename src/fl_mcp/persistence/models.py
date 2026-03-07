"""SQLModel persistence models."""

from typing import Optional

from sqlmodel import Field, SQLModel


class TransactionRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_id: str
    status: str


class CheckpointRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    checkpoint_id: str
    transaction_id: str
