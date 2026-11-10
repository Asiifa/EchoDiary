"""Tests for structured AI analysis, Pydantic schemas, and Ollama integration."""
import pytest
from app.schemas.analysis_schema import DailyAnalysisOutput, ExtractedTask
from app.services.ollama_service import OllamaService, OllamaServiceError


def test_schema_exact_three_line_summary():
    """Verify summary validator guarantees exactly 3 lines."""
    # Test with 3 lines
    data_3 = {
        "summary": ["First line.", "Second line.", "Third line."],
        "primary_mood": "Happy",
        "mood_confidence": 0.85,
        "mood_evidence": "User described being happy.",
    }
    out_3 = DailyAnalysisOutput.model_validate(data_3)
    assert len(out_3.summary) == 3

    # Test with single multi-sentence string
    data_str = {
        "summary": "Attended morning classes. Finished coding lab. Rested at home.",
        "primary_mood": "Calm",
        "mood_confidence": 0.9,
        "mood_evidence": "Quiet evening.",
    }
    out_str = DailyAnalysisOutput.model_validate(data_str)
    assert len(out_str.summary) == 3

    # Test with >3 lines (should be trimmed to 3)
    data_4 = {
        "summary": ["One", "Two", "Three", "Four", "Five"],
        "primary_mood": "Excited",
        "mood_confidence": 0.95,
        "mood_evidence": "Excited words.",
    }
    out_4 = DailyAnalysisOutput.model_validate(data_4)
    assert len(out_4.summary) == 3


def test_schema_mood_normalization_and_confidence():
    """Verify primary and secondary moods are normalized to supported categories and confidence clamped."""
    data = {
        "summary": ["L1", "L2", "L3"],
        "primary_mood": "happy",  # lowercase
        "secondary_mood": "CALM",
        "mood_confidence": 95,   # percentage instead of decimal
        "mood_evidence": "Smiled while speaking.",
    }
    out = DailyAnalysisOutput.model_validate(data)
    assert out.primary_mood == "Happy"
    assert out.secondary_mood == "Calm"
    assert out.mood_confidence == 0.95

    # Unsupported mood should safely fallback to Neutral
    data_bad_mood = {
        "summary": ["L1", "L2", "L3"],
        "primary_mood": "Euphoric_Unknown",
        "mood_confidence": 1.5,
        "mood_evidence": "Evidence.",
    }
    out_bad = DailyAnalysisOutput.model_validate(data_bad_mood)
    assert out_bad.primary_mood == "Neutral"
    assert out_bad.mood_confidence == 1.0


def test_task_extraction_schema():
    """Verify actionable task validation and priority/date handling."""
    task_raw = {
        "description": "Finish literature review chapter",
        "due_date": "2026-11-15",
        "priority": "high",
    }
    task = ExtractedTask.model_validate(task_raw)
    assert task.description == "Finish literature review chapter"
    assert task.due_date == "2026-11-15"
    assert task.priority == "High"

    # Invalid due date should become None safely
    task_invalid_date = {
        "description": "Call teammates",
        "due_date": "by tomorrow",
        "priority": "unknown",
    }
    t2 = ExtractedTask.model_validate(task_invalid_date)
    assert t2.due_date is None
    assert t2.priority == "Medium"


def test_ollama_json_repair_and_extraction():
    """Test JSON block extraction from markdown and trailing comma repair."""
    service = OllamaService()

    raw_markdown = 'Here is the analysis:\n```json\n{"summary": ["A", "B", "C"], "primary_mood": "Calm", "mood_confidence": 0.8, "mood_evidence": "Tone was peaceful", "topics": ["Study",]}\n```'
    extracted = service._extract_json_block(raw_markdown)
    repaired = service._repair_json(extracted)

    import json
    parsed = json.loads(repaired)
    assert parsed["primary_mood"] == "Calm"
    assert len(parsed["summary"]) == 3


def test_empty_speech_handling():
    """Verify empty or silent recordings return clean, non-crashing default analysis."""
    service = OllamaService()
    res = service.analyze_daily_entry("", "2026-11-09")
    assert len(res.summary) == 3
    assert res.primary_mood == "Neutral"
    assert res.tasks == []

