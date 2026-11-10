"""Data Transfer Object (DTO) for detached DiaryEntry presentation in the UI."""
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Optional, List, Dict, Any, Union
from app.utils.date_utils import parse_date


@dataclass
class DiaryEntryDTO:
    """
    Plain Data Transfer Object representing a detached snapshot of a DiaryEntry.
    Completely decoupled from SQLAlchemy ORM sessions to prevent DetachedInstanceError.
    """
    id: str = ""
    entry_date: Optional[date] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    audio_file_path: Optional[str] = None
    duration_seconds: float = 0.0
    original_transcript: str = ""
    edited_transcript: Optional[str] = None
    effective_transcript: str = ""
    summary_line_1: Optional[str] = None
    summary_line_2: Optional[str] = None
    summary_line_3: Optional[str] = None
    summary_lines: List[str] = field(default_factory=list)
    primary_mood: str = "Neutral"
    secondary_mood: Optional[str] = None
    mood_confidence: float = 0.0
    mood_evidence: Optional[str] = None
    topics: List[str] = field(default_factory=list)
    highlights: List[str] = field(default_factory=list)
    tasks_count: int = 0
    tasks: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_orm(cls, entry: Optional[Any]) -> Optional["DiaryEntryDTO"]:
        """
        Convert a SQLAlchemy DiaryEntry ORM instance (while session is open)
        or an existing dict/DTO into an isolated DiaryEntryDTO.
        """
        if entry is None:
            return None

        if isinstance(entry, cls):
            return entry

        if isinstance(entry, dict):
            return cls.from_dict(entry)

        # 1. Summary lines
        summary_list: List[str] = []
        if hasattr(entry, "summary_lines") and entry.summary_lines:
            try:
                summary_list = [str(s).strip() for s in entry.summary_lines if s and str(s).strip()]
            except Exception:
                summary_list = []
        if not summary_list:
            for attr in ("summary_line_1", "summary_line_2", "summary_line_3"):
                val = getattr(entry, attr, None)
                if val and str(val).strip():
                    summary_list.append(str(val).strip())

        # 2. Transcripts
        orig_trans = getattr(entry, "original_transcript", "") or ""
        ed_trans = getattr(entry, "edited_transcript", None)
        if hasattr(entry, "effective_transcript") and entry.effective_transcript is not None:
            try:
                eff_trans = str(entry.effective_transcript)
            except Exception:
                eff_trans = ed_trans if (ed_trans and ed_trans.strip()) else orig_trans
        else:
            eff_trans = ed_trans if (ed_trans and ed_trans.strip()) else orig_trans

        # 3. Topics and Highlights
        topics_list: List[str] = []
        if hasattr(entry, "topics") and entry.topics:
            try:
                topics_list = list(entry.topics)
            except Exception:
                topics_list = []

        highlights_list: List[str] = []
        if hasattr(entry, "highlights") and entry.highlights:
            try:
                highlights_list = list(entry.highlights)
            except Exception:
                highlights_list = []

        # 4. Tasks
        tasks_list: List[Dict[str, Any]] = []
        tasks_cnt = 0
        if hasattr(entry, "tasks"):
            try:
                if entry.tasks is not None:
                    tasks_cnt = len(entry.tasks)
                    tasks_list = [t.to_dict() if hasattr(t, "to_dict") else dict(t) for t in entry.tasks]
            except Exception:
                tasks_cnt = 0
                tasks_list = []

        # 5. Date
        entry_d = getattr(entry, "entry_date", None)
        if isinstance(entry_d, str):
            entry_d = parse_date(entry_d)

        return cls(
            id=str(getattr(entry, "id", "") or ""),
            entry_date=entry_d,
            created_at=getattr(entry, "created_at", None),
            updated_at=getattr(entry, "updated_at", None),
            audio_file_path=getattr(entry, "audio_file_path", None),
            duration_seconds=float(getattr(entry, "duration_seconds", 0.0) or 0.0),
            original_transcript=orig_trans,
            edited_transcript=ed_trans,
            effective_transcript=eff_trans,
            summary_line_1=getattr(entry, "summary_line_1", None),
            summary_line_2=getattr(entry, "summary_line_2", None),
            summary_line_3=getattr(entry, "summary_line_3", None),
            summary_lines=summary_list,
            primary_mood=getattr(entry, "primary_mood", "Neutral") or "Neutral",
            secondary_mood=getattr(entry, "secondary_mood", None),
            mood_confidence=float(getattr(entry, "mood_confidence", 0.0) or 0.0),
            mood_evidence=getattr(entry, "mood_evidence", None),
            topics=topics_list,
            highlights=highlights_list,
            tasks_count=tasks_cnt,
            tasks=tasks_list,
        )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DiaryEntryDTO":
        """Build DiaryEntryDTO from a standard dictionary."""
        entry_d = d.get("entry_date")
        if isinstance(entry_d, str):
            entry_d = parse_date(entry_d)

        summary = d.get("summary_lines", d.get("summary", []))
        if isinstance(summary, str):
            summary = [summary]
        elif not isinstance(summary, list):
            summary = []

        tasks_data = d.get("tasks", [])
        tasks_cnt = len(tasks_data) if isinstance(tasks_data, list) else d.get("tasks_count", 0)

        orig = d.get("original_transcript", "") or ""
        edited = d.get("edited_transcript")
        effective = d.get("effective_transcript")
        if not effective:
            effective = edited if (edited and edited.strip()) else orig

        return cls(
            id=str(d.get("id", "") or ""),
            entry_date=entry_d,
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
            audio_file_path=d.get("audio_file_path"),
            duration_seconds=float(d.get("duration_seconds", 0.0) or 0.0),
            original_transcript=orig,
            edited_transcript=edited,
            effective_transcript=effective or "",
            summary_line_1=d.get("summary_line_1"),
            summary_line_2=d.get("summary_line_2"),
            summary_line_3=d.get("summary_line_3"),
            summary_lines=[str(s) for s in summary if s and str(s).strip()],
            primary_mood=d.get("primary_mood", "Neutral") or "Neutral",
            secondary_mood=d.get("secondary_mood"),
            mood_confidence=float(d.get("mood_confidence", 0.0) or 0.0),
            mood_evidence=d.get("mood_evidence"),
            topics=list(d.get("topics", [])) if isinstance(d.get("topics"), list) else [],
            highlights=list(d.get("highlights", [])) if isinstance(d.get("highlights"), list) else [],
            tasks_count=int(tasks_cnt or 0),
            tasks=list(tasks_data) if isinstance(tasks_data, list) else [],
        )

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

