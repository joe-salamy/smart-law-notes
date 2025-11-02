"""
Folder structure verification and creation.
Ensures each class has the required folder hierarchy.
"""

from pathlib import Path
from typing import List
import config


def verify_and_create_folders(class_folder: Path) -> None:
    """
    Verify and create the required folder structure for a class.

    Args:
        class_folder: Path to the class root folder

    Raises:
        Exception: If folder creation fails
    """
    if not isinstance(class_folder, Path):
        class_folder = Path(class_folder)

    if not class_folder.exists():
        raise Exception(f"Class folder does not exist: {class_folder}")

    # Define all required folders
    llm_base = class_folder / config.LLM_BASE

    required_folders = [
        llm_base / config.LECTURE_INPUT,
        llm_base / config.LECTURE_OUTPUT,
        llm_base / config.LECTURE_PROCESSED / config.LECTURE_PROCESSED_AUDIO,
        llm_base / config.LECTURE_PROCESSED / config.LECTURE_PROCESSED_TXT,
        llm_base / config.READING_INPUT,
        llm_base / config.READING_OUTPUT,
        llm_base / config.READING_PROCESSED,
    ]

    # Create all folders
    for folder in required_folders:
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise Exception(f"Failed to create folder {folder}: {e}")

    return None


def get_class_paths(class_folder: Path) -> dict:
    """
    Get all relevant paths for a class.

    Args:
        class_folder: Path to the class root folder

    Returns:
        Dictionary with all folder paths
    """
    if not isinstance(class_folder, Path):
        class_folder = Path(class_folder)

    llm_base = class_folder / config.LLM_BASE

    return {
        "class_name": class_folder.name,
        "lecture_input": llm_base / config.LECTURE_INPUT,
        "lecture_output": llm_base / config.LECTURE_OUTPUT,
        "lecture_processed_audio": llm_base
        / config.LECTURE_PROCESSED
        / config.LECTURE_PROCESSED_AUDIO,
        "lecture_processed_txt": llm_base
        / config.LECTURE_PROCESSED
        / config.LECTURE_PROCESSED_TXT,
        "reading_input": llm_base / config.READING_INPUT,
        "reading_output": llm_base / config.READING_OUTPUT,
        "reading_processed": llm_base / config.READING_PROCESSED,
    }


def get_audio_files(class_folder: Path) -> List[Path]:
    """
    Get all M4A audio files from lecture-input folder.

    Args:
        class_folder: Path to the class root folder

    Returns:
        List of paths to M4A files
    """
    paths = get_class_paths(class_folder)
    lecture_input = paths["lecture_input"]

    if not lecture_input.exists():
        return []

    return list(lecture_input.glob("*.m4a"))


def get_txt_files(class_folder: Path, reading: bool = False) -> List[Path]:
    """
    Get all TXT files from lecture-input or reading-input folder.

    Args:
        class_folder: Path to the class root folder
        reading: If True, get reading files; if False, get lecture files

    Returns:
        List of paths to TXT files
    """
    paths = get_class_paths(class_folder)
    input_folder = paths["reading_input"] if reading else paths["lecture_input"]

    if not input_folder.exists():
        return []

    return list(input_folder.glob("*.txt"))
