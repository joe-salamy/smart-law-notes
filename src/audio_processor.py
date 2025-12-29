"""
Audio transcription using faster-whisper with CPU optimization.
Converts M4A lecture files to text transcripts with timestamps.
Includes audio preprocessing: noise reduction, filtering, normalization.
"""

import os
import tempfile
from pathlib import Path
from typing import List, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
from dotenv import load_dotenv

import numpy as np
import noisereduce as nr
import soundfile as sf
import librosa
from faster_whisper import WhisperModel
from scipy import signal
from tqdm import tqdm
from pydub import AudioSegment

import config
from folder_manager import get_class_paths, get_audio_files
from file_mover import move_audio_to_processed
from logger_config import get_logger

# Load environment variables
load_dotenv()

# Initialize logger
logger = get_logger(__name__)


# Module-level cache for the worker process
_WORKER_MODEL = None


def _worker_init(model_name: str, device: str, compute_type: str, cpu_threads: int):
    """Initializer for worker processes: load the faster-whisper model once per worker.

    Args:
        model_name: Whisper model size (e.g., 'large-v3')
        device: 'cpu' or 'cuda'
        compute_type: 'int8' for CPU, 'float16' for GPU
        cpu_threads: Number of CPU threads to use
    """
    global _WORKER_MODEL
    try:
        # Set HuggingFace token for authenticated downloads
        hf_token = os.getenv("HF_TOKEN")
        if hf_token:
            os.environ["HF_TOKEN"] = hf_token
            logger.debug(f"HF_TOKEN configured for model download")

        logger.info(
            f"[MODEL LOADING] Worker initializing: {model_name} on {device} with {compute_type} (this may take a minute...)"
        )
        logger.info(f"⏳ Loading Whisper model in worker process...")
        _WORKER_MODEL = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads,
        )
        logger.info(f"✓ Whisper model ready in worker")
        logger.info(f"[MODEL READY] Whisper model loaded successfully in worker")
    except Exception as e:
        logger.error(f"Error loading model in worker: {e}", exc_info=True)
        _WORKER_MODEL = None
        raise  # Re-raise to prevent silent failures


def preprocess_audio(audio_file: Path) -> Tuple[np.ndarray, int]:
    """
    Preprocess audio file for optimal transcription.

    Pipeline:
    1. Convert M4A to WAV (16kHz, mono)
    2. Apply noise reduction
    3. Apply bandpass filter (80Hz - 7500Hz) for speech frequencies
    4. Normalize audio levels

    Args:
        audio_file: Path to M4A audio file

    Returns:
        Tuple of (audio_array, sample_rate)
    """
    logger.debug(f"Starting audio preprocessing for: {audio_file.name}")
    temp_wav_path = None

    try:
        # Step 1: Convert M4A to WAV using pydub (handles M4A properly)
        logger.debug(f"[M4A→WAV] Converting {audio_file.name}")
        audio = AudioSegment.from_file(str(audio_file), format="m4a")

        # Create temporary WAV file
        temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_wav_path = temp_wav.name
        temp_wav.close()

        # Export as WAV (16kHz mono)
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(temp_wav_path, format="wav")
        logger.debug(f"[M4A→WAV DONE] Converted to WAV")

        # Load the converted WAV file
        logger.debug(f"[LOAD AUDIO] Loading converted audio at 16kHz mono")
        samples, sample_rate = librosa.load(temp_wav_path, sr=16000, mono=True)
        logger.debug(f"[LOAD AUDIO DONE] {len(samples)} samples at {sample_rate}Hz")
        # samples are already in float32 format normalized to [-1, 1]

    finally:
        # Clean up temporary file
        if temp_wav_path and os.path.exists(temp_wav_path):
            os.unlink(temp_wav_path)
            logger.debug(f"Cleaned up temporary conversion file")

    # Step 2: Apply noise reduction
    # Uses stationary noise reduction algorithm
    logger.debug("Applying noise reduction")
    samples = nr.reduce_noise(y=samples, sr=sample_rate, stationary=True)
    logger.debug("Noise reduction completed")

    # Step 3: Apply bandpass filter (80Hz - 7500Hz)
    # Focuses on human speech frequency range
    # Adjusted to stay below Nyquist frequency (8000Hz for 16kHz sample rate)
    logger.debug("Applying bandpass filter (80Hz - 7500Hz)")
    nyquist = sample_rate / 2
    low = 80 / nyquist
    high = 7500 / nyquist  # Changed from 8000 to 7500 to ensure < 1.0

    # Validate filter frequencies
    if high >= 1.0:
        logger.warning(f"High frequency {high} >= 1.0, adjusting to 0.95")
        high = 0.95

    b, a = signal.butter(4, [low, high], btype="band")
    samples = signal.filtfilt(b, a, samples)
    logger.debug("Bandpass filter applied")

    # Step 4: Normalize audio levels
    # Target: -20dB LUFS (prevents clipping, ensures consistent volume)
    logger.debug("Normalizing audio levels to -20dB")
    max_amplitude = np.abs(samples).max()
    if max_amplitude > 0:
        target_amplitude = 10 ** (-20 / 20)  # -20dB
        samples = samples * (target_amplitude / max_amplitude)
        logger.debug(
            f"Audio normalized: max amplitude {max_amplitude:.4f} -> {target_amplitude:.4f}"
        )
    else:
        logger.warning(f"Audio file has zero amplitude: {audio_file.name}")

    logger.debug(f"Audio preprocessing completed for: {audio_file.name}")
    return samples, sample_rate


