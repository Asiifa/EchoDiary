"""Pytest fixtures and test environment setup."""
import os
import tempfile
import pytest
import numpy as np
import soundfile as sf
from datetime import date, datetime, timedelta
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.config import Config
from app.models.diary_entry import DiaryEntry
from app.models.task import Task
from app.schemas.analysis_schema import DailyAnalysisOutput, ExtractedTask
from app.schemas.weekly_schema import WeeklyDigestOutput


from sqlalchemy.pool import StaticPool

@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests and cleanup afterwards."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def test_db_session():
    """In-memory SQLite database session using StaticPool for clean isolated tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionTesting = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionTesting()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def sample_wav_file(temp_dir):
    """Generate a valid 2-second sine wave WAV file for testing."""
    file_path = temp_dir / "test_audio.wav"
    sr = 16000
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration), False)
    sine_wave = 0.5 * np.sin(2 * np.pi * 440 * t)
    sf.write(str(file_path), sine_wave.astype(np.float32), sr, subtype="PCM_16", format="WAV")
    return file_path


@pytest.fixture
def sample_transcript():
    """Sample student voice diary transcript for development and testing."""
    return (
        "Today was a productive day. In the morning I attended our database systems lecture "
        "and worked with Sarah on the group project assignment. We resolved the query indexing issue "
        "which made me feel very relieved and happy. I still need to submit the literature survey "
        "by Friday and schedule the team review meeting tomorrow."
    )


@pytest.fixture
def mock_daily_analysis():
    """Mock structured AI response."""
    return DailyAnalysisOutput(
        summary=[
            "Attended database systems lecture in the morning.",
            "Collaborated with Sarah to solve the project query indexing problem.",
            "Felt relieved and happy with project progress while preparing upcoming deliverables."
        ],
        primary_mood="Happy",
        secondary_mood="Calm",
        mood_confidence=0.9,
        mood_evidence="The speaker mentioned feeling very relieved and happy after solving the issue.",
        topics=["Database systems", "Group project", "Query indexing", "Coursework"],
        highlights=["Resolved the query indexing issue with Sarah"],
        tasks=[
            ExtractedTask(
                description="Submit the literature survey",
                due_date="2026-11-13",
                priority="High"
            ),
            ExtractedTask(
                description="Schedule the team review meeting",
                due_date=None,
                priority="Medium"
            )
        ]
    )
