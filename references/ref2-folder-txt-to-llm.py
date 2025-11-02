import os
import sys
import shutil
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ========== CONFIGURATION - EDIT THESE ==========
PROMPT_FILE = "reading.md"    # <-- Change this to the desired prompt file name (e.g., "reading.md", "lecture.md")

CONTRACTS = "c:\\Users\\joesa\\OneDrive\\Documents\\Law school\\Contracts\\LLM"
CIVPRO = "c:\\Users\\joesa\\OneDrive\\Documents\\Law school\\Civ pro\\LLM"
TORTS = "c:\\Users\\joesa\\OneDrive\\Documents\\Law school\\Torts\\LLM"
CLASSES = [CONTRACTS, CIVPRO, TORTS]  # Will iterate through all classes
# ================================================

def read_file(filepath):
    """Read and return the contents of a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

def process_file_with_gemini(txt_content, system_prompt, api_key):
    """Send content to Gemini 2.5 Pro and return the response."""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name='gemini-2.5-pro',
            system_instruction=system_prompt
        )
        
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=9000  # Approximately 6000 words (1.5 tokens per word)
        )
        
        response = model.generate_content(
            txt_content,
            generation_config=generation_config
        )
        return response.text
    except Exception as e:
        print(f"Error processing with Gemini: {e}")
        return None

def move_to_processed(txt_file, processed_folder):
    """Move processed txt file to the processed folder."""
    try:
        processed_folder.mkdir(parents=True, exist_ok=True)
        destination = processed_folder / txt_file.name
        shutil.move(str(txt_file), str(destination))
        print(f"  ✓ Moved to processed folder: {txt_file.name}")
        return True
    except Exception as e:
        print(f"  ✗ Error moving {txt_file.name}: {e}")
        return False

def process_class(class_folder, prompt_file, api_key):
    """Process all files for a single class."""
    input_folder = Path(class_folder) / "LLM input txt"
    output_folder = Path(class_folder) / "LLM output md"
    processed_folder = Path(class_folder) / "Processed inputs"
    
    # Validate input folder
    if not input_folder.exists():
        print(f"  Input folder '{input_folder}' does not exist - skipping")
        return
    
    # Get all txt files
    txt_files = list(input_folder.glob('*.txt'))
    if not txt_files:
        print(f"  No txt files found - skipping")
        return
    
    # Read system prompt
    system_prompt = read_file(prompt_file)
    if system_prompt is None:
        return
    
    # Create output folder if it doesn't exist
    output_folder.mkdir(parents=True, exist_ok=True)
    
    print(f"  Found {len(txt_files)} txt file(s) to process")
    print(f"  Output will be saved to: {output_folder}\n")
    
    # Process each file
    for i, txt_file in enumerate(txt_files, 1):
        print(f"  [{i}/{len(txt_files)}] Processing: {txt_file.name}")
        
        # Read input file
        txt_content = read_file(txt_file)
        if txt_content is None:
            continue
        
        # Process with Gemini
        result = process_file_with_gemini(txt_content, system_prompt, api_key)
        if result is None:
            continue
        
        # Save output
        output_file = output_folder / f"{txt_file.stem}.md"
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"    ✓ Saved: {output_file.name}")
            
            # Move processed file
            move_to_processed(txt_file, processed_folder)
            print()  # Add blank line between files
            
        except Exception as e:
            print(f"    ✗ Error saving {output_file}: {e}\n")

def main():
    # Get API key from environment variable
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env file")
        print("Please create a .env file with: GEMINI_API_KEY=your_api_key_here")
        sys.exit(1)
    
    # Get prompt file path
    script_dir = Path(__file__).parent
    prompt_file = script_dir / "prompts" / PROMPT_FILE
    
    # Validate prompt file
    if not prompt_file.exists():
        print(f"Error: Prompt file '{PROMPT_FILE}' not found at '{prompt_file}'")
        sys.exit(1)
    
    print(f"System prompt loaded from: {prompt_file}")
    print(f"Processing {len(CLASSES)} class(es)\n")
    print("=" * 60)
    
    # Process each class
    for class_folder in CLASSES:
        class_name = Path(class_folder).parent.name  # Get the class name from path
        print(f"\n{'=' * 60}")
        print(f"PROCESSING: {class_name}")
        print('=' * 60)
        process_class(class_folder, prompt_file, api_key)
    
    print("\n" + "=" * 60)
    print("All classes processed!")
    print("=" * 60)

if __name__ == "__main__":
    main()