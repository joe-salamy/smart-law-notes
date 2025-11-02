"""
File movement and copying utilities.
Handles moving processed files and copying outputs.
"""

import shutil
from pathlib import Path
from datetime import datetime

import config


def setup_output_directory() -> Path:
    """
    Create and return the new-outputs-safe-delete directory.

    Returns:
        Path to the output directory
    """
    output_dir = config.NEW_OUTPUTS_DIR

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
    except Exception as e:
        raise Exception(f"Failed to create output directory: {e}")


def move_to_processed(file_path: Path, processed_folder: Path) -> bool:
    """
    Move a file to the processed folder.

    Args:
        file_path: Path to the file to move
        processed_folder: Destination folder

    Returns:
        True if successful, False otherwise
    """
    try:
        processed_folder.mkdir(parents=True, exist_ok=True)
        destination = processed_folder / file_path.name

        # If destination exists, add timestamp to avoid overwriting
        if destination.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            stem = destination.stem
            suffix = destination.suffix
            destination = processed_folder / f"{stem}_{timestamp}{suffix}"

        shutil.move(str(file_path), str(destination))
        return True

    except Exception as e:
        print(f"    ✗ Error moving {file_path.name}: {e}")
        return False


def copy_to_new_outputs(file_path: Path, new_outputs_dir: Path) -> bool:
    """
    Copy a file to the new-outputs-safe-delete directory.

    Args:
        file_path: Path to the file to copy
        new_outputs_dir: Destination directory

    Returns:
        True if successful, False otherwise
    """
    try:
        new_outputs_dir.mkdir(parents=True, exist_ok=True)
        destination = new_outputs_dir / file_path.name

        # If destination exists, add timestamp to avoid overwriting
        if destination.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            stem = destination.stem
            suffix = destination.suffix
            destination = new_outputs_dir / f"{stem}_{timestamp}{suffix}"

        shutil.copy2(str(file_path), str(destination))
        return True

    except Exception as e:
        print(f"    ✗ Error copying {file_path.name} to new-outputs: {e}")
        return False


def move_audio_to_processed(audio_file: Path, processed_audio_folder: Path) -> bool:
    """
    Move an audio file to the processed audio folder.

    Args:
        audio_file: Path to the audio file
        processed_audio_folder: Destination folder for processed audio

    Returns:
        True if successful, False otherwise
    """
    return move_to_processed(audio_file, processed_audio_folder)