def format_timestamp(seconds: float) -> str:
    """
    Format seconds to [HH:MM:SS] timestamp.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"[{hours:02d}:{minutes:02d}:{secs:02d}]"


def transcribe_single_file(args: Tuple[Path, Path]) -> Tuple[bool, str, Path]:
    """
    Transcribe a single audio file with preprocessing and timestamps.

    Args:
        args: Tuple of (audio_file, output_folder)

    Returns:
        Tuple of (success, message, audio_file)
    """
    audio_file, output_folder = args
    temp_wav = None

    try:
        logger.info(f"[WORKER START] Processing: {audio_file.name}")
        # Use the worker-global model
        global _WORKER_MODEL
        if _WORKER_MODEL is None:
            logger.error(f"[ERROR] Model not loaded in worker for {audio_file.name}")
            return False, "Model not loaded in worker", audio_file

        logger.debug(f"[MODEL CHECK] Worker model ready for {audio_file.name}")

        # Step 1: Preprocess audio
        logger.info(f"[PREPROCESSING START] {audio_file.name}")
        audio_data, sample_rate = preprocess_audio(audio_file)
        duration_minutes = len(audio_data) / sample_rate / 60
        logger.info(
            f"[PREPROCESSING DONE] {audio_file.name} - Duration: {duration_minutes:.1f} minutes"
        )

        # Save preprocessed audio to temporary WAV file
        temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_wav.close()
        logger.debug(f"Created temporary WAV file: {temp_wav.name}")

        # Save audio data using soundfile
        sf.write(temp_wav.name, audio_data, sample_rate)
        logger.debug(f"Saved preprocessed audio to temporary file")

        # Step 2: Transcribe with timestamps
        logger.info(
            f"[TRANSCRIPTION START] {audio_file.name} - This may take several minutes..."
        )
        logger.info(f"🔄 Transcribing: {audio_file.name} ({duration_minutes:.1f} min)")
        segments, info = _WORKER_MODEL.transcribe(
            temp_wav.name,
            beam_size=5,
            language="en",
            word_timestamps=False,  # Use segment-level timestamps
        )
        logger.info(
            f"[TRANSCRIPTION DONE] {audio_file.name} - Detected language: {info.language}, Processing segments..."
        )

        # Step 3: Format transcription with timestamps
        transcription_lines = []
        segment_count = 0
        for segment in segments:
            timestamp = format_timestamp(segment.start)
            text = segment.text.strip()
            transcription_lines.append(f"{timestamp} {text}")
            segment_count += 1
            # Log progress every 50 segments
            if segment_count % 50 == 0:
                logger.info(
                    f"[PROGRESS] {audio_file.name} - Processed {segment_count} segments..."
                )

        logger.info(
            f"[SEGMENTS COMPLETE] {audio_file.name} - Total segments: {segment_count}"
        )
        transcription = "\n".join(transcription_lines)

        # Step 4: Save to txt file
        txt_filename = audio_file.stem + ".txt"
        txt_output_path = output_folder / txt_filename
        logger.info(
            f"[SAVING] {audio_file.name} - Writing {len(transcription_lines)} lines to {txt_filename}"
        )

        with open(txt_output_path, "w", encoding="utf-8") as f:
            f.write(transcription)

        logger.info(f"[SAVE COMPLETE] {txt_filename}")

        # Clean up temporary file
        if temp_wav and os.path.exists(temp_wav.name):
            os.unlink(temp_wav.name)
            logger.debug(f"Cleaned up temporary file")

        logger.info(f"[WORKER COMPLETE] ✓ Successfully transcribed: {audio_file.name}")
        return True, "Successfully transcribed", audio_file

    except Exception as e:
        logger.error(f"Error transcribing {audio_file.name}: {e}", exc_info=True)
        # Clean up temporary file on error
        if temp_wav and os.path.exists(temp_wav.name):
            os.unlink(temp_wav.name)
            logger.debug(f"Cleaned up temporary file after error")
        return False, f"Error: {str(e)}", audio_file


def process_class_lectures(
    class_folder: Path,
    model_name: str,
    device: str,
    compute_type: str,
    cpu_threads: int,
) -> Tuple[int, int]:
    """
    Process all lecture audio files for a single class.

    Args:
        class_folder: Path to the class root folder
        model_name: Whisper model to use
        device: 'cpu' or 'cuda'
        compute_type: 'int8' for CPU, 'float16' for GPU
        cpu_threads: Number of CPU threads to use

    Returns:
        Tuple of (successful_count, failed_count)
    """
    paths = get_class_paths(class_folder)
    class_name = paths["class_name"]
    logger.debug(f"Processing lectures for class: {class_name}")

    audio_files = get_audio_files(class_folder)

    if not audio_files:
        logger.info(f"  No audio files found")
        logger.debug(f"No audio files in {paths['lecture_input']}")
        return 0, 0

    logger.info(f"  Found {len(audio_files)} audio file(s)")
    logger.debug(f"Audio files: {[f.name for f in audio_files]}")

    # Prepare arguments for parallel processing
    task_args = [(audio_file, paths["lecture_input"]) for audio_file in audio_files]

    successful = 0
    failed = 0

    logger.debug(
        f"Starting parallel transcription with {config.MAX_AUDIO_WORKERS} workers"
    )

    # Log explanation (progress bar only updates when files complete)
    logger.info(
        f"Note: Progress bar updates when files complete. Watch log file for detailed progress."
    )
    logger.info(f"Monitor with: Get-Content <log_file> -Wait -Tail 50")

    # Process files in parallel with progress bar
    with ProcessPoolExecutor(
        max_workers=config.MAX_AUDIO_WORKERS,
        initializer=_worker_init,
        initargs=(model_name, device, compute_type, cpu_threads),
    ) as executor:
        futures = {
            executor.submit(transcribe_single_file, args): args[0] for args in task_args
        }

        # Progress bar for transcription
        with tqdm(total=len(audio_files), desc="  Transcribing", unit="file") as pbar:
            for future in as_completed(futures):
                audio_file = futures[future]
                try:
                    success, message, original_file = future.result()

                    if success:
                        successful += 1
                        logger.debug(f"Transcription successful: {original_file.name}")
                        # Move the audio file to the processed audio folder
                        moved = move_audio_to_processed(
                            original_file, paths["lecture_processed_audio"]
                        )

                        if moved:
                            moved_msg = "moved to processed audio"
                            logger.debug(
                                f"Audio file moved to processed: {original_file.name}"
                            )
                        else:
                            moved_msg = "failed to move audio"
                            logger.warning(
                                f"Failed to move audio file: {original_file.name}"
                            )

                        pbar.write(f"    ✓ {original_file.name} ({moved_msg})")
                    else:
                        failed += 1
                        logger.error(
                            f"Transcription failed for {original_file.name}: {message}"
                        )
                        pbar.write(f"    ✗ {original_file.name}: {message}")

                except Exception as e:
                    failed += 1
                    logger.error(
                        f"Unexpected error processing {audio_file.name}: {e}",
                        exc_info=True,
                    )
                    pbar.write(f"    ✗ {audio_file.name}: Unexpected error: {e}")

                pbar.update(1)

    logger.debug(
        f"Class transcription complete: {successful} successful, {failed} failed"
    )
    return successful, failed


def process_all_lectures(classes: List[Path]) -> None:
    """
    Process lecture audio files for all classes with CPU-optimized settings.

    Args:
        classes: List of class folder paths
    """
    # CPU-optimized configuration (per instructions)
    device = "cpu"
    compute_type = "int8"  # Faster CPU inference with minimal accuracy loss
    cpu_threads = 4  # Safe limit to avoid overheating/crashing
    model_name = "large-v3"  # Most accurate Whisper model

    logger.info(f"\nUsing faster-whisper model: {model_name}")
    logger.info(f"Device: {device} (compute_type: {compute_type})")
    logger.info(f"CPU threads: {cpu_threads}")
    logger.info(f"Parallel workers: {config.MAX_AUDIO_WORKERS}")
    logger.debug(f"Processing {len(classes)} classes for audio transcription")

    total_successful = 0
    total_failed = 0

    for class_folder in classes:
        paths = get_class_paths(class_folder)
        class_name = paths["class_name"]
        logger.info(f"\n{class_name}:")
        logger.debug(f"Processing class folder: {class_folder}")

        try:
            logger.debug(f"Starting lecture processing for {class_name}")
            successful, failed = process_class_lectures(
                class_folder, model_name, device, compute_type, cpu_threads
            )
            total_successful += successful
            total_failed += failed

            if successful > 0:
                logger.info(f"  ✓ Transcribed {successful} file(s)")
                logger.debug(
                    f"{class_name}: {successful} files transcribed successfully"
                )
            if failed > 0:
                logger.info(f"  ✗ Failed {failed} file(s)")
                logger.warning(f"{class_name}: {failed} files failed transcription")

        except Exception as e:
            logger.error(f"  ✗ Error processing class {class_name}: {e}", exc_info=True)
            total_failed += 1

    logger.info(f"\n{'─' * 70}")
    logger.info(
        f"Transcription Summary: {total_successful} successful, {total_failed} failed"
    )
    logger.info("─" * 70)
    logger.debug(
        f"Audio transcription completed: {total_successful} successful, {total_failed} failed"
    )
