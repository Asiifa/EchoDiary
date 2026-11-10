"""
Sample Data Seeder for EchoDiary
Populates the local database with 7 realistic student voice diary entries,
synthesized audio WAV files, extracted tasks, and a weekly digest.
Useful for testing, demonstrations, and instant evaluation.
"""
import sys
import numpy as np
import soundfile as sf
from datetime import date, timedelta, datetime
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Config
from app.database import init_db, get_db_session
from app.models.diary_entry import DiaryEntry
from app.models.task import Task
from app.services.weekly_digest_service import WeeklyDigestService
from app.services.export_service import ExportService
from app.utils.file_manager import FileManager


def generate_synthetic_audio(output_path: Path, duration_sec: float = 3.0):
    """Generate a clean ambient sine chime as placeholder audio for sample entries."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sr = 16000
    t = np.linspace(0, duration_sec, int(sr * duration_sec), False)
    # Gentle harmonic tone
    audio = 0.25 * np.sin(2 * np.pi * 528 * t) * np.exp(-t / 1.5)
    sf.write(str(output_path), audio.astype(np.float32), sr, subtype="PCM_16", format="WAV")


SAMPLE_ENTRIES = [
    {
        "days_ago": 6,
        "mood": "Calm",
        "secondary_mood": "Grateful",
        "confidence": 0.92,
        "evidence": "Speaker noted peaceful morning study and gratefulness for a restful weekend.",
        "duration": 28.5,
        "transcript": (
            "Started my Monday with an early morning run across campus. Attended the operating systems "
            "lecture and took thorough notes on process synchronization. In the afternoon I reviewed "
            "the seminar slides. Felt calm and ready for the week ahead."
        ),
        "summary": [
            "Started Monday with morning exercise and attended operating systems lecture.",
            "Reviewed seminar slides and studied process synchronization concepts.",
            "Felt calm, focused, and prepared for the upcoming week."
        ],
        "topics": ["Operating Systems", "Exercise", "Study Routine"],
        "highlights": ["Completed 5km morning run", "Understood semaphores in OS"],
        "tasks": [
            {"desc": "Review chapter 3 practice problems", "due": 4, "prio": "Medium"},
            {"desc": "Email lab TA regarding group assignment", "due": 5, "prio": "High"},
        ],
    },
    {
        "days_ago": 5,
        "mood": "Excited",
        "secondary_mood": "Happy",
        "confidence": 0.88,
        "evidence": "Enthusiastic tone describing project milestone and collaboration.",
        "duration": 34.0,
        "transcript": (
            "Today was exciting. Alex and I finished designing the database schema for our senior project. "
            "Our professor reviewed our normalized tables and gave very positive feedback. We celebrated "
            "with coffee at the student union."
        ),
        "summary": [
            "Finished database schema design with Alex for senior project.",
            "Received positive feedback from course professor on database normalization.",
            "Celebrated milestone with coffee and planned next implementation steps."
        ],
        "topics": ["Senior Project", "Database Schema", "Alex"],
        "highlights": ["Professor approved normalized database design"],
        "tasks": [
            {"desc": "Initialize GitHub repository and add README", "due": 3, "prio": "High"},
        ],
    },
    {
        "days_ago": 4,
        "mood": "Stressed",
        "secondary_mood": "Uncertain",
        "confidence": 0.82,
        "evidence": "Expressed anxiety regarding upcoming chemistry midterm and heavy workload.",
        "duration": 42.1,
        "transcript": (
            "Feeling quite stressed tonight. The organic chemistry assignment took over four hours and "
            "I still have two problem sets left. Also need to study for Thursday's midterm exam. "
            "I will sleep early tonight to have energy tomorrow."
        ),
        "summary": [
            "Spent four hours working through difficult organic chemistry problem sets.",
            "Expressed stress over multiple upcoming assignment deadlines and midterm exam.",
            "Decided to prioritize sleep and rest to regain focus for tomorrow."
        ],
        "topics": ["Chemistry", "Midterm Exam", "Workload"],
        "highlights": ["Completed the reaction mechanism synthesis problem"],
        "tasks": [
            {"desc": "Complete chemistry practice exam questions", "due": 2, "prio": "High"},
            {"desc": "Form study group session with Maya", "due": 3, "prio": "Medium"},
        ],
    },
    {
        "days_ago": 3,
        "mood": "Happy",
        "secondary_mood": "Relieved",
        "confidence": 0.90,
        "evidence": "Speaker expressed relief after finishing study group session and feeling prepared.",
        "duration": 31.2,
        "transcript": (
            "Much better day today. Maya and I spent two hours at the library reviewing organic chemistry "
            "mechanisms. Everything clicked into place and I feel so much more confident for tomorrow. "
            "Had a great phone call with my family in the evening."
        ),
        "summary": [
            "Studied organic chemistry reaction mechanisms with Maya at the campus library.",
            "Gained strong confidence in key exam topics after collaborative review.",
            "Enjoyed an uplifting evening phone call with family."
        ],
        "topics": ["Library Study", "Maya", "Family", "Chemistry"],
        "highlights": ["Mastered carbon-carbon coupling mechanisms"],
        "tasks": [
            {"desc": "Pack calculator and stationery for exam", "due": 1, "prio": "High"},
        ],
    },
    {
        "days_ago": 2,
        "mood": "Excited",
        "secondary_mood": "Relieved",
        "confidence": 0.94,
        "evidence": "Very happy tone reporting exam went smoothly and celebrating with friends.",
        "duration": 38.0,
        "transcript": (
            "The chemistry exam is done! The questions were very similar to our practice set and I finished "
            "with ten minutes to spare. In the evening our intramural volleyball team won our first match. "
            "Such a fun and energizing Thursday."
        ),
        "summary": [
            "Successfully completed the organic chemistry midterm exam with time to spare.",
            "Played intramural volleyball and won the opening match of the season.",
            "Felt high energy, relief, and excitement heading into the weekend."
        ],
        "topics": ["Midterm Exam", "Volleyball", "Celebration"],
        "highlights": ["Acquitted the chemistry exam with confidence", "Won intramural match"],
        "tasks": [
            {"desc": "Wash team sports gear", "due": 1, "prio": "Low"},
        ],
    },
    {
        "days_ago": 1,
        "mood": "Calm",
        "secondary_mood": "Happy",
        "confidence": 0.89,
        "evidence": "Speaker enjoyed a slow Friday afternoon and planned leisurely weekend activities.",
        "duration": 25.4,
        "transcript": (
            "Relaxing Friday. Attended my afternoon ethics seminar which sparked an interesting discussion "
            "on AI privacy and data ownership. Read a few chapters of my sci-fi book at a local cafe. "
            "Looking forward to a productive yet balanced weekend."
        ),
        "summary": [
            "Participated in seminar discussion regarding AI privacy and data rights.",
            "Spent a quiet afternoon reading at a local cafe.",
            "Reflected on maintaining balance between academic goals and personal well-being."
        ],
        "topics": ["AI Ethics", "Reading", "Cafe", "Relaxation"],
        "highlights": ["Contributed keynote point during ethics seminar"],
        "tasks": [
            {"desc": "Outline ethics term paper draft", "due": 4, "prio": "Medium"},
        ],
    },
    {
        "days_ago": 0,
        "mood": "Grateful",
        "secondary_mood": "Calm",
        "confidence": 0.95,
        "evidence": "Deep expression of gratitude for personal progress and supportive friends.",
        "duration": 30.1,
        "transcript": (
            "Recorded this reflection after cooking dinner with roommates. Taking time today to appreciate "
            "how much progress I have made this semester. Balancing coursework, project meetings, and health "
            "is finally feeling natural. Ready to take on next week with renewed energy."
        ),
        "summary": [
            "Prepared a home-cooked dinner and spent quality time with roommates.",
            "Appreciated personal academic progress and healthy daily routines.",
            "Felt grateful, grounded, and motivated for the week ahead."
        ],
        "topics": ["Roommates", "Cooking", "Semester Goals", "Gratitude"],
        "highlights": ["Cooked dinner for friends", "Maintained consistent sleep schedule"],
        "tasks": [
            {"desc": "Set goals and weekly priorities for Monday", "due": 1, "prio": "Medium"},
        ],
    },
]


def seed_data():
    """Populate database and local directories with sample entries."""
    Config.ensure_directories()
    init_db()

    today = date.today()
    created_entries = []

    print(f"[*] Seeding EchoDiary database with 7 realistic student entries...")

    with get_db_session() as session:
        for item in SAMPLE_ENTRIES:
            entry_date = today - timedelta(days=item["days_ago"])

            # Check if entry already exists for this date
            existing = session.query(DiaryEntry).filter(DiaryEntry.entry_date == entry_date).first()
            if existing:
                session.delete(existing)
                session.flush()

            # Create audio file
            import uuid
            entry_id = str(uuid.uuid4())
            audio_path = FileManager.get_recording_path(entry_date, entry_id, ext=".wav")
            generate_synthetic_audio(audio_path, duration_sec=item["duration"] / 10.0)

            entry = DiaryEntry(
                id=entry_id,
                entry_date=entry_date,
                created_at=datetime.utcnow() - timedelta(days=item["days_ago"]),
                updated_at=datetime.utcnow() - timedelta(days=item["days_ago"]),
                audio_file_path=str(audio_path),
                duration_seconds=item["duration"],
                original_transcript=item["transcript"],
                edited_transcript=item["transcript"],
                summary_line_1=item["summary"][0],
                summary_line_2=item["summary"][1],
                summary_line_3=item["summary"][2],
                primary_mood=item["mood"],
                secondary_mood=item.get("secondary_mood"),
                mood_confidence=item["confidence"],
                mood_evidence=item["evidence"],
            )
            entry.topics = item["topics"]
            entry.highlights = item["highlights"]
            session.add(entry)
            session.flush()

            # Add tasks
            for t_item in item["tasks"]:
                task_due = entry_date + timedelta(days=t_item["due"])
                task = Task(
                    diary_entry_id=entry.id,
                    description=t_item["desc"],
                    due_date=task_due,
                    priority=t_item["prio"],
                    status="Completed" if item["days_ago"] > 2 else "Pending",
                    created_at=datetime.utcnow() - timedelta(days=item["days_ago"]),
                    completed_at=(datetime.utcnow() - timedelta(days=1)) if item["days_ago"] > 2 else None,
                )
                session.add(task)
            session.flush()

            # Export daily files
            ExportService.export_daily_entry(entry)
            created_entries.append(entry)
            print(f"  ✓ Added entry for {entry_date} ({entry.primary_mood}) - 3 summary lines, {len(item['tasks'])} tasks")

    print(f"\n[+] Successfully seeded {len(created_entries)} diary entries.")
    print(f"[+] All audio files and daily exports generated.")
    print(f"[*] Run 'python main.py' to explore the populated dashboard and insights!")


if __name__ == "__main__":
    seed_data()

