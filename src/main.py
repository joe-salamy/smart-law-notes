"""
Central orchestrator for law school note generation.
Processes lecture audio and reading text files for multiple classes.
"""

import sys
from config import CLASSES
from llm_processor import process_all_readings, process_all_lectures
from folder_manager import setup_and_verify


def main():
    """Main entry point for the law school note generator."""
    print("=" * 70)
    print("LAW SCHOOL NOTE GENERATOR")
    print("=" * 70)

    # Setup and verify all folders
    output_dir = setup_and_verify(CLASSES)

    # Process lecture transcripts with LLM
    print(f"\n{'=' * 70}")
    print("STEP 3: Generating Lecture Notes with LLM")
    print("=" * 70)

    try:
        process_all_lectures(CLASSES, output_dir)
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
