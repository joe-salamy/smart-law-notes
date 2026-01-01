"""
LLM processing using Gemini with multithreading.
Generates notes from lecture transcripts and reading texts.
"""

import os
from pathlib import Path
from typing import List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import google.generativeai as genai
from dotenv import load_dotenv

import config
from folder_manager import get_class_paths, get_txt_files
from file_mover import move_to_processed, copy_to_new_outputs
from logger_config import get_logger

# Load environment variables
load_dotenv()

# Initialize logger
logger = get_logger(__name__)


def read_file(filepath: Path) -> Optional[str]:
    """Read and return contents of a file."""
    try:
        logger.debug(f"Reading file: {filepath.name}")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        logger.debug(
            f"File read successfully: {filepath.name} ({len(content)} characters)"
        )
        return content
    except Exception as e:
        logger.error(f"Error reading {filepath.name}: {e}", exc_info=True)
        return None


def load_system_prompt(prompt_file: str, class_name: str) -> Optional[str]:
    """
    Load system prompt from prompts folder and substitute class name.

    Args:
        prompt_file: Name of the prompt file to load
        class_name: Name of the class for context
    """
    prompt_path = config.PROMPT_DIR / prompt_file
    logger.debug(f"Loading system prompt from: {prompt_path}")

    if not prompt_path.exists():
        logger.error(f"Prompt file not found: {prompt_path}")
        raise Exception(f"Prompt file not found: {prompt_path}")

    base_prompt = read_file(prompt_path)
    if base_prompt is None:
        logger.error(f"Failed to read prompt file: {prompt_path}")
        return None

    formatted_prompt = base_prompt.format(class_name=class_name)
    logger.debug(f"System prompt loaded and formatted for class: {class_name}")
    return formatted_prompt


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
    logger.debug(f"Processing content with Gemini ({len(content)} characters)")

    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(f"Gemini API call attempt {attempt}/{max_retries}")
            response = model.generate_content(content)
            logger.debug(f"Gemini response received ({len(response.text)} characters)")
            return response.text
        except Exception as e:
            # Simple exponential backoff for transient failures
            if attempt == max_retries:
                logger.error(
                    f"Gemini API error after {max_retries} attempts: {e}", exc_info=True
                )
                return None
            backoff = 2 ** (attempt - 1)
            logger.warning(
                f"Gemini API error on attempt {attempt}, retrying in {backoff}s: {e}"
            )
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
        logger.debug(f"Processing file: {input_file.name}")
        # Read input file
        content = read_file(input_file)
        if content is None:
            logger.error(f"Failed to read file: {input_file.name}")
            return False, "Failed to read file", input_file

        # Process with Gemini using the shared per-class model
        logger.debug(f"Sending to Gemini: {input_file.name}")
        result = process_with_gemini(model, content)
        if result is None:
            logger.error(f"Gemini API error for file: {input_file.name}")
            return False, "Gemini API error", input_file

        # Save output markdown
        output_file = output_folder / f"{input_file.stem}.md"
        logger.debug(f"Saving output to: {output_file}")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)
        logger.debug(f"Output saved: {output_file.name}")

        # Copy to new-outputs-safe-delete
        logger.debug(f"Copying to new-outputs: {output_file.name}")
        copy_to_new_outputs(output_file, new_outputs_dir)

        # Move input to processed
        logger.debug(f"Moving to processed: {input_file.name}")
        move_to_processed(input_file, processed_folder)

        logger.info(f"Successfully processed: {input_file.name}")
        return True, "Success", input_file

    except Exception as e:
        logger.error(f"Error processing {input_file.name}: {e}", exc_info=True)
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

    logger.debug(
        f"Starting parallel processing of {total_files} files with {config.MAX_LLM_WORKERS} workers"
    )
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
                    logger.info(
                        f"✓ [{successful + failed}/{total_files}] {original_file.name}"
                    )
                    logger.debug(f"Successfully processed {original_file.name}")
                else:
                    failed += 1
                    logger.info(
                        f"✗ [{successful + failed}/{total_files}] {original_file.name}: {message}"
                    )
                    logger.error(f"Failed to process {original_file.name}: {message}")

            except Exception as e:
                failed += 1
                logger.error(
                    f"Unexpected error processing {txt_file.name}: {e}", exc_info=True
                )
                logger.info(
                    f"✗ [{successful + failed}/{total_files}] {txt_file.name}: Unexpected error: {e}"
                )

    logger.debug(
        f"Parallel processing complete: {successful} successful, {failed} failed"
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
    class_name = paths["class_name"]

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

    logger.debug(f"Processing {file_type} files for {class_name}")

    if not txt_files:
        logger.info(f"No {file_type} files found")
        return 0, 0

    logger.info(f"Found {len(txt_files)} {file_type} file(s)")
    logger.debug(f"{file_type} files: {[f.name for f in txt_files]}")

    # Load system prompt
    try:
        # Get class name from the folder path
        logger.debug(f"Loading system prompt for {class_name}")
        system_prompt = load_system_prompt(prompt_file, class_name)
        if system_prompt is None:
            logger.error(f"Error loading prompt for {class_name}")
            logger.info(f"✗ Error loading prompt")
            return 0, len(txt_files)
    except Exception as e:
        logger.error(f"Error loading prompt for {class_name}: {e}", exc_info=True)
        logger.info(f"✗ Error loading prompt: {e}")
        return 0, len(txt_files)

    # Configure API and create a single GenerativeModel for this class.
    # Calling genai.configure once and reusing a model instance reduces per-task overhead.
    logger.debug(f"Configuring Gemini API for {class_name}")
    genai.configure(api_key=api_key)
    try:
        logger.debug(f"Creating GenerativeModel: {config.GEMINI_MODEL}")
        model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL, system_instruction=system_prompt
        )
        logger.debug(f"GenerativeModel created successfully")
    except Exception as e:
        logger.error(
            f"Error creating GenerativeModel for {class_name}: {e}", exc_info=True
        )
        logger.info(f"✗ Error creating GenerativeModel: {e}")
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
    logger.debug(f"Starting parallel processing for {class_name}")
    return execute_parallel_processing(task_args, len(txt_files))


