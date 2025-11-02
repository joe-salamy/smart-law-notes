# Law School Note Generator

Automated system for generating lecture and reading notes from audio files and text documents using Whisper and Gemini AI.

## Features

- **Audio Transcription**: Converts M4A lecture recordings to text using OpenAI Whisper
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

- Converts M4A files to text transcripts
- Uses multiprocessing for parallel transcription
- Saves transcripts to `lecture-input/` folder

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
# Whisper model (tiny=fastest, large=most accurate)
WHISPER_MODEL = 'tiny'

# Gemini model
GEMINI_MODEL = 'gemini-2.0-flash-exp'

# Max output tokens for generated notes
MAX_OUTPUT_TOKENS = 9000

# Parallel processing workers
MAX_AUDIO_WORKERS = 4   # CPU cores for transcription
MAX_LLM_WORKERS = 5     # Threads for API calls
```

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

- Increase `MAX_AUDIO_WORKERS` for transcription (use # of CPU cores)
- Increase `MAX_LLM_WORKERS` for API calls (5-10 works well)
- Use smaller Whisper model (`tiny` or `base`)

**API rate limits:**

- Reduce `MAX_LLM_WORKERS` to slow down API requests
- Add delays between batches if needed

## Notes

- Input folders should be empty after successful processing
- All outputs are copied to `new-outputs-safe-delete/` for backup
- Processed files are moved (not deleted) for safety
- The script creates folder structure automatically
- Duplicate filenames get timestamps to avoid overwriting

## License

Personal use for law school studies.
