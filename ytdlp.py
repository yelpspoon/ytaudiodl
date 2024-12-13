import re
import subprocess
import shutil
import time
import logging
from pathlib import Path
import unicodedata
import argparse
import sys

# Timing function decorator
def timing_function(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time
        print(f"Function {func.__name__} executed in {duration:.2f} seconds.")  # Log to terminal
        return result
    return wrapper


# Streamlit-specific logging handler
class StreamlitHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        import streamlit as st
        st.write(log_entry)  # Display log in the Streamlit app


# Set up logging configuration (simplified for Streamlit and command-line)
def setup_logging(video_title, is_streamlit=False):
    """Set up logging for the video processing."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    if is_streamlit:
        handler = StreamlitHandler()
        logging.getLogger().addHandler(handler)
        logging.info("Logging started for Streamlit.")
    else:
        logging.info("Logging started for command line.")


def sanitize_filename(filename):
    """Sanitize a filename by normalizing Unicode and removing invalid characters."""
    # Normalize Unicode characters to ASCII
    normalized = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode('utf-8')
    # Remove invalid characters (anything not alphanumeric, space, period, dash, or underscore)
    sanitized = re.sub(r'[^\w\s\.-]', '', normalized)
    # Collapse multiple spaces and strip leading/trailing spaces
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized


@timing_function
def extract_video_info(video_url):
    """Extract video title and ID using yt-dlp CLI."""
    result = subprocess.run(
        ["yt-dlp", "--get-title", "--get-id", video_url],
        capture_output=True,
        text=True,
        check=True,
    )
    output = result.stdout.strip().split("\n")
    video_title = output[0] if output else "Unknown Title"
    video_id = output[1] if len(output) > 1 else "UnknownID"
    print(f"Video ID: {video_id}")  # Log to terminal
    print(f"Video Title: {video_title}")  # Log to terminal
    return video_title.strip(), video_id


@timing_function
def process_video(video_url, log_enabled=False, progress_callback=None, is_streamlit=False):
    """Download and process video audio."""
    video_title, video_id = extract_video_info(video_url)

    if log_enabled:
        setup_logging(video_title, is_streamlit)

    # Sanitize the video title for creating a valid directory
    sanitized_title = sanitize_filename(video_title)
    video_title_path = Path(sanitized_title)
    video_title_path.mkdir(parents=True, exist_ok=True)

    # Download audio to the subdirectory
    if progress_callback:
        progress_callback(f"Downloading audio for {sanitized_title}...")

    process = subprocess.Popen(
        [
            "yt-dlp",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "320k",
            "--split-chapters",
            "--output", f"{video_title_path}/%(title)s.%(ext)s",
            video_url,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Real-time logging from both stdout and stderr
    for line in process.stdout:
        logging.info(line.strip())  # Log to terminal/Streamlit
        if is_streamlit:
            import streamlit as st
            st.write(line.strip())  # Stream to Streamlit

    for line in process.stderr:
        logging.error(line.strip())  # Log errors to terminal/Streamlit
        if is_streamlit:
            import streamlit as st
            st.write(f"ERROR: {line.strip()}")  # Stream to Streamlit

    # Wait for the process to finish
    process.wait()

    # Handle chapter-split files
    chapter_files = list(Path(".").glob(f"{sanitized_title} - *.mp3"))

    if chapter_files:
        if progress_callback:
            progress_callback("Processing chapter-split files...")
        logging.info("Renaming and moving chapter-split files...")
        for chapter_file in chapter_files:
            match = re.search(r" - (\d+)", chapter_file.name)
            if match:
                number = match.group(1)
                two_digit_number = f"{int(number):02d}"
                formatted_name = chapter_file.name.strip().replace(f" - {number}", f" - {two_digit_number}")
                new_name = sanitize_filename(formatted_name.replace(f" [{video_id}]", ""))
            else:
                new_name = sanitize_filename(chapter_file.name.replace(f" [{video_id}]", ""))

            dest = video_title_path / new_name
            shutil.move(str(chapter_file), str(dest))
            logging.info(f"Renamed and moved: {chapter_file} -> {dest}")

        # Remove the main, originally downloaded file
        main_file = video_title_path / f"{sanitized_title}.mp3"
        if main_file.exists():
            main_file.unlink()
            logging.info(f"Removed original main file: {main_file}")

    # Apply ReplayGain (always applied)
    print("About to apply replaygain")
    progress_callback("About to apply replaygain")
    logging.info("About to apply replaygain")
    apply_replaygain(video_title_path, progress_callback)

    return video_title_path if chapter_files else video_title_path / f"{sanitized_title}.mp3"


def apply_replaygain(video_title_path, progress_callback=None):
    logging.info("Applying ReplayGain...")
    if progress_callback:
        progress_callback("Applying ReplayGain...")

    final_files = list(video_title_path.glob("*.mp3"))
    if not final_files:
        logging.warning("No MP3 files found for ReplayGain processing.")
        if progress_callback:
            progress_callback("No MP3 files found for ReplayGain processing.")
        return

    for file in final_files:
        try:
            # Use subprocess.run to capture both stdout and stderr separately
            command = ["mp3gain", "-r", "-k", "-o", str(file)]
            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode == 0:
                combined_output = result.stdout.strip()
                logging.info(f"ReplayGain applied to {file}: {combined_output}")
                if progress_callback:
                    progress_callback(f"ReplayGain applied to {file}: {combined_output}")
            else:
                combined_output = result.stdout.strip() + "\n" + result.stderr.strip()
                logging.error(f"Error applying ReplayGain to {file}: {combined_output}")
                if progress_callback:
                    progress_callback(f"Error applying ReplayGain to {file}: {combined_output}")
                raise subprocess.CalledProcessError(result.returncode, command, output=combined_output)

        except subprocess.CalledProcessError as e:
            error_message = f"Error applying ReplayGain to {file}: {e.output}"
            logging.error(error_message)
            if progress_callback:
                progress_callback(error_message)
            raise
        except Exception as e:
            error_message = f"Unexpected error applying ReplayGain to {file}: {str(e)}"
            logging.error(error_message)
            if progress_callback:
                progress_callback(error_message)
            raise


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Download and process YouTube video audio.")
    parser.add_argument('--url', required=True, help="YouTube URL to download")
    parser.add_argument('-l', '--log', action='store_true', help="Enable logging to a file")
    parser.add_argument('--streamlit', action='store_true', help="Enable Streamlit-specific logging")
    args = parser.parse_args()
