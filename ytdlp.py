# ytdlp.py
import logging
from pathlib import Path
import subprocess
import shutil
import re
import time

# Streamlit-specific logging handler
class StreamlitHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        import streamlit as st
        st.write(log_entry)  # Display log in the Streamlit app

# Set up logging configuration
def setup_logging(video_id, is_streamlit=False):
    """Set up logging for the video processing."""
    log_filename = f"{video_id}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler() if not is_streamlit else StreamlitHandler(),
        ],
    )
    logging.info(f"Logging started for video ID: {video_id}")

def extract_video_info(video_url):
    """Extract video title and ID using yt-dlp CLI."""
    result = subprocess.run(
        ["yt-dlp", "--get-title", "--get-id", "--restrict-filenames", video_url],
        capture_output=True,
        text=True,
        check=True,
    )
    output = result.stdout.strip().split("\n")
    video_title = output[0] if output else "Unknown Title"
    video_id = output[1] if len(output) > 1 else "UnknownID"
    return video_title.strip(), video_id

def process_video(video_url, video_id, log_enabled=False, progress_callback=None, is_streamlit=False):
    """Download and process video audio."""
    video_title, _ = extract_video_info(video_url)

    if log_enabled:
        setup_logging(video_id, is_streamlit)

    # Create a directory for storing audio files
    video_title_path = Path(video_title)
    video_title_path.mkdir(parents=True, exist_ok=True)

    # Download audio to the subdirectory
    if progress_callback:
        progress_callback(f"Downloading audio for {video_title}...")

    # Run yt-dlp to process the video
    process = subprocess.Popen(
        [
            "yt-dlp",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "320k",
            "--split-chapters",
            "--restrict-filenames",
            "--print", f"after_move:FILENAME:%(filepath)s",
            "--print-to-file", f"after_move:%(filepath)s", "fname.txt",
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

    # Read the downloaded filename from fname.txt
    try:
        with open("fname.txt", "r") as file:
            downloaded_file = Path(file.read().strip())
            logging.info(f"Downloaded file: {downloaded_file}")
    except FileNotFoundError:
        logging.error("fname.txt not found. Cannot retrieve the downloaded filename.")
        return

    # Handle chapter-split files
    chapter_files = list(Path(".").glob(f"{downloaded_file.stem} - *.mp3"))

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
                new_name = formatted_name.replace(f" [{video_id}]", "")
            else:
                new_name = chapter_file.name.replace(f" [{video_id}]", "")

            dest = video_title_path / new_name
            shutil.move(str(chapter_file), str(dest))
            logging.info(f"Renamed and moved: {chapter_file} -> {dest}")

        # Remove the main, originally downloaded file
        if downloaded_file.exists():
            downloaded_file.unlink()
            logging.info(f"Removed original main file: {downloaded_file}")

    # Apply ReplayGain (always applied)
    print("About to apply replaygain")
    progress_callback("About to apply replaygain")
    logging.info("About to apply replaygain")
    apply_replaygain(video_title_path, progress_callback)

    return video_title_path if chapter_files else downloaded_file


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
