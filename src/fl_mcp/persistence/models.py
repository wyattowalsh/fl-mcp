"""SQLModel persistence models."""

from sqlmodel import Field, SQLModel


class TransactionRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    transaction_id: str
    status: str


class CheckpointRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    checkpoint_id: str
    transaction_id: str
