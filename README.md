# EchoDiary – Voice Diary and Mood Summariser

> **Privacy-First, Offline-Native Desktop AI Journal for Students & Professionals**  
> Built with **Python 3.12**, **PySide6**, **faster-whisper**, **Ollama (`qwen2.5:3b`)**, **SQLite / SQLAlchemy**, **Pydantic v2**, and **PyQtGraph**.

---

## 1. Overview & Privacy Principles

**EchoDiary** is an offline-first desktop application designed to help students and professionals capture their daily thoughts through voice, maintain consistency, understand their emotional patterns, and track actionable commitments.

### Core Privacy Guarantees:
- **100% Local Inference**: Zero speech data or transcripts are ever transmitted over the internet.
- **No Cloud AI APIs**: Uses local **faster-whisper** for speech-to-text on your CPU (int8 quantization) and local **Ollama** running `qwen2.5:3b` strictly over `http://127.0.0.1:11434`.
- **Local Data Storage**: All database records, audio recordings, and file exports reside exclusively on your local file system (`%LOCALAPPDATA%\EchoDiary` on Windows).
- **Zero Telemetry**: No background usage tracking, third-party analytics, or telemetry.

---

## 2. Technology Stack

| Layer | Component | Technology |
|---|---|---|
| **Language** | Python 3.11 / 3.12 | Python 3.12.10 (64-bit) |
| **Desktop GUI** | Modern Framed UI | PySide6 (Qt for Python 6.12) |
| **Audio Capture** | Low-latency Mic Stream | `sounddevice` with NumPy circular buffer |
| **Audio Encoding** | WAV / Audio Reader | `soundfile` with PCM_16 encoding |
| **Speech-to-Text** | Local Transcription | `faster-whisper` (Base Multilingual, CPU int8) |
| **Local LLM** | Daily & Weekly Digest | Ollama with `qwen2.5:3b` |
| **Data Validation** | Schema Enforcement | Pydantic v2 |
| **Database** | Local Relational Store | SQLite via SQLAlchemy 2.0 ORM |
| **Visualizations** | Reactive Charts | `pyqtgraph` |
| **Testing** | Automated Unit Tests | `pytest` |

---

## 3. Directory Structure

```text
Voice-Diary-Mood-Summariser/
│
├── main.py                     # Application bootstrap and Qt event loop runner
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Pytest configuration
├── README.md                   # Complete documentation and user guide
├── .gitignore                  # Git ignore rules
│
├── app/
│   ├── __init__.py
│   ├── config.py               # Paths, environment variables, default settings
│   ├── database.py             # SQLAlchemy engine and session lifecycle managers
│   │
│   ├── models/                 # SQLAlchemy ORM Models
│   │   ├── __init__.py
│   │   ├── diary_day.py        # Calendar-day grouping and combined analysis
│   │   ├── diary_entry.py      # Individual recording, summary, and mood
│   │   ├── task.py             # Actionable Task model linked to entries
│   │   ├── weekly_report.py    # 7-day WeeklyReport model
│   │   └── settings.py         # Key-value persistent user preferences
│   │
│   ├── schemas/                # Pydantic v2 Schema Validation
│   │   ├── __init__.py
│   │   ├── analysis_schema.py  # DailyAnalysisOutput and ExtractedTask schemas
│   │   └── weekly_schema.py    # WeeklyDigestOutput schema
│   │
│   ├── services/               # Modular Business Logic Layer
│   │   ├── __init__.py
│   │   ├── audio_recorder.py   # sounddevice recording with RMS level callbacks
│   │   ├── audio_player.py     # Threaded sounddevice audio player with seek
│   │   ├── transcription_service.py # Local faster-whisper CPU int8 engine
│   │   ├── ollama_service.py   # Ollama HTTP client with JSON repair & retry
│   │   ├── summary_service.py  # 3-line daily summary orchestrator
│   │   ├── mood_service.py     # 10 mood categories and color mapping
│   │   ├── task_service.py     # Task CRUD, filtering, and status toggle
│   │   ├── diary_day_service.py # Combined daily analysis and task reconciliation
│   │   ├── weekly_digest_service.py # 7-day aggregation and partial-week logic
│   │   ├── export_service.py   # Daily TXT/JSON and Weekly MD/TXT exporters
│   │   └── backup_service.py   # Database ZIP backup and safe restore
│   │
│   ├── ui/                     # PySide6 User Interface
│   │   ├── __init__.py
│   │   ├── main_window.py      # Persistent sidebar navigation & QStackedWidget
│   │   ├── dashboard.py        # Overview dashboard with dynamic greeting
│   │   ├── recorder.py         # Voice recorder, level meter, player & transcription
│   │   ├── diary_view.py       # My Diary entry browser, search, and detail viewer
│   │   ├── todo_view.py        # Dedicated task management with filters
│   │   ├── weekly_view.py      # 7-day weekly digest with PyQtGraph charts
│   │   ├── settings_view.py    # Settings, hardware tester, backups, and privacy
│   │   ├── styles.py           # Clean, calming lavender/neutral QSS stylesheet
│   │   └── components/
│   │       ├── __init__.py
│   │       ├── audio_waveform.py # Live animated level visualizer bars
│   │       ├── mood_badge.py    # Color-coded pill badge with indicator dot
│   │       ├── stat_card.py     # Rounded metric card
│   │       └── toast.py         # Non-blocking notification toast
│   │
│   └── utils/
│       ├── __init__.py
│       ├── date_utils.py       # 7-day range helpers and date formatters
│       ├── file_manager.py     # Structured directory generator and atomic writes
│       └── validators.py       # Audio file validation and sanitization
│
└── tests/                      # Automated Test Suite
    ├── __init__.py
    ├── conftest.py             # Fixtures for SQLite in-memory and mock audio
    ├── test_database.py        # DB table creation, saving, retrieval, cascades
    ├── test_diary_days.py      # Multiple recordings, combined analysis, and legacy migration
    ├── test_transcription.py   # Audio validation and format tests
    ├── test_analysis.py        # Pydantic schemas, 3-line validator, JSON repair
    ├── test_tasks.py           # Task CRUD, filters, and status toggling
    ├── test_weekly_digest.py   # 7-day calculations, partial week, empty week
    ├── test_exports.py         # Daily & weekly atomic file exports
    └── test_ui_runtime_errors.py # Diary date navigation and responsive UI regressions
```

