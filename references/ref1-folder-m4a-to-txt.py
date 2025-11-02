import os
import whisper
from pathlib import Path

# --- Configuration Variables ---

# 1. Variable for path to the folder containing M4A files
LECTURES_FOLDER_PATH = Path("C:\\Users\\joesa\\OneDrive\\Documents\\Law school\\Contracts\\Transcripts\\Eitan audio new")

# 2. Variable for the path to output folder 
OUTPUT_FOLDER_PATH = Path("C:\\Users\\joesa\\OneDrive\\Documents\\Law school\\Contracts\\Transcripts\\Eitan txt")

# 3. Variable for path to processed folder 
PROCESSED_FOLDER_PATH = Path("C:\\Users\\joesa\\OneDrive\\Documents\\Law school\\Contracts\\Transcripts\\Eitan audio processed")

# Choose your Whisper model size. 'base' is a good balance of speed and accuracy.
# (I switched to 'tiny' for faster processing.)
# Options: 'tiny', 'base', 'small', 'medium', 'large'
WHISPER_MODEL = 'tiny' 

# --- Script Logic ---

def transcribe_folder(input_dir: Path, output_dir: Path, processed_dir: Path, model_name: str):
    """
    Transcribes all M4A files in an input directory and saves the output 
    TXT files to an output directory.
    """
    
    # Check if the lectures folder exists
    if not input_dir.is_dir():
        print(f"Error: Lecture folder not found at {input_dir}")
        return

    # Create the output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load the Whisper model once for all files
    print(f"Loading Whisper model: {model_name}...")
    try:
        model = whisper.load_model(model_name)
    except Exception as e:
        print(f"Error loading model: {e}")
        print("Make sure you have all dependencies (like FFmpeg) installed.")
        return

    print("Model loaded. Starting transcription...")
    
    # Iterate over all M4A files in the input folder
    for m4a_file in input_dir.glob('*.m4a'):
        print(f"\nProcessing file: {m4a_file.name}")
        
        # Define the output TXT file path in the Downloads folder
        # e.g., 'lecture_1.m4a' -> 'lecture_1_transcription.txt'
        txt_filename = m4a_file.stem + '_transcription.txt'
        txt_output_path = output_dir / txt_filename
        
        try:
            # Perform the transcription
            result = model.transcribe(str(m4a_file))
            transcription = result["text"]
            
            # Save the transcription to the TXT file
            with open(txt_output_path, 'w', encoding='utf-8') as f:
                f.write(transcription)
            
            print(f"Successfully transcribed and saved to: {txt_output_path}")
            
            # Create processed directory if it doesn't exist
            processed_dir.mkdir(parents=True, exist_ok=True)
            
            # Move the M4A file to the processed directory
            processed_file = processed_dir / m4a_file.name
            try:
                m4a_file.rename(processed_file)
                print(f"Moved {m4a_file.name} to processed folder")
            except Exception as e:
                print(f"Error moving file to processed folder: {e}")
            
        except Exception as e:
            print(f"An error occurred while transcribing {m4a_file.name}: {e}")

if __name__ == "__main__":
    transcribe_folder(LECTURES_FOLDER_PATH, OUTPUT_FOLDER_PATH, PROCESSED_FOLDER_PATH, WHISPER_MODEL)