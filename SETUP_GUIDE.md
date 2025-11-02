# Complete Setup Guide

## Quick Start Checklist

- [ ] Install Python 3.8+
- [ ] Install FFmpeg
- [ ] Clone/download project
- [ ] Create virtual environment
- [ ] Install dependencies
- [ ] Get Gemini API key
- [ ] Configure `.env` file
- [ ] Update class paths in `config.py`
- [ ] Create prompt files
- [ ] Test run

---

## Detailed Instructions

### 1. Install Python

**Check if already installed:**
```bash
python --version
```

Should show Python 3.8 or higher.

**If not installed:**
- Download from [python.org](https://www.python.org/downloads/)
- During installation, check "Add Python to PATH"

### 2. Install FFmpeg

FFmpeg is required for Whisper to process audio files.

**Windows (using Chocolatey):**
```bash
choco install ffmpeg
```

**Windows (manual):**
1. Download from [ffmpeg.org/download.html](https://ffmpeg.org/download.html)
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to system PATH

**Mac:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Verify installation:**
```bash
ffmpeg -version
```

### 3. Set Up Project

**Navigate to project directory:**
```bash
cd path/to/law-school-notes
```

**Create virtual environment:**
```bash
python -m venv venv
```

**Activate virtual environment:**

*Windows:*
```bash
venv\Scripts\activate
```

*Mac/Linux:*
```bash
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt.

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `openai-whisper` - Audio transcription
- `google-generativeai` - Gemini API
- `python-dotenv` - Environment variables
- `pathlib` - Path handling

**Note:** First-time Whisper installation will download model files (~100MB for 'tiny' model).

### 5. Get Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with Google account
3. Click "Create API Key"
4. Copy the key (save it securely!)

**Note:** Gemini API has a free tier with rate limits. Check current limits at [ai.google.dev](https://ai.google.dev/pricing).

### 6. Configure Environment Variables

**Create `.env` file:**

In the project root directory, create a file named `.env`:

```bash
# On Windows
type nul > .env

# On Mac/Linux
touch .env
```

**Add API key to `.env`:**

Open `.env` in a text editor and add:

```
GEMINI_API_KEY=your_actual_api_key_here
```

Replace `your_actual_api_key_here` with your actual key from step 5.

**Important:** Never commit `.env` to git (it's in `.gitignore`).

### 7. Configure Class Paths

**Edit `src/config.py`:**

Open `src/config.py` and update the `CLASSES` list:

```python
CLASSES = [
    Path("C:\\Users\\YourName\\Documents\\Law school\\Contracts"),
    Path("C:\\Users\\YourName\\Documents\\Law school\\Civ pro"),
    Path("C:\\Users\\YourName\\Documents\\Law school\\Torts"),
]
```

**Tips:**
- Use absolute paths (full path from drive letter)
- On Windows, use double backslashes `\\` or forward slashes `/`
- Check paths exist in File Explorer before running

### 8. Create Prompt Files

**Create `prompts` directory:**
```bash
mkdir prompts
```

**Create `prompts/lecture.md`:**

Copy the example lecture prompt provided, or create your own following this structure:

```markdown
# Lecture Notes Prompt

You are a legal educator creating study notes from lecture transcripts.

[Instructions for what to include and how to format]

[Examples of good notes]
```

**Create `prompts/reading.md`:**

Copy the example reading prompt provided, or create your own with instructions for:
- Case briefs (facts, issue, holding, reasoning)
- Statutory interpretation
- Textbook summaries

### 9. Prepare Your Files

**For each class, add files to:**

```
Class Name/LLM/
├── lecture-input/     ← Put .m4a audio files here
└── reading-input/     ← Put .txt reading files here
```

**File naming tips:**
- Use descriptive names: `contracts_week1_offer_acceptance.m4a`
- Avoid special characters: `() [] {} & % $ # @`
- Use underscores or hyphens: `civ-pro-personal-jurisdiction.txt`

### 10. Test Run

**Navigate to src directory:**
```bash
cd src
```

**Run the script:**
```bash
python main.py
```

**What should happen:**
1. Folder structure verification
2. Audio transcription progress bar
3. LLM processing with status updates
4. Files moved to processed folders
5. Success summary

**Expected output location:**
```
Class Name/LLM/
├── lecture-output/    ← Generated lecture notes (.md)
├── reading-output/    ← Generated reading notes (.md)
└── lecture-processed/ ← Original files moved here
```

Plus all outputs copied to: `new-outputs-safe-delete/`

---

## Common Issues & Solutions

### "FFmpeg not found"

**Problem:** Whisper can't find FFmpeg

**Solution:**
1. Verify installation: `ffmpeg -version`
2. If not found, reinstall FFmpeg
3. Restart terminal after installation
4. Check system PATH includes FFmpeg

### "GEMINI_API_KEY not found"

**Problem:** `.env` file not loaded or incorrect

**Solution:**
1. Verify `.env` exists in project root (not in `src/`)
2. Check file contains: `GEMINI_API_KEY=your_key`
3. No quotes needed around the key
4. No spaces around the `=` sign

### "No module named..."

**Problem:** Dependencies not installed or wrong environment

**Solution:**
1. Verify venv is activated: `(venv)` in prompt
2. Reinstall: `pip install -r requirements.txt`
3. Try: `pip install --upgrade [module_name]`

### "Permission denied" or "Access denied"

**Problem:** File in use or insufficient permissions

**Solution:**
1. Close any programs using the audio files
2. Run terminal as administrator (Windows)
3. Check file permissions
4. Try moving files manually first

### Script runs but no output

**Problem:** Input folders empty or wrong paths

**Solution:**
1. Verify files are in correct input folders
2. Check file extensions (.m4a for audio, .txt for text)
3. Review class paths in `config.py`
4. Check terminal for error messages

### API rate limit errors

**Problem:** Too many requests to Gemini

**Solution:**
1. Reduce `MAX_LLM_WORKERS` in `config.py`
2. Process fewer classes at once
3. Wait a few minutes between runs
4. Check API quota at Google AI Studio

### Slow processing

**Problem:** Transcription or API calls taking too long

**Solution:**
1. Use smaller Whisper model: `WHISPER_MODEL = 'tiny'`
2. Increase workers: `MAX_AUDIO_WORKERS = 8` (up to # CPU cores)
3. Process classes individually
4. Upgrade to faster Gemini model if needed

---

## Optimization Tips

### For Faster Transcription

```python
# In config.py

# Use smallest model (fastest, less accurate)
WHISPER_MODEL = 'tiny'

# Increase workers (use CPU core count)
MAX_AUDIO_WORKERS = 8  # Check with Task Manager
```

### For Better Quality

```python
# Use larger model (slower, more accurate)
WHISPER_MODEL = 'base'  # or 'small'

# Use better Gemini model
GEMINI_MODEL = 'gemini-2.5-pro'

# Allow longer outputs
MAX_OUTPUT_TOKENS = 12000
```

### For Cost Efficiency

```python
# Use free/cheaper model
GEMINI_MODEL = 'gemini-2.0-flash-exp'

# Reduce output length
MAX_OUTPUT_TOKENS = 6000

# Process in smaller batches
MAX_LLM_WORKERS = 3
```

---

## Maintenance

### Updating Dependencies

```bash
# Activate venv
source venv/bin/activate  # or venv\Scripts\activate

# Update all
pip install --upgrade -r requirements.txt

# Or update specific package
pip install --upgrade google-generativeai
```

### Backing Up Settings

Save these files when backing up:
- `.env` (API keys)
- `src/config.py` (your class paths)
- `prompts/*.md` (your custom prompts)

### Cleaning Up

**Clear processed files:**
```bash
# After verifying outputs are good
rm -rf */LLM/lecture-processed/*
rm -rf */LLM/reading-processed/*
```

**Clear all outputs (start fresh):**
```bash
rm -rf */LLM/*-output/*
rm -rf new-outputs-safe-delete/*
```

---

## Getting Help

1. **Check README.md** for general information
2. **Review error messages** in terminal (often self-explanatory)
3. **Test components individually:**
   - Whisper: `whisper --help`
   - Python: `python --version`
   - FFmpeg: `ffmpeg -version`
4. **Check API status:** [Google AI Studio](https://makersuite.google.com/)
5. **Verify file paths** are correct and accessible

---

## Next Steps

After successful setup:

1. **Customize prompts** in `prompts/` folder
2. **Adjust settings** in `config.py` for your needs
3. **Create workflow** for regular note generation
4. **Backup important outputs** regularly
5. **Review quality** and refine prompts as needed

Good luck with your law school studies! 📚⚖️
