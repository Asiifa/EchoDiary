"""Database connection and session management using SQLAlchemy."""
import json
import uuid
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from app.config import Config

Base = declarative_base()

_engine = None
_SessionFactory = None


def get_engine(db_url: str = None):
    """Retrieve or create the SQLAlchemy engine with SQLite pragmas."""
    global _engine
    if _engine is None or db_url is not None:
        url = db_url or Config.DATABASE_URL
        # Ensure directories exist
        if "sqlite:///" in url:
            db_path = url.replace("sqlite:///", "")
            import os
            from pathlib import Path
            if db_path != ":memory:":
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        _engine = create_engine(
            url,
            connect_args={"check_same_thread": False} if "sqlite" in url else {},
            echo=False,
        )
    return _engine


def get_session_factory(db_url: str = None):
    """Retrieve or initialize the session maker."""
    global _SessionFactory
    engine = get_engine(db_url)
    if _SessionFactory is None or db_url is not None:
        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionFactory


def init_db(db_url: str = None) -> None:
    """Create tables and safely attach legacy recordings and tasks to diary days."""
    import app.models  # Ensure every ORM model is registered before create_all.

    Config.ensure_directories()
    engine = get_engine(db_url)
    Base.metadata.create_all(bind=engine)
    _migrate_diary_days(engine)


def _migrate_diary_days(engine) -> None:
    """Backfill date-level rows and nullable foreign keys for existing SQLite data."""
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as connection:
        tables = inspect(connection).get_table_names()
        if "diary_entries" not in tables or "diary_days" not in tables:
            return

        entry_columns = {
            column["name"] for column in inspect(connection).get_columns("diary_entries")
        }
        task_columns = (
            {column["name"] for column in inspect(connection).get_columns("tasks")}
            if "tasks" in tables
            else set()
        )
        if "diary_day_id" not in entry_columns:
            connection.execute(text(
                "ALTER TABLE diary_entries ADD COLUMN diary_day_id "
                "VARCHAR(36) REFERENCES diary_days(id)"
            ))
        if "tasks" in tables and "diary_day_id" not in task_columns:
            connection.execute(text(
                "ALTER TABLE tasks ADD COLUMN diary_day_id "
                "VARCHAR(36) REFERENCES diary_days(id)"
            ))

        dates = connection.execute(
            text("SELECT DISTINCT entry_date FROM diary_entries")
        ).scalars().all()
        for entry_date in dates:
            day_id = connection.execute(
                text("SELECT id FROM diary_days WHERE entry_date = :entry_date"),
                {"entry_date": entry_date},
            ).scalar_one_or_none()
            if day_id is None:
                day_id = str(uuid.uuid4())
                connection.execute(
                    text(
                        "INSERT INTO diary_days ("
                        "id, entry_date, recurring_topics_json, new_developments_json, "
                        "completed_items_json, outstanding_items_json, analysis_task_ids_json"
                        ") VALUES ("
                        ":id, :entry_date, '[]', '[]', '[]', '[]', '[]'"
                        ")"
                    ),
                    {"id": day_id, "entry_date": entry_date},
                )
            connection.execute(
                text(
                    "UPDATE diary_entries SET diary_day_id = :day_id "
                    "WHERE entry_date = :entry_date AND diary_day_id IS NULL"
                ),
                {"day_id": day_id, "entry_date": entry_date},
            )

        if "tasks" in tables:
            connection.execute(text(
                "UPDATE tasks SET diary_day_id = ("
                "SELECT diary_entries.diary_day_id FROM diary_entries "
                "WHERE diary_entries.id = tasks.diary_entry_id"
                ") WHERE diary_day_id IS NULL AND diary_entry_id IS NOT NULL"
            ))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_tasks_diary_day_id ON tasks (diary_day_id)"
            ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_diary_entries_diary_day_id "
            "ON diary_entries (diary_day_id)"
        ))


@contextmanager
def get_db_session(db_url: str = None) -> Generator[Session, None, None]:
    """Context manager for safe database session lifecycle."""
    session_maker = get_session_factory(db_url)
    session: Session = session_maker()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