---

## 4. Local Data Storage Structure

On Windows, all user data is organized in `%LOCALAPPDATA%\EchoDiary`:
```text
%LOCALAPPDATA%\EchoDiary\
│
├── database/
│   └── echodiary.db            # SQLite relational database
│
├── recordings/
│   └── YYYY/
│       └── MM/
│           └── YYYY-MM-DD_<id>.wav # Captured microphone or imported audio
│
├── exports/
│   ├── daily/
│   │   ├── YYYY-MM-DD_diary.txt    # Full diary entry text and transcripts
│   │   ├── YYYY-MM-DD_summary.txt  # Three-line summary text
│   │   ├── YYYY-MM-DD_tasks.txt    # Actionable to-dos text
│   │   └── YYYY-MM-DD_entry.json   # Full structured JSON record
│   └── weekly/
│       ├── YYYY-MM-DD_to_YYYY-MM-DD_weekly_digest.md  # Markdown report
│       └── YYYY-MM-DD_to_YYYY-MM-DD_weekly_digest.txt # Plain text digest
│
├── backups/
│   └── EchoDiary_backup_YYYYMMDD_HHMMSS.zip # Database snapshot archives
│
└── logs/
    └── echodiary.log           # Lifecycle and error logs (no diary transcripts)
```

---

## 5. Prerequisites & Installation

