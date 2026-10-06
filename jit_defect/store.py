"""Portable relational schema; SQLite is the validated local default."""

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    provenance: Mapped[str] = mapped_column(Text)
    label_policy: Mapped[str] = mapped_column(Text)
    source_sha256: Mapped[str] = mapped_column(String(64), index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean)
    row_count: Mapped[int] = mapped_column(Integer)
    labeled_count: Mapped[int] = mapped_column(Integer)
    positive_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Commit(Base):
    __tablename__ = "commits"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), primary_key=True)
    commit_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    label: Mapped[int | None] = mapped_column(Integer, nullable=True)
    features: Mapped[dict] = mapped_column(JSON)
    message: Mapped[str] = mapped_column(Text)


class Model(Base):
    __tablename__ = "registered_models"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    model_metadata: Mapped[dict] = mapped_column("metadata", JSON)
    metrics: Mapped[dict] = mapped_column(JSON)
    test_predictions: Mapped[list] = mapped_column(JSON)
    artifact_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Prediction(Base):
    __tablename__ = "predictions"
    model_id: Mapped[str] = mapped_column(
        ForeignKey("registered_models.id"), primary_key=True
    )
    commit_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    probability: Mapped[float]
    scope: Mapped[str] = mapped_column(String(16), index=True)


class Store:
    def __init__(self, data_dir: Path, database_url: str | None = None):
        self.data_dir = Path(data_dir).resolve()
        self.models_dir = self.data_dir / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        url = database_url or f"sqlite:///{(self.data_dir / 'jit.sqlite3').as_posix()}"
        self.engine = create_engine(
            url,
            connect_args={"check_same_thread": False}
            if url.startswith("sqlite:")
            else {},
        )
        if url.startswith("sqlite:"):

            @event.listens_for(self.engine, "connect")
            def configure_sqlite(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(self.engine, expire_on_commit=False)

    def artifact(self, model_id):
        return self.models_dir / f"{model_id}.joblib"
