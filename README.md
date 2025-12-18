# Law School Note Generator

Automated system for generating lecture and reading notes from audio files and text documents using Whisper and Gemini AI.

## Features

- **Audio Transcription**: Converts M4A lecture recordings to text using faster-whisper (large-v3 model) with timestamps
  - CPU-optimized with int8 quantization for fast processing
  - Audio preprocessing: noise reduction, bandpass filtering, normalization
  - Segment-level timestamps in [HH:MM:SS] format for easy navigation
  - Progress bars showing real-time transcription status
- **AI Note Generation**: Creates structured notes from transcripts and readings using Google Gemini
- **Parallel Processing**: Uses multiprocessing for transcription and multithreading for API calls
- **Multi-Class Support**: Processes multiple law school classes simultaneously
- **Organized Output**: Maintains clean folder structure with automatic file management

## Project Structure

```
.
├── src/
│   ├── main.py                 # Central orchestrator
│   ├── config.py               # Configuration settings
│   ├── folder_manager.py       # Folder structure management
│   ├── audio_processor.py      # Audio transcription with Whisper
│   ├── llm_processor.py        # LLM processing with Gemini
│   └── file_mover.py           # File management utilities
├── prompts/
│   ├── reading.md              # Reading notes prompt
│   └── lecture.md              # Lecture notes prompt
├── new-outputs-safe-delete/    # Consolidated output location
├── tests/
│   └── __init__.py
├── .env                        # API keys (not in git)
├── .gitignore
├── requirements.txt
└── README.md
```

## Class Folder Structure

Each class should have the following structure:

```
Class Name/
└── LLM/
    ├── lecture-input/          # Place M4A audio files here
    ├── lecture-output/         # Generated lecture notes
    ├── lecture-processed/
    │   ├── audio/              # Processed audio files
    │   └── txt/                # Processed transcripts
    ├── reading-input/          # Place reading TXT files here
    ├── reading-output/         # Generated reading notes
    └── reading-processed/      # Processed reading files
```

## Setup Instructions

### 1. Prerequisites

- Python 3.8 or higher
- FFmpeg (required for Whisper)
- Gemini API key

### 2. Install FFmpeg

**Windows:**

```bash
# Using Chocolatey
choco install ffmpeg

# Or download from https://ffmpeg.org/download.html
```

**Mac:**

```bash
brew install ffmpeg
```

**Linux:**

```bash
sudo apt update
sudo apt install ffmpeg
```

### 3. Create Virtual Environment

```bash
python -m venv venv
```

**Activate:**

- Windows: `venv\Scripts\activate`
- Mac/Linux: `source venv/bin/activate`

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Environment

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_api_key_here
```

Get your API key from: https://makersuite.google.com/app/apikey

### 6. Configure Classes

Edit `src/config.py` to add your class folders:

```python
CLASSES = [
    Path("C:\\path\\to\\Contracts"),
    Path("C:\\path\\to\\Civ pro"),
    Path("C:\\path\\to\\Torts"),
]
```

### 7. Create Prompt Files

Create two markdown files in the `prompts/` folder:

- `lecture.md` - System prompt for lecture note generation
- `reading.md` - System prompt for reading note generation

Example prompt structure:

```markdown
You are an expert legal educator creating comprehensive study notes.

Analyze the provided text and create detailed notes that:

1. Identify key concepts and principles
2. Highlight important cases and holdings
3. Explain complex legal doctrines clearly
4. Provide examples and applications

Format the notes with clear headings and bullet points.
```

## Usage

### Run the Complete Pipeline

```bash
cd src
python main.py
```

This will:

1. Verify folder structure for all classes
2. Transcribe all audio files in `lecture-input/`
3. Generate lecture notes from transcripts
4. Generate reading notes from reading files
5. Move processed files to appropriate folders
6. Copy all outputs to `new-outputs-safe-delete/`

### Processing Steps

**Step 1: Folder Verification**

- Checks each class has required folder structure
- Creates missing folders automatically

**Step 2: Audio Transcription**

- Converts M4A files to text transcripts with timestamps
- Audio preprocessing pipeline:
  - Converts M4A to WAV (16kHz, mono)
  - Applies noise reduction to remove background noise
  - Applies bandpass filter (80Hz-8000Hz) for speech frequencies
  - Normalizes audio levels to -20dB LUFS
- Uses faster-whisper (large-v3) for most accurate transcription
- CPU-optimized with int8 quantization (4 threads)
- Shows progress bars during transcription
- Saves timestamped transcripts to `lecture-input/` folder
- Expected performance: 3-4x real-time (1 hour lecture = 15-20 minutes)

**Step 3: Lecture Note Generation**

- Processes lecture transcripts with Gemini
- Uses multithreading for parallel API calls
- Saves markdown notes to `lecture-output/`
- Moves transcripts to `lecture-processed/txt/`

**Step 4: Reading Note Generation**

- Processes reading files with Gemini
- Uses multithreading for parallel API calls
- Saves markdown notes to `reading-output/`
- Moves reading files to `reading-processed/`

## Configuration Options

Edit `src/config.py` to customize:

```python
# Gemini model
GEMINI_MODEL = 'gemini-2.5-pro'

# Max output tokens for generated notes
MAX_OUTPUT_TOKENS = 9000

# Parallel processing workers
MAX_AUDIO_WORKERS = 3   # Parallel processes for transcription (2-3 recommended)
MAX_LLM_WORKERS = 5     # Threads for API calls
```

**Note**: Audio transcription now uses faster-whisper with CPU-optimized settings (large-v3 model, int8 compute, 4 CPU threads). These settings are hardcoded for optimal performance on AMD Ryzen 7 7730U processors.

## Workflow

1. **Place Files**: Add M4A files to `lecture-input/` and TXT files to `reading-input/`
2. **Run Script**: Execute `python main.py`
3. **Review Output**:
   - Individual class folders contain class-specific notes
   - `new-outputs-safe-delete/` contains all generated notes
4. **Input Folders**: Will be empty after processing (files moved to `processed/`)

## Troubleshooting

**"FFmpeg not found" error:**

- Ensure FFmpeg is installed and in your system PATH
- Test with: `ffmpeg -version`

**"GEMINI_API_KEY not found" error:**

- Check `.env` file exists in project root
- Verify API key is valid

**"Module not found" errors:**

- Ensure virtual environment is activated
- Reinstall: `pip install -r requirements.txt`

**Slow processing:**

- Transcription is CPU-optimized (int8, 4 threads) for ~3-4x real-time speed
- Increase `MAX_AUDIO_WORKERS` in config.py (2-3 recommended for parallel files)
- Don't exceed 4 CPU threads to avoid system instability
- Increase `MAX_LLM_WORKERS` for faster API processing (5-10 works well)

**API rate limits:**

- Reduce `MAX_LLM_WORKERS` to slow down API requests
- Add delays between batches if needed

**Audio preprocessing errors:**

- Ensure FFmpeg is properly installed (required for pydub)
- Check M4A files are not corrupted
- Verify sufficient disk space for temporary WAV files

**Out of memory errors:**

- Reduce `MAX_AUDIO_WORKERS` to process fewer files simultaneously
- Close other applications to free up RAM
- Process classes one at a time if needed

## Notes

- Input folders should be empty after successful processing
- All outputs are copied to `new-outputs-safe-delete/` for backup
- Processed files are moved (not deleted) for safety
- The script creates folder structure automatically
- Duplicate filenames get timestamps to avoid overwriting

## License

Personal use for law school studies.
