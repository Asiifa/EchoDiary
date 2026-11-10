"""Pydantic schemas for weekly digest analysis."""
from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class WeeklyDigestOutput(BaseModel):
    """Structured output for 7-day weekly digest from local LLM."""
    overview: str = Field(..., description="Comprehensive narrative overview of the week")
    highlights: List[str] = Field(default_factory=list, description="Important highlights and events")
    accomplishments: List[str] = Field(default_factory=list, description="Key accomplishments and wins")
    main_topics: List[str] = Field(default_factory=list, description="Main topics discussed across the week")
    recurring_themes: List[str] = Field(default_factory=list, description="Recurring patterns or themes identified")
    suggested_priorities: List[str] = Field(default_factory=list, description="Suggested focus areas and priorities for next week")
    mood_trend_summary: str = Field("", description="Narrative commentary on emotional trajectory and mood changes")

