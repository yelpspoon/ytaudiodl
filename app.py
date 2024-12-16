# app.py
import streamlit as st
from pathlib import Path
import shutil
import zipfile
import logging
import subprocess
import re

# --- Streamlit-Specific Functions and UI ---

def prepare_download(video_url, log_enabled=False, progress_callback=None):
    """Prepare audio for download via Streamlit."""
    video_title, video_id = extract_video_info(video_url)

    result = process_video(video_url, video_id, log_enabled, progress_callback, is_streamlit=True)

    if isinstance(result, Path):
        if result.suffix == '.mp3':
            return result
        zip_filename = f"{result.name}.zip"
        with zipfile.ZipFile(zip_filename, "w") as zipf:
            for file in result.iterdir():
                zipf.write(file, arcname=file.name)
        shutil.rmtree(result)
        return Path(zip_filename)
    else:
        raise FileNotFoundError("Download failed or returned invalid data.")

# Streamlit UI
st.title("YouTube Audio Downloader")
st.subheader("Download and process YouTube videos into audio files.")

# Input field for YouTube URL
video_url = st.text_input("Enter YouTube video URL:")

# Logging option
enable_logging = st.checkbox("Enable detailed logging")

# Create columns for layout: one for Process button, one for download button
col1, col2 = st.columns([2, 1])  # Adjust the ratio for button positioning

# Placeholder for progress updates
progress = st.empty()

# Initialize download placeholder for dynamic button rendering
download_placeholder = col2.empty()

# "Process" button
process_button_clicked = col1.button("Process")

if process_button_clicked:
    if video_url:
        try:
            # Define the progress callback
            def progress_callback(message):
                st.markdown(f"<div style='background-color: #BBDEFB; padding: 10px; border-radius: 5px;'>{message}</div>", unsafe_allow_html=True)

            # Start processing and show progress
            progress_callback("Processing video, please wait...")
            result_path = prepare_download(
                video_url, log_enabled=enable_logging, progress_callback=progress_callback
            )

            # Update progress to indicate completion
            progress.markdown(
                '<div style="background-color: #C8E6C9; padding: 10px; border-radius: 5px;">Processing complete! Ready for download.</div>',
                unsafe_allow_html=True
            )

            # Check if the result is a file or a zip
            if result_path.suffix == ".mp3":
                with open(result_path, "rb") as file:
                    download_placeholder.download_button(
                        label="Download Audio File",
                        data=file,
                        file_name=result_path.name,
                        mime="audio/mp3"
                    )
            elif result_path.suffix == ".zip":
                with open(result_path, "rb") as file:
                    download_placeholder.download_button(
                        label="Download Zipped Chapters",
                        data=file,
                        file_name=result_path.name,
                        mime="application/zip"
                    )
        except Exception as e:
            st.markdown(f'<div style="background-color: #FFCDD2; padding: 10px; border-radius: 5px; color: #D32F2F;">An error occurred: {str(e)}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="background-color: #FFF9C4; padding: 10px; border-radius: 5px; color: #F57F17;">Please enter a valid YouTube video URL to proceed.</div>', unsafe_allow_html=True)

# --- Processing Functions (From ytdlp.py) ---

def setup_logging(video_id, is_streamlit=False):
    """Set up logging for video processing."""
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

    process = subprocess.Popen(
        [
            "yt-dlp",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "320k",
            "--split-chapters",
            "--restrict-filenames",
            "--output", f"{video_title_path}/%(title)s.%(ext)s",
            video_url,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Log real-time progress
    for line in process.stdout:
        if is_streamlit:
            st.write(line.strip())
    for line in process.stderr:
        if is_streamlit:
            st.write(f"ERROR: {line.strip()}")

    process.wait()

    # Handle chapter-split files
    chapter_files = list(Path(".").glob(f"{video_title_path.name} - *.mp3"))

    if chapter_files:
        for chapter_file in chapter_files:
            dest = video_title_path / chapter_file.name
            shutil.move(str(chapter_file), str(dest))

    apply_replaygain(video_title_path, progress_callback)
    return video_title_path if chapter_files else None

def apply_replaygain(video_title_path, progress_callback=None):
    """Apply ReplayGain to MP3 files."""
    final_files = list(video_title_path.glob("*.mp3"))
    for file in final_files:
        command = ["mp3gain", "-r", "-k", "-o", str(file)]
        subprocess.run(command)

# Streamlit-specific logging handler
class StreamlitHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        st.write(log_entry)
