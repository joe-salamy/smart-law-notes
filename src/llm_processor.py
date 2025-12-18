"""
LLM processing using Gemini with multithreading.
Generates notes from lecture transcripts and reading texts.
"""

import os
from pathlib import Path
from typing import List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import google.generativeai as genai
from dotenv import load_dotenv

import config
from folder_manager import get_class_paths, get_txt_files
from file_mover import move_to_processed, copy_to_new_outputs

# Load environment variables
load_dotenv()


def read_file(filepath: Path) -> Optional[str]:
    """Read and return contents of a file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"    ✗ Error reading {filepath.name}: {e}")
        return None


def load_system_prompt(prompt_file: str, class_name: str) -> Optional[str]:
    """
    Load system prompt from prompts folder and substitute class name.

    Args:
        prompt_file: Name of the prompt file to load
        class_name: Name of the class for context
    """
    prompt_path = config.PROMPT_DIR / prompt_file

    if not prompt_path.exists():
        raise Exception(f"Prompt file not found: {prompt_path}")

    base_prompt = read_file(prompt_path)
    if base_prompt is None:
        return None

    return base_prompt.format(class_name=class_name)


def process_with_gemini(
    model: genai.GenerativeModel, content: str, max_retries: int = 3
) -> Optional[str]:
    """
    Send content to Gemini using a pre-created `GenerativeModel` and return the response.

    This function includes a small retry/backoff loop to handle transient API errors.

    Args:
        model: Pre-configured genai.GenerativeModel instance (created once per class)
        content: Text content to process
        max_retries: Number of attempts (default 3)

    Returns:
        Generated text or None if error
    """
    generation_config = genai.types.GenerationConfig(
        max_output_tokens=config.MAX_OUTPUT_TOKENS
    )

    for attempt in range(1, max_retries + 1):
        try:
            response = model.generate_content(
                content, generation_config=generation_config
            )
            return response.text
        except Exception as e:
            # Simple exponential backoff for transient failures
            if attempt == max_retries:
                return None
            backoff = 2 ** (attempt - 1)
            time.sleep(backoff)
            continue


def process_single_file(
    args: Tuple[Path, genai.GenerativeModel, Path, Path, Path, bool],
) -> Tuple[bool, str, Path]:
    """
    Process a single text file with Gemini.

    Args:
        args: Tuple of (input_file, model, output_folder, processed_folder,
                       new_outputs_dir, is_reading)

    Returns:
        Tuple of (success, message, input_file)
    """
    (
        input_file,
        model,
        output_folder,
        processed_folder,
        new_outputs_dir,
        is_reading,
    ) = args

    try:
        # Read input file
        content = read_file(input_file)
        if content is None:
            return False, "Failed to read file", input_file

        # Process with Gemini using the shared per-class model
        result = process_with_gemini(model, content)
        if result is None:
            return False, "Gemini API error", input_file

        # Save output markdown
        output_file = output_folder / f"{input_file.stem}.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)

        # Copy to new-outputs-safe-delete
        copy_to_new_outputs(output_file, new_outputs_dir)

        # Move input to processed
        move_to_processed(input_file, processed_folder)

        return True, "Success", input_file

    except Exception as e:
        return False, f"Error: {str(e)}", input_file


def execute_parallel_processing(
    task_args: List[Tuple[Path, genai.GenerativeModel, Path, Path, Path, bool]],
    total_files: int,
) -> Tuple[int, int]:
    """
    Execute parallel processing of files using ThreadPoolExecutor.

    Args:
        task_args: List of argument tuples for process_single_file
        total_files: Total number of files to process

    Returns:
        Tuple of (successful_count, failed_count)
    """
    successful = 0
    failed = 0

    # Process files in parallel with threads (I/O bound)
    with ThreadPoolExecutor(max_workers=config.MAX_LLM_WORKERS) as executor:
        futures = {
            executor.submit(process_single_file, args): args[0] for args in task_args
        }

        for future in as_completed(futures):
            txt_file = futures[future]
            try:
                success, message, original_file = future.result()

                if success:
                    successful += 1
                    print(
                        f"    ✓ [{successful + failed}/{total_files}] {original_file.name}"
                    )
                else:
                    failed += 1
                    print(
                        f"    ✗ [{successful + failed}/{total_files}] {original_file.name}: {message}"
                    )

            except Exception as e:
                failed += 1
                print(
                    f"    ✗ [{successful + failed}/{total_files}] {txt_file.name}: Unexpected error: {e}"
                )

    return successful, failed


def process_class_files(
    class_folder: Path, is_reading: bool, new_outputs_dir: Path, api_key: str
) -> Tuple[int, int]:
    """
    Process all files (reading or lecture) for a single class.

    Args:
        class_folder: Path to the class root folder
        is_reading: True for reading files, False for lecture files
        new_outputs_dir: Path to new-outputs-safe-delete directory
        api_key: Gemini API key

    Returns:
        Tuple of (successful_count, failed_count)
    """
    paths = get_class_paths(class_folder)

    # Get appropriate folders and files
    if is_reading:
        txt_files = get_txt_files(class_folder, reading=True)
        output_folder = paths["reading_output"]
        processed_folder = paths["reading_processed"]
        prompt_file = config.READING_PROMPT_FILE
        file_type = "reading"
    else:
        txt_files = get_txt_files(class_folder, reading=False)
        output_folder = paths["lecture_output"]
        processed_folder = paths["lecture_processed_txt"]
        prompt_file = config.LECTURE_PROMPT_FILE
        file_type = "lecture transcript"

    if not txt_files:
        print(f"  No {file_type} files found")
        return 0, 0

    print(f"  Found {len(txt_files)} {file_type} file(s)")

    # Load system prompt
    try:
        # Get class name from the folder path
        class_name = paths["class_name"]
        system_prompt = load_system_prompt(prompt_file, class_name)
        if system_prompt is None:
            print(f"  ✗ Error loading prompt")
            return 0, len(txt_files)
    except Exception as e:
        print(f"  ✗ Error loading prompt: {e}")
        return 0, len(txt_files)

    # Configure API and create a single GenerativeModel for this class.
    # Calling genai.configure once and reusing a model instance reduces per-task overhead.
    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL, system_instruction=system_prompt
        )
    except Exception as e:
        print(f"  ✗ Error creating GenerativeModel: {e}")
        return 0, len(txt_files)

    # Prepare arguments for parallel processing: pass the shared model into each task.
    task_args = [
        (
            txt_file,
            model,
            output_folder,
            processed_folder,
            new_outputs_dir,
            is_reading,
        )
        for txt_file in txt_files
    ]

    # Execute parallel processing
    return execute_parallel_processing(task_args, len(txt_files))


def process_all_lectures(classes: List[Path], new_outputs_dir: Path) -> None:
    """Process lecture transcripts for all classes."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise Exception("GEMINI_API_KEY not found in .env file")

    print(f"\nUsing model: {config.GEMINI_MODEL}")
    print(f"Parallel workers: {config.MAX_LLM_WORKERS}")

    total_successful = 0
    total_failed = 0

    for class_folder in classes:
        paths = get_class_paths(class_folder)
        print(f"\n{paths['class_name']}:")

        try:
            successful, failed = process_class_files(
                class_folder,
                is_reading=False,
                new_outputs_dir=new_outputs_dir,
                api_key=api_key,
            )
            total_successful += successful
            total_failed += failed

            if successful > 0:
                print(f"  ✓ Processed {successful} file(s)")
            if failed > 0:
                print(f"  ✗ Failed {failed} file(s)")

        except Exception as e:
            print(f"  ✗ Error processing class: {e}")

    print(f"\n{'─' * 70}")
    print(
        f"Lecture Notes Summary: {total_successful} successful, {total_failed} failed"
    )
    print("─" * 70)


def process_all_readings(classes: List[Path], new_outputs_dir: Path) -> None:
    """Process reading files for all classes."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise Exception("GEMINI_API_KEY not found in .env file")

    print(f"\nUsing model: {config.GEMINI_MODEL}")
    print(f"Parallel workers: {config.MAX_LLM_WORKERS}")

    total_successful = 0
    total_failed = 0

    for class_folder in classes:
        paths = get_class_paths(class_folder)
        print(f"\n{paths['class_name']}:")

        try:
            successful, failed = process_class_files(
                class_folder,
                is_reading=True,
                new_outputs_dir=new_outputs_dir,
                api_key=api_key,
            )
            total_successful += successful
            total_failed += failed

            if successful > 0:
                print(f"  ✓ Processed {successful} file(s)")
            if failed > 0:
                print(f"  ✗ Failed {failed} file(s)")

        except Exception as e:
            print(f"  ✗ Error processing class: {e}")

    print(f"\n{'─' * 70}")
    print(
        f"Reading Notes Summary: {total_successful} successful, {total_failed} failed"
    )
    print("─" * 70)