### A. System Requirements
- **Operating System**: Windows 10/11 (64-bit), macOS, or Linux.
- **Python**: Version 3.11 or 3.12 (64-bit).
- **RAM**: 8 GB minimum (16 GB recommended for Whisper + LLM inference).
- **Microphone**: Any functional built-in microphone or external headset.
- **Ollama**: Installed locally on your machine ([https://ollama.com](https://ollama.com)).

### B. Setup Instructions

1. **Clone or navigate to the repository**:
   ```bash
   cd d:\Voice-Diary-Mood-Summariser
   ```

2. **Create and activate a virtual environment**:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```powershell
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

### C. Installing Local AI Models

1. **Download the Ollama Language Model**:
   Make sure Ollama is running, then pull the default model:
   ```powershell
   ollama pull qwen2.5:3b
   ```
   *(Optional: You may also use `qwen2.5:7b` or `llama3.2:3b` configured via the Settings tab).*

2. **Pre-caching the faster-whisper Model**:
   The application uses faster-whisper's `base` multilingual model by default (or `tiny` for speed). You can pre-cache it offline with:
   ```powershell
   python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"
   ```

---

## 6. How to Run the Application

To launch EchoDiary:
```powershell
.\venv\Scripts\python main.py
```

### Running Automated Tests
Run the complete test suite with pytest:
```powershell
.\venv\Scripts\pytest -v
```

---

## 7. Feature Walkthrough

### 1. Dashboard
- **Personalized Greeting**: Dynamic "Good morning", "Good afternoon", or "Good evening" with the current date.
- **Today's Status Banner**: Displays whether you have recorded today's diary. If recorded, shows the mood badge and 3-line summary; if not, provides a 1-click button to record.
- **4 Key Stat Cards**: Total Entries, Entries Logged this Week, Pending Tasks, Completed Tasks.
- **Latest Diary Entry Card**: Shows the most recent reflection with duration, 3-line summary lines, and link to My Diary.
- **Weekly Mood Overview**: Pill breakdown of moods experienced in the current 7-day period.

### 2. New Voice Entry (Recorder)
- **Microphone Selection**: Dropdown listing all available audio input devices.
- **Recording Controls**: Start, Pause, Resume, Stop, and Discard/Re-record.
- **Live Level Waveform**: 42 dynamic animated vertical bars that react to microphone RMS volume.
- **Import Audio Files**: Supports importing existing `.wav`, `.mp3`, `.m4a`, `.flac`, and `.ogg` files with duration and format validation.
- **Built-in Audio Player**: Seekable audio slider with real-time playback position and play/pause button.
- **Local Speech-to-Text**: One-click local transcription using `faster-whisper` (CPU int8). Automatically detects language.
- **Editable Transcript**: Allows refining the spoken text before AI analysis while keeping the original speech record intact.
- **Analyze with AI & Save Entry**: Invokes local `qwen2.5:3b` to produce the 3-line summary, mood classification, topics, and tasks.

### 3. My Diary
- **Date-Based Navigation**: Browse weekday/date groups with recording counts; recordings appear chronologically within each day.
- **Daily Combined Analysis**: Local Ollama compares all recordings for a date, summarizes recurring topics and developments, and reconciles up to three distinct actionable tasks without resetting completion status.
- **Individual Recording Details**: Review each recording's timestamp, duration, transcript, individual analysis, and independent audio playback.
- **Search & Mood Filter**: Search transcripts, topics, and summaries; filter recordings by mood.
- **Tabbed Transcripts**: Switch between Edited/Effective Transcript and Original Speech Transcript.
- **Extracted Tasks**: Interactive checkboxes to mark tasks completed directly from the diary view.
- **Entry Management**: Edit transcript/mood, export daily files, or delete entry (with clear explanation of consequences for audio and tasks).

On startup, existing recordings and tasks are backfilled to their date groups using a backward-compatible SQLite migration. Their transcripts, individual analyses, and task statuses are retained.

### 4. To-Do List
- **Action Items Filter**: Filter by "Pending", "Completed", or "All".
- **Priority Filter**: Filter by High, Medium, Low.
- **Due Date Sorting**: Sort deadlines ascending with undated items cleanly positioned.
- **Source Link**: One-click "From Diary" button navigates back to the exact diary entry where the task originated.
- **Manual Task Creation**: Add custom tasks with priority and optional deadlines.
- **Export Task List**: Exports all current tasks to a clean text file in `exports/`.

### 5. Weekly Insights & Digest
- **7-Day Period Selection**: Date picker with quick buttons for "Current 7 Days" and "Previous Week".
- **Objective Synthesis**: Uses actual saved entries from the 7-day period.
- **Partial-Week Handling**: When fewer than 7 days have entries, displays a clear warning banner stating that the digest is based on partial data.
- **PyQtGraph Charts**:
  - **Mood Distribution**: Clean bar chart displaying the frequency of each mood.
  - **7-Day Activity & Trend**: Timeline plot displaying daily recording activity and confidence ratings.
- **Comprehensive Report**:
  - 1. Weekly Overview
  - 2. Key Highlights
  - 3. Accomplishments
  - 4. Main Topics Discussed
  - 5. Recurring Themes
  - 6. Next Week's Suggested Priorities
- **Export Formats**: Export the weekly digest as Markdown (`.md`) or formatted Plain Text (`.txt`).

### 6. Settings & Privacy Center
- **Local AI Status**: Live indicator for Ollama connectivity with model selector.
- **Whisper Configuration**: Select between `base` (recommended), `tiny` (fastest), and `small`.
- **Audio Hardware**: Select default microphone and view recording specs.
- **Storage Directory Explorer**: One-click buttons to open the database, recordings, and exports folders in Windows File Explorer.
- **Backup & Restore**: Create timestamped zip backups of the database or restore from an existing backup archive with automatic pre-restore safety copy.
- **Privacy Wipe**: Complete data purge option with red safety confirmation to reset the database and delete all local audio.

---

## 8. Building a Standalone Windows Executable (.exe)

You can package EchoDiary into a standalone Windows `.exe` using **PyInstaller**:

1. **Install PyInstaller**:
   ```powershell
   .\venv\Scripts\pip install pyinstaller
   ```

2. **Build the Application**:
   ```powershell
   .\venv\Scripts\pyinstaller --noconfirm --onedir --windowed `
       --name "EchoDiary" `
       --collect-data "faster_whisper" `
       --collect-data "pyqtgraph" `
       --collect-submodules "sounddevice" `
       --collect-submodules "soundfile" `
       main.py
   ```

3. **Output**:
   The standalone application bundle will be created in `dist/EchoDiary/EchoDiary.exe`.

---

## 9. Known Considerations & Technical Notes

- **Microphone Permissions**: On Windows 10/11, ensure microphone access is granted in *Windows Settings -> Privacy & Security -> Microphone*.
- **Ollama Background Process**: Ollama must be running as a background service (`http://127.0.0.1:11434`) before generating daily summaries or weekly digests.
- **Model Storage**: Ollama models are stored in `%USERPROFILE%\.ollama\models`, and HuggingFace Whisper models are cached in `%USERPROFILE%\.cache\huggingface\hub`.
