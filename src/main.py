"""
Central orchestrator for law school note generation.
Processes lecture audio and reading text files for multiple classes.
"""

import sys
from pathlib import Path
from typing import List
from config import CLASSES
from llm_processor import process_all_readings, process_all_lectures
from folder_manager import verify_and_create_folders
from file_mover import setup_output_directory
from audio_processor import process_all_lectures as process_audio
from logger_config import setup_logging, get_logger

# Initialize logger
logger = get_logger(__name__)


def main():
    """Main entry point for the law school note generator."""
    # Initialize logging first
    setup_logging()

    logger.info("=" * 70)
    logger.info("LAW SCHOOL NOTE GENERATOR")
    logger.info("=" * 70)
    logger.debug(f"Processing {len(CLASSES)} classes")

    # Setup new-outputs-safe-delete directory
    try:
        logger.debug("Setting up output directory")
        output_dir = setup_output_directory()
        logger.info(f"\n✓ Output directory ready: {output_dir}")
        logger.debug(f"Output directory path: {output_dir}")
    except Exception as e:
        logger.error(f"\n✗ Error setting up output directory: {e}", exc_info=True)
        sys.exit(1)

    # Verify all class folders have correct structure
    logger.info(f"\n{'=' * 70}")
    logger.info("STEP 1: Verifying Folder Structure")
    logger.info("=" * 70)

    for class_folder in CLASSES:
        class_name = Path(class_folder).name
        logger.info(f"\nVerifying: {class_name}")
        logger.debug(f"Class folder path: {class_folder}")
        try:
            verify_and_create_folders(class_folder)
            logger.info(f"  ✓ Folder structure verified")
        except Exception as e:
            logger.error(f"  ✗ Error: {e}", exc_info=True)
            sys.exit(1)

    # Process lecture audio files to transcripts
    logger.info(f"\n{'=' * 70}")
    logger.info("STEP 2: Converting Lecture Audio to Text")
    logger.info("=" * 70)

    try:
        logger.debug("Starting audio processing")
        process_audio(CLASSES)
        logger.debug("Audio processing completed")
    except Exception as e:
        logger.error(f"\n✗ Error processing lectures: {e}", exc_info=True)
        sys.exit(1)

    # Process lecture transcripts with LLM
    logger.info(f"\n{'=' * 70}")
    logger.info("STEP 3: Generating Lecture Notes with LLM")
    logger.info("=" * 70)

    try:
        logger.debug("Starting lecture transcript processing")
        process_all_lectures(CLASSES, output_dir)
        logger.debug("Lecture transcript processing completed")
    except Exception as e:
        logger.error(f"\n✗ Error processing lecture transcripts: {e}", exc_info=True)
        sys.exit(1)

    # Process reading files with LLM
    logger.info(f"\n{'=' * 70}")
    logger.info("STEP 4: Generating Reading Notes with LLM")
    logger.info("=" * 70)

    try:
        logger.debug("Starting reading processing")
        process_all_readings(CLASSES, output_dir)
        logger.debug("Reading processing completed")
    except Exception as e:
        logger.error(f"\n✗ Error processing readings: {e}", exc_info=True)
        sys.exit(1)

    # Final summary
    logger.info(f"\n{'=' * 70}")
    logger.info("PROCESSING COMPLETE!")
    logger.info("=" * 70)
    logger.info(f"\nAll outputs have been saved to:")
    logger.info(f"  - Individual class folders")
    logger.info(f"  - {output_dir}")
    logger.info("\nInput folders should now be empty (files moved to processed/).")
    logger.info("=" * 70)
    logger.debug("Program execution completed successfully")


if __name__ == "__main__":
    main()
