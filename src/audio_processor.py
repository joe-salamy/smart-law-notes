"""
Audio transcription using Whisper with multiprocessing.
Converts M4A lecture files to text transcripts.
"""

import whisper
from pathlib import Path
from typing import List, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed

import config
from folder_manager import get_class_paths, get_audio_files
from file_mover import move_audio_to_processed


# Module-level cache for the worker process. Each worker will have its own
# interpreter and thus its own copy of this variable.
_WORKER_MODEL = None


def _worker_init(model_name: str):
    """Initializer for worker processes: load the Whisper model once per worker.

    This function is passed to ProcessPoolExecutor(initializer=..., initargs=...).
    It populates the module-level _WORKER_MODEL in each worker process.
    """
    global _WORKER_MODEL
    try:
        _WORKER_MODEL = whisper.load_model(model_name)
    except Exception:
        # Let individual tasks detect and raise errors if model loading fails.
        _WORKER_MODEL = None


def transcribe_single_file(args: Tuple[Path, Path]) -> Tuple[bool, str, Path]:
    """
    Transcribe a single audio file.

    Args:
        args: Tuple of (audio_file, output_folder)

    Returns:
        Tuple of (success, message, audio_file)
    """
    audio_file, output_folder = args

    try:
        # Use the worker-global model if available, otherwise fallback to loading
        # on demand (this keeps backward compatibility if initializer wasn't used).
        global _WORKER_MODEL
        model = _WORKER_MODEL or whisper.load_model(config.WHISPER_MODEL)

        # Transcribe
        result = model.transcribe(str(audio_file))
        transcription = result["text"]

        # Save to txt file
        txt_filename = audio_file.stem + ".txt"
        txt_output_path = output_folder / txt_filename

        with open(txt_output_path, "w", encoding="utf-8") as f:
            f.write(transcription)

        return True, "Successfully transcribed", audio_file

    except Exception as e:
        return False, f"Error: {str(e)}", audio_file


def process_class_lectures(class_folder: Path, model_name: str) -> Tuple[int, int]:
    """
    Process all lecture audio files for a single class.

    Args:
        class_folder: Path to the class root folder
        model_name: Whisper model to use

    Returns:
        Tuple of (successful_count, failed_count)
    """
    paths = get_class_paths(class_folder)
    audio_files = get_audio_files(class_folder)

    if not audio_files:
        print(f"  No audio files found")
        return 0, 0

    print(f"  Found {len(audio_files)} audio file(s)")

    # Prepare arguments for parallel processing
    task_args = [(audio_file, paths["lecture_input"]) for audio_file in audio_files]

    successful = 0
    failed = 0

    # Process files in parallel. Use initializer to load the model once per worker.
    with ProcessPoolExecutor(
        max_workers=config.MAX_AUDIO_WORKERS,
        initializer=_worker_init,
        initargs=(model_name,),
    ) as executor:
        futures = {
            executor.submit(transcribe_single_file, args): args[0] for args in task_args
        }

        for future in as_completed(futures):
            audio_file = futures[future]
            try:
                success, message, original_file = future.result()

                if success:
                    successful += 1
                    # Move the audio file to the processed audio folder
                    moved = move_audio_to_processed(
                        original_file, paths["lecture_processed_audio"]
                    )

                    if moved:
                        moved_msg = "moved to processed audio"
                    else:
                        moved_msg = "failed to move audio"

                    print(
                        f"    ✓ [{successful + failed}/{len(audio_files)}] {original_file.name} ({moved_msg})"
                    )
                else:
                    failed += 1
                    print(
                        f"    ✗ [{successful + failed}/{len(audio_files)}] {original_file.name}: {message}"
                    )

            except Exception as e:
                failed += 1
                print(
                    f"    ✗ [{successful + failed}/{len(audio_files)}] {audio_file.name}: Unexpected error: {e}"
                )

    return successful, failed


def process_all_lectures(classes: List[Path]) -> None:
    """
    Process lecture audio files for all classes.

    Args:
        classes: List of class folder paths
    """
    print(f"\nUsing Whisper model: {config.WHISPER_MODEL}")
    print(f"Parallel workers: {config.MAX_AUDIO_WORKERS}")

    total_successful = 0
    total_failed = 0

    for class_folder in classes:
        paths = get_class_paths(class_folder)
        print(f"\n{paths['class_name']}:")

        try:
            successful, failed = process_class_lectures(
                class_folder, config.WHISPER_MODEL
            )
            total_successful += successful
            total_failed += failed

            if successful > 0:
                print(f"  ✓ Transcribed {successful} file(s)")
            if failed > 0:
                print(f"  ✗ Failed {failed} file(s)")

        except Exception as e:
            print(f"  ✗ Error processing class: {e}")
            total_failed += 1

    print(f"\n{'─' * 70}")
    print(
        f"Transcription Summary: {total_successful} successful, {total_failed} failed"
    )
    print("─" * 70)
