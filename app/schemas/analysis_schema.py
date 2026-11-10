"""Pydantic schemas for daily diary AI analysis."""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator
from app.config import Config


class ExtractedTask(BaseModel):
    """Actionable to-do item extracted from diary speech."""
    description: str = Field(..., min_length=2, description="Actionable task description")
    due_date: Optional[str] = Field(None, description="Due date in YYYY-MM-DD format if explicitly stated, else null")
    priority: Literal["Low", "Medium", "High"] = Field("Medium", description="Task priority")

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, v: str) -> str:
        if isinstance(v, str):
            v_title = v.strip().capitalize()
            if v_title in Config.TASK_PRIORITIES:
                return v_title
        return "Medium"

    @field_validator("due_date", mode="before")
    @classmethod
    def clean_due_date(cls, v: Optional[str]) -> Optional[str]:
        if not v or str(v).lower() in ("null", "none", "", "n/a", "no"):
            return None
        # Basic YYYY-MM-DD pattern validation or fallback
        v_str = str(v).strip()
        parts = v_str.split("-")
        if len(parts) == 3 and len(parts[0]) == 4:
            return v_str
        return None


class DailyAnalysisOutput(BaseModel):
    """Structured output from local LLM for a daily diary entry."""
    summary: List[str] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Exactly three concise sentences summarizing the diary entry"
    )
    primary_mood: str = Field(
        ...,
        description="Primary expressed mood from supported categories"
    )
    secondary_mood: Optional[str] = Field(
        None,
        description="Optional secondary mood from supported categories"
    )
    mood_confidence: float = Field(
        0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score for the mood analysis between 0.0 and 1.0"
    )
    mood_evidence: str = Field(
        ...,
        min_length=3,
        description="Brief evidence directly from transcript supporting the mood identification"
    )
    topics: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Up to five key topics discussed"
    )
    highlights: List[str] = Field(
        default_factory=list,
        description="Important achievements, events, or memorable moments"
    )
    tasks: List[ExtractedTask] = Field(
        default_factory=list,
        description="Actionable to-do items extracted from the transcript"
    )

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary_lines(cls, v: any) -> List[str]:
        if isinstance(v, str):
            # If string returned, split by newline or periods
            lines = [line.strip("- *• \t\r") for line in v.strip().split("\n") if line.strip()]
            if len(lines) == 1:
                # Try splitting sentences
                sentences = [s.strip() for s in lines[0].split(". ") if s.strip()]
                lines = sentences
            v = lines

        if isinstance(v, list):
            cleaned = [str(item).strip("- *• \t\r\n") for item in v if str(item).strip()]
            if len(cleaned) == 3:
                return cleaned
            elif len(cleaned) > 3:
                # Combine extra into the third line or take top 3
                return cleaned[:3]
            elif len(cleaned) == 2:
                # Add a concluding observational line
                cleaned.append("Reflected on the day's experiences.")
                return cleaned
            elif len(cleaned) == 1:
                parts = cleaned[0].split(". ")
                if len(parts) >= 3:
                    return [p.strip().rstrip(".") + "." for p in parts[:3]]
                return [cleaned[0], "Continued with daily routine and activities.", "Reflected on the day's events."]
        return ["Completed daily activities.", "Engaged with scheduled routine.", "Reflected on personal progress."]

    @field_validator("primary_mood", mode="before")
    @classmethod
    def normalize_primary_mood(cls, v: str) -> str:
        if isinstance(v, str):
            v_title = v.strip().capitalize()
            for supported in Config.SUPPORTED_MOODS:
                if supported.lower() == v_title.lower():
                    return supported
        return "Neutral"

    @field_validator("secondary_mood", mode="before")
    @classmethod
    def normalize_secondary_mood(cls, v: Optional[str]) -> Optional[str]:
        if not v or str(v).lower() in ("null", "none", "", "n/a"):
            return None
        if isinstance(v, str):
            v_title = v.strip().capitalize()
            for supported in Config.SUPPORTED_MOODS:
                if supported.lower() == v_title.lower():
                    return supported
        return None

    @field_validator("mood_confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: any) -> float:
        try:
            val = float(v)
            if val >= 2.0 and val <= 100.0:
                val = val / 100.0
            elif val > 1.0:
                val = 1.0
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 0.75

    @field_validator("topics", mode="before")
    @classmethod
    def limit_topics(cls, v: any) -> List[str]:
        if isinstance(v, list):
            cleaned = [str(x).strip() for x in v if str(x).strip()]
            return cleaned[:5]
        return []


class CombinedDailyAnalysisOutput(BaseModel):
    """Structured synthesis of all recordings saved for one calendar day."""

    summary: List[str] = Field(..., min_length=3, max_length=3)
    recurring_topics: List[str] = Field(default_factory=list)
    new_developments: List[str] = Field(default_factory=list)
    completed_items: List[str] = Field(default_factory=list)
    outstanding_items: List[str] = Field(default_factory=list)
    tasks: List[ExtractedTask] = Field(default_factory=list, max_length=3)
