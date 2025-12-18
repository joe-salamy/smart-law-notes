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

import numpy as np
import noisereduce as nr
from faster_whisper import WhisperModel
from pydub import AudioSegment
from scipy import signal
from tqdm import tqdm

import config
from folder_manager import get_class_paths, get_audio_files
from file_mover import move_audio_to_processed


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
        _WORKER_MODEL = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads,
        )
    except Exception as e:
        print(f"Error loading model in worker: {e}")
        _WORKER_MODEL = None


def preprocess_audio(audio_file: Path) -> Tuple[np.ndarray, int]:
    """
    Preprocess audio file for optimal transcription.

    Pipeline:
    1. Convert M4A to WAV (16kHz, mono)
    2. Apply noise reduction
    3. Apply bandpass filter (80Hz - 8000Hz) for speech frequencies
    4. Normalize audio levels

    Args:
        audio_file: Path to M4A audio file

    Returns:
        Tuple of (audio_array, sample_rate)
    """
    # Step 1: Convert M4A to WAV (16kHz, mono)
    audio = AudioSegment.from_file(str(audio_file), format="m4a")
    audio = audio.set_frame_rate(16000).set_channels(1)

    # Convert to numpy array
    samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
    samples = samples / (2**15)  # Normalize to [-1, 1]
    sample_rate = audio.frame_rate

    # Step 2: Apply noise reduction
    # Uses stationary noise reduction algorithm
    samples = nr.reduce_noise(y=samples, sr=sample_rate, stationary=True)

    # Step 3: Apply bandpass filter (80Hz - 8000Hz)
    # Focuses on human speech frequency range
    nyquist = sample_rate / 2
    low = 80 / nyquist
    high = 8000 / nyquist
    b, a = signal.butter(4, [low, high], btype="band")
    samples = signal.filtfilt(b, a, samples)

    # Step 4: Normalize audio levels
    # Target: -20dB LUFS (prevents clipping, ensures consistent volume)
    max_amplitude = np.abs(samples).max()
    if max_amplitude > 0:
        target_amplitude = 10 ** (-20 / 20)  # -20dB
        samples = samples * (target_amplitude / max_amplitude)

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
        # Use the worker-global model
        global _WORKER_MODEL
        if _WORKER_MODEL is None:
            return False, "Model not loaded in worker", audio_file

        # Step 1: Preprocess audio
        audio_data, sample_rate = preprocess_audio(audio_file)

        # Save preprocessed audio to temporary WAV file
        temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_wav.close()

        # Convert numpy array back to AudioSegment for saving
        audio_data_int16 = (audio_data * 2**15).astype(np.int16)
        preprocessed_audio = AudioSegment(
            audio_data_int16.tobytes(),
            frame_rate=sample_rate,
            sample_width=2,
            channels=1,
        )
        preprocessed_audio.export(temp_wav.name, format="wav")

        # Step 2: Transcribe with timestamps
        segments, info = _WORKER_MODEL.transcribe(
            temp_wav.name,
            beam_size=5,
            language="en",
            word_timestamps=False,  # Use segment-level timestamps
        )

        # Step 3: Format transcription with timestamps
        transcription_lines = []
        for segment in segments:
            timestamp = format_timestamp(segment.start)
            text = segment.text.strip()
            transcription_lines.append(f"{timestamp} {text}")

        transcription = "\n".join(transcription_lines)

        # Step 4: Save to txt file
        txt_filename = audio_file.stem + ".txt"
        txt_output_path = output_folder / txt_filename

        with open(txt_output_path, "w", encoding="utf-8") as f:
            f.write(transcription)

        # Clean up temporary file
        if temp_wav and os.path.exists(temp_wav.name):
            os.unlink(temp_wav.name)

        return True, "Successfully transcribed", audio_file

    except Exception as e:
        # Clean up temporary file on error
        if temp_wav and os.path.exists(temp_wav.name):
            os.unlink(temp_wav.name)
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
    audio_files = get_audio_files(class_folder)

    if not audio_files:
        print(f"  No audio files found")
        return 0, 0

    print(f"  Found {len(audio_files)} audio file(s)")

    # Prepare arguments for parallel processing
    task_args = [(audio_file, paths["lecture_input"]) for audio_file in audio_files]

    successful = 0
    failed = 0

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
                        # Move the audio file to the processed audio folder
                        moved = move_audio_to_processed(
                            original_file, paths["lecture_processed_audio"]
                        )

                        if moved:
                            moved_msg = "moved to processed audio"
                        else:
                            moved_msg = "failed to move audio"

                        pbar.write(f"    ✓ {original_file.name} ({moved_msg})")
                    else:
                        failed += 1
                        pbar.write(f"    ✗ {original_file.name}: {message}")

                except Exception as e:
                    failed += 1
                    pbar.write(f"    ✗ {audio_file.name}: Unexpected error: {e}")

                pbar.update(1)

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

    print(f"\nUsing faster-whisper model: {model_name}")
    print(f"Device: {device} (compute_type: {compute_type})")
    print(f"CPU threads: {cpu_threads}")
    print(f"Parallel workers: {config.MAX_AUDIO_WORKERS}")

    total_successful = 0
    total_failed = 0

    for class_folder in classes:
        paths = get_class_paths(class_folder)
        print(f"\n{paths['class_name']}:")

        try:
            successful, failed = process_class_lectures(
                class_folder, model_name, device, compute_type, cpu_threads
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
