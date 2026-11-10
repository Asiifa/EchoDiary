"""Ollama local AI analysis service with strict JSON schema validation and retry logic."""
import json
import re
import requests
from typing import Dict, Any, List, Optional, Tuple
from app.config import Config
from app.schemas.analysis_schema import DailyAnalysisOutput, CombinedDailyAnalysisOutput
from app.schemas.weekly_schema import WeeklyDigestOutput


class OllamaServiceError(Exception):
    """Exception raised when Ollama local inference fails or is unavailable."""
    pass


class OllamaService:
    """
    Client for local Ollama instance running at http://127.0.0.1:11434.
    Ensures zero cloud leakage and enforces strict Pydantic validation.
    """

    def __init__(
        self,
        host: str = Config.OLLAMA_HOST,
        model_name: str = Config.DEFAULT_OLLAMA_MODEL,
        timeout: int = Config.OLLAMA_REQUEST_TIMEOUT,
    ):
        self.host = host.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout

    def check_connection(self) -> Tuple[bool, str, List[str]]:
        """
        Check if local Ollama daemon is reachable and list locally available models.
        Returns (is_connected, message, list_of_models).
        """
        try:
            url = f"{self.host}/api/tags"
            resp = requests.get(url, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                if self.model_name in models or any(m.startswith(self.model_name) for m in models):
                    return True, f"Ollama is running with model '{self.model_name}' ready.", models
                return True, f"Ollama is connected, but model '{self.model_name}' is not in local list.", models
            return False, f"Ollama responded with HTTP status {resp.status_code}.", []
        except requests.exceptions.ConnectionError:
            return False, "Ollama local service is not running. Please start Ollama via system tray or command line.", []
        except Exception as e:
            return False, f"Connection to Ollama failed: {str(e)}", []

    def _extract_json_block(self, raw_text: str) -> str:
        """Extract JSON substring from LLM response handling markdown code blocks."""
        text = raw_text.strip()
        # Look for ```json ... ``` or ``` ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # Look for { ... }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start: end + 1].strip()
        return text

    def _repair_json(self, json_str: str) -> str:
        """Attempt to repair common LLM JSON output flaws (trailing commas, quotes)."""
        # Remove trailing commas before closing braces/brackets
        repaired = re.sub(r",\s*([\]}])", r"\1", json_str)
        return repaired

    def _call_ollama_generate(self, prompt: str, system_prompt: str) -> str:
        """Send prompt to local Ollama /api/generate endpoint."""
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
            },
        }

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            if response.status_code != 200:
                raise OllamaServiceError(
                    f"Ollama returned HTTP error {response.status_code}: {response.text}"
                )
            result = response.json()
            return result.get("response", "")
        except requests.exceptions.ConnectionError:
            raise OllamaServiceError(
                "Unable to connect to Ollama at 127.0.0.1:11434. "
                "Ensure the Ollama application is running locally."
            )
        except requests.exceptions.Timeout:
            raise OllamaServiceError(
                f"Ollama inference timed out after {self.timeout} seconds. The local system may be under heavy load."
            )
        except Exception as e:
            raise OllamaServiceError(f"Ollama inference failed: {str(e)}")

    def analyze_daily_entry(self, transcript: str, entry_date: str) -> DailyAnalysisOutput:
        """
        Analyze a daily voice diary transcript to produce:
        1. Exactly three-line summary.
        2. Primary and secondary mood + confidence + evidence.
        3. Up to 5 key topics.
        4. Daily highlights.
        5. Actionable to-do extraction.
        """
        if not transcript or not transcript.strip() or transcript.strip() == "[No audible speech detected in recording]":
            return DailyAnalysisOutput(
                summary=[
                    "Recorded audio contained no audible speech or was silent.",
                    "No daily activities were logged for this session.",
                    "Check microphone volume and settings before the next recording."
                ],
                primary_mood="Neutral",
                secondary_mood=None,
                mood_confidence=0.5,
                mood_evidence="No speech detected in recording.",
                topics=["Audio silence"],
                highlights=[],
                tasks=[],
            )

        system_prompt = (
            "You are a helpful, empathetic, and objective personal diary AI assistant. "
            "You run completely locally to process a user's spoken daily diary entry.\n\n"
            "STRICT PRIVACY & ACCURACY RULES:\n"
            "1. ONLY use information explicitly stated or clearly implied by the speaker in the transcript. "
            "NEVER invent or hallucinate facts, events, or commitments.\n"
            "2. SUMMARY: Must contain EXACTLY three concise lines/sentences capturing key events, activities, and reflections.\n"
            "3. MOOD ANALYSIS: Identify the primary mood from this exact list: "
            f"{Config.SUPPORTED_MOODS}. "
            "Also provide a mood confidence score between 0.0 and 1.0, brief direct evidence from the transcript, "
            "and an optional secondary mood. Do NOT diagnose medical or psychiatric conditions.\n"
            "4. TOPICS: Extract up to 5 key topics.\n"
            "5. HIGHLIGHTS: Extract memorable accomplishments, milestones, or key events.\n"
            "6. TO-DO EXTRACTION: Extract only actionable tasks explicitly mentioned. For each task specify description, "
            "priority ('Low', 'Medium', or 'High'), and due_date in 'YYYY-MM-DD' format if mentioned (otherwise null). "
            "If no tasks were mentioned, return an empty list [].\n"
            "7. FORMAT: You MUST return a single valid JSON object strictly matching this structure:\n"
            "{\n"
            '  "summary": ["First sentence.", "Second sentence.", "Third sentence."],\n'
            '  "primary_mood": "Happy",\n'
            '  "secondary_mood": "Calm",\n'
            '  "mood_confidence": 0.85,\n'
            '  "mood_evidence": "Quoted or cited evidence from speech.",\n'
            '  "topics": ["College", "Project"],\n'
            '  "highlights": ["Finished presentation slides"],\n'
            '  "tasks": [\n'
            '    {"description": "Send email to professor", "due_date": null, "priority": "High"}\n'
            "  ]\n"
            "}"
        )

        user_prompt = f"Today's Date: {entry_date}\n\nSpoken Diary Transcript:\n{transcript}"

        last_error = None
        for attempt in range(2):  # Try initial call, retry once with explicit repair if needed
            try:
                raw_response = self._call_ollama_generate(user_prompt, system_prompt)
                json_text = self._extract_json_block(raw_response)
                json_repaired = self._repair_json(json_text)
                parsed_data = json.loads(json_repaired)
                # Validate with Pydantic
                validated_output = DailyAnalysisOutput.model_validate(parsed_data)
                return validated_output
            except Exception as e:
                last_error = e
                # Retry prompt with repair instruction
                user_prompt += "\n\nCRITICAL: Your previous response was not valid JSON. Output strictly raw JSON conforming to the schema."

        raise OllamaServiceError(f"Failed to generate structured AI analysis after retries: {str(last_error)}")

    def analyze_combined_day(
        self, transcripts: List[str], entry_date: str
    ) -> CombinedDailyAnalysisOutput:
        """Synthesize every recording for a date without replacing individual analyses."""
        recordings = [
            f"Recording {index}:\n{transcript.strip()}"
            for index, transcript in enumerate(transcripts, start=1)
            if transcript and transcript.strip()
        ]
        if not recordings:
            raise OllamaServiceError("Cannot analyze a day without any diary transcripts.")

        system_prompt = (
            "You synthesize a user's multiple local voice-diary recordings from one date. "
            "Use only facts in the recordings; do not infer missing commitments or invent events. "
            "Compare recordings to identify recurring topics and developments, explicitly distinguish "
            "completed items from outstanding tasks, and produce exactly three concise summary lines. "
            "Return no more than the three most important distinct actionable tasks across all recordings. "
            "Merge duplicate tasks while preserving the clearest wording and explicitly stated due date. "
            "Return valid JSON with keys summary (three strings), recurring_topics, new_developments, "
            "completed_items, outstanding_items (string arrays), and tasks (objects with description, "
            "due_date or null, and priority Low, Medium, or High)."
        )
        user_prompt = (
            f"Diary date: {entry_date}\n\n"
            "Earlier recordings appear before later recordings. Treat a task as completed only when "
            "a recording explicitly says it was completed.\n\n"
            + "\n\n".join(recordings)
        )
        last_error = None
        for attempt in range(2):
            try:
                raw_response = self._call_ollama_generate(user_prompt, system_prompt)
                parsed_data = json.loads(
                    self._repair_json(self._extract_json_block(raw_response))
                )
                return CombinedDailyAnalysisOutput.model_validate(parsed_data)
            except Exception as error:
                last_error = error
                user_prompt += (
                    "\n\nReturn only valid JSON matching every required field and limit tasks to three."
                )

        raise OllamaServiceError(
            f"Failed to generate combined daily analysis after retries: {str(last_error)}"
        )

    def generate_weekly_digest(
        self,
        start_date: str,
        end_date: str,
        entries_data: List[Dict[str, Any]],
        pending_tasks_count: int,
        completed_tasks_count: int,
    ) -> WeeklyDigestOutput:
        """
        Generate weekly digest using actual saved diary entries from the 7-day period.
        """
        is_partial = len(entries_data) < 7

        system_prompt = (
            "You are an analytical and encouraging personal development AI. "
            "You analyze a user's 7-day voice diary entries to generate an objective weekly digest.\n"
            "RULES:\n"
            "1. ONLY synthesize facts from the provided diary entries. Never fabricate entries or events.\n"
            f"2. Note: The user logged {len(entries_data)} entries during this 7-day period "
            f"({'partial data' if is_partial else 'full week'}).\n"
            "3. Provide:\n"
            "   - 'overview': A 2-3 paragraph cohesive summary of the week's themes, events, and emotional trajectory.\n"
            "   - 'highlights': List of 3-6 notable moments/milestones.\n"
            "   - 'accomplishments': List of completed goals or wins.\n"
            "   - 'main_topics': List of dominant themes.\n"
            "   - 'recurring_themes': List of habits, challenges, or repeated concerns.\n"
            "   - 'suggested_priorities': List of 3-5 recommended priorities for next week.\n"
            "   - 'mood_trend_summary': Commentary on how moods shifted across the days.\n"
            "4. Return strictly valid JSON."
        )

        # Build context from actual diary entries
        context_lines = [f"Week Range: {start_date} to {end_date}"]
        context_lines.append(f"Entries Logged: {len(entries_data)} of 7 days")
        context_lines.append(f"Tasks: {completed_tasks_count} completed, {pending_tasks_count} pending.\n")

        for entry in entries_data:
            entry_date = entry.get("entry_date", "Unknown Date")
            mood = entry.get("primary_mood", "Neutral")
            summary = " ".join(entry.get("summary", []))
            topics = ", ".join(entry.get("topics", []))
            context_lines.append(
                f"- Date: {entry_date} | Mood: {mood}\n"
                f"  Summary: {summary}\n"
                f"  Topics: {topics}\n"
            )

        user_prompt = "\n".join(context_lines)

        last_error = None
        for attempt in range(2):
            try:
                raw_response = self._call_ollama_generate(user_prompt, system_prompt)
                json_text = self._extract_json_block(raw_response)
                json_repaired = self._repair_json(json_text)
                parsed_data = json.loads(json_repaired)
                validated_output = WeeklyDigestOutput.model_validate(parsed_data)
                return validated_output
            except Exception as e:
                last_error = e
                user_prompt += "\n\nCRITICAL: Output strictly raw JSON conforming to the schema."

        raise OllamaServiceError(f"Failed to generate weekly digest after retries: {str(last_error)}")