def process_all_lectures(classes: List[Path], new_outputs_dir: Path) -> None:
    """Process lecture transcripts for all classes."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not found in .env file")
        raise Exception("GEMINI_API_KEY not found in .env file")

    logger.info(f"Using model: {config.GEMINI_MODEL}")
    logger.info(f"Parallel workers: {config.MAX_LLM_WORKERS}")
    logger.debug(f"Processing lecture transcripts for {len(classes)} classes")

    total_successful = 0
    total_failed = 0

    for class_folder in classes:
        paths = get_class_paths(class_folder)
        class_name = paths["class_name"]
        logger.info("─" * 70)
        logger.info(f"{class_name}:")
        logger.debug(f"Processing class folder: {class_folder}")

        try:
            logger.debug(f"Starting lecture processing for {class_name}")
            successful, failed = process_class_files(
                class_folder,
                is_reading=False,
                new_outputs_dir=new_outputs_dir,
                api_key=api_key,
            )
            total_successful += successful
            total_failed += failed

            if successful > 0:
                logger.info(f"✓ Processed {successful} file(s)")
                logger.debug(
                    f"{class_name}: {successful} lecture files processed successfully"
                )
            if failed > 0:
                logger.info(f"✗ Failed {failed} file(s)")
                logger.warning(f"{class_name}: {failed} lecture files failed")

        except Exception as e:
            logger.error(f"Error processing class {class_name}: {e}", exc_info=True)
            logger.info(f"✗ Error processing class: {e}")

    logger.info("─" * 70)
    logger.info(
        f"Lecture Notes Summary: {total_successful} successful, {total_failed} failed"
    )
    logger.info("─" * 70)
    logger.debug(
        f"Lecture processing completed: {total_successful} successful, {total_failed} failed"
    )


def process_all_readings(classes: List[Path], new_outputs_dir: Path) -> None:
    """Process reading files for all classes."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not found in .env file")
        raise Exception("GEMINI_API_KEY not found in .env file")

    logger.info(f"Using model: {config.GEMINI_MODEL}")
    logger.info(f"Parallel workers: {config.MAX_LLM_WORKERS}")
    logger.debug(f"Processing reading files for {len(classes)} classes")

    total_successful = 0
    total_failed = 0

    for class_folder in classes:
        paths = get_class_paths(class_folder)
        class_name = paths["class_name"]
        logger.info("─" * 70)
        logger.info(f"{class_name}:")
        logger.debug(f"Processing class folder: {class_folder}")

        try:
            logger.debug(f"Starting reading processing for {class_name}")
            successful, failed = process_class_files(
                class_folder,
                is_reading=True,
                new_outputs_dir=new_outputs_dir,
                api_key=api_key,
            )
            total_successful += successful
            total_failed += failed

            if successful > 0:
                logger.info(f"✓ Processed {successful} file(s)")
                logger.debug(
                    f"{class_name}: {successful} reading files processed successfully"
                )
            if failed > 0:
                logger.info(f"✗ Failed {failed} file(s)")
                logger.warning(f"{class_name}: {failed} reading files failed")

        except Exception as e:
            logger.error(f"Error processing class {class_name}: {e}", exc_info=True)
            logger.info(f"✗ Error processing class: {e}")

    logger.info("─" * 70)
    logger.info(
        f"Reading Notes Summary: {total_successful} successful, {total_failed} failed"
    )
    logger.info("─" * 70)
    logger.debug(
        f"Reading processing completed: {total_successful} successful, {total_failed} failed"
    )
