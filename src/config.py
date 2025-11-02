"""
Configuration settings for law school note generator.
Edit the class folders list to match your directory structure.
"""

from pathlib import Path
import os

# ========== EDIT THESE PATHS ==========

# List of class folders - add or remove as needed
CLASSES = [
    Path("C:\\Users\\joesa\\OneDrive\\Documents\\Law school\\Contracts"),
    Path("C:\\Users\\joesa\\OneDrive\\Documents\\Law school\\Civ pro"),
    Path("C:\\Users\\joesa\\OneDrive\\Documents\\Law school\\Torts"),
]

# ========== PROCESSING SETTINGS ==========

# Whisper model size for transcription
# Options: 'tiny', 'base', 'small', 'medium', 'large'
# 'tiny' = fastest, 'large' = most accurate
WHISPER_MODEL = "tiny"

# Gemini model configuration
GEMINI_MODEL = "gemini-2.5-pro"
MAX_OUTPUT_TOKENS = 9000

# Number of parallel processes/threads
# Determine a sensible default number of workers for CPU-only transcription.
# Use (cpu_count - 1) to leave one core free for system responsiveness, but
# cap the value to avoid large memory usage when multiple models are loaded.
# For your laptop (Ryzen CPU, 16GB RAM) this will usually pick a reasonable value.
_CPU_COUNT = os.cpu_count() or 1
MAX_AUDIO_WORKERS = min(
    6, max(1, _CPU_COUNT - 1)
)  # Multiprocessing for CPU-intensive transcription
MAX_LLM_WORKERS = 5  # Multithreading for I/O-bound API calls

# ========== FOLDER STRUCTURE ==========

# These define the expected folder structure within each class
LLM_BASE = "LLM"

LECTURE_INPUT = "lecture-input"
LECTURE_OUTPUT = "lecture-output"
LECTURE_PROCESSED = "lecture-processed"
LECTURE_PROCESSED_AUDIO = "audio"
LECTURE_PROCESSED_TXT = "txt"

READING_INPUT = "reading-input"
READING_OUTPUT = "reading-output"
READING_PROCESSED = "reading-processed"

# ========== PROMPT FILES ==========

PROMPT_DIR = Path("prompts")
LECTURE_PROMPT_FILE = "lecture.md"
READING_PROMPT_FILE = "reading.md"

# ========== OUTPUT DIRECTORY ==========

NEW_OUTPUTS_DIR = Path("C:\\Users\\joesa\\Downloads")
