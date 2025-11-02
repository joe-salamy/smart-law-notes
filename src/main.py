"""
Central orchestrator for law school note generation.
Processes lecture audio and reading text files for multiple classes.
"""

import sys
from pathlib import Path

from config import CLASSES
from folder_manager import verify_and_create_folders
from audio_processor import process_all_lectures
from llm_processor import process_all_readings, process_all_lecture_transcripts
from file_mover import setup_output_directory


def main():
    """Main entry point for the law school note generator."""
    print("=" * 70)
    print("LAW SCHOOL NOTE GENERATOR")
    print("=" * 70)

    # Setup new-outputs-safe-delete directory
    try:
        output_dir = setup_output_directory()
        print(f"\n✓ Output directory ready: {output_dir}")
    except Exception as e:
        print(f"\n✗ Error setting up output directory: {e}")
        sys.exit(1)

    # Verify all class folders have correct structure
    print(f"\n{'=' * 70}")
    print("STEP 1: Verifying Folder Structure")
    print("=" * 70)

    for class_folder in CLASSES:
        class_name = Path(class_folder).name
        print(f"\nVerifying: {class_name}")
        try:
            verify_and_create_folders(class_folder)
            print(f"  ✓ Folder structure verified")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            sys.exit(1)

    # Process lecture audio files to transcripts
    print(f"\n{'=' * 70}")
    print("STEP 2: Converting Lecture Audio to Text")
    print("=" * 70)

    try:
        process_all_lectures(CLASSES)
    except Exception as e:
        print(f"\n✗ Error processing lectures: {e}")
        sys.exit(1)

    # Process lecture transcripts with LLM
    print(f"\n{'=' * 70}")
    print("STEP 3: Generating Lecture Notes with LLM")
    print("=" * 70)

    try:
        process_all_lecture_transcripts(CLASSES, output_dir)
    except Exception as e:
        print(f"\n✗ Error processing lecture transcripts: {e}")
        sys.exit(1)

    # Process reading files with LLM
    print(f"\n{'=' * 70}")
    print("STEP 4: Generating Reading Notes with LLM")
    print("=" * 70)

    try:
        process_all_readings(CLASSES, output_dir)
    except Exception as e:
        print(f"\n✗ Error processing readings: {e}")
        sys.exit(1)

    # Final summary
    print(f"\n{'=' * 70}")
    print("PROCESSING COMPLETE!")
    print("=" * 70)
    print(f"\nAll outputs have been saved to:")
    print(f"  - Individual class folders")
    print(f"  - {output_dir}")
    print("\nInput folders should now be empty (files moved to processed/).")
    print("=" * 70)


if __name__ == "__main__":
    main()
