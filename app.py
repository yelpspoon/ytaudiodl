import logging
from pathlib import Path
import subprocess
import shutil
import zipfile
import re
import streamlit as st
import unicodedata


# Streamlit-specific logging handler
class StreamlitHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        st.write(log_entry)  # Display log in the Streamlit app


# Set up logging configuration
def setup_logging(video_id):
    """Set up logging for the video processing."""
    log_filename = f"{video_id}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_filename),
            StreamlitHandler(),
        ],
    )
    logging.info("Logging started for video ID: %s", video_id)


# Helper function for subprocess commands
def os_cmd(command, stream_output=False):
    """
    Execute a shell command and capture its output.

    Args:
        command (list): The command to execute.
        stream_output (bool): Whether to stream output line-by-line.

    Returns:
        tuple: A tuple containing stderr, stdout, and the return code.
    """
    if stream_output:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        stdout, stderr = [], []
        for line in process.stdout:
            logging.info(line.strip())
            stdout.append(line.strip())
        for line in process.stderr:
            logging.error(line.strip())
            stderr.append(line.strip())
        process.wait()
        return "\n".join(stderr), "\n".join(stdout), process.returncode
    else:
        result = subprocess.run(
            command, capture_output=True, text=True
        )
        return result.stderr, result.stdout, result.returncode


def extract_video_info(video_url):
    """Extract video title and ID using yt-dlp CLI."""
    command = ["yt-dlp", "--get-title", "--get-id", "--restrict-filenames", video_url]
    err, out, rc = os_cmd(command)
    if rc != 0:
        logging.error("Error extracting video info: %s", err)
        raise RuntimeError(f"Failed to extract video info: {err}")
    output = out.strip().split("\n")
    video_title = output[0] if output else "Unknown Title"
    video_id = output[1] if len(output) > 1 else "UnknownID"
    return video_title.strip(), video_id


def process_video(video_url, audio_format="mp3", audio_quality="320k", progress_callback=None):
    """Download and process video audio."""
    video_title, video_id = extract_video_info(video_url)

    logging.info("Setting up logging...")
    setup_logging(video_id)
    video_title_path = Path(video_title)
    video_title_path.mkdir(parents=True, exist_ok=True)

    if progress_callback:
        progress_callback(f"Downloading audio for {video_title}...")

    command = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", audio_format,
        "--audio-quality", audio_quality,
        "--split-chapters",
        "--restrict-filenames",
        "--print", f"after_move:FILENAME:%(filepath)s",
        "--print-to-file", f"after_move:%(filepath)s", "fname.txt",
        "--output", f"{video_title_path}/%(title)s.%(ext)s",
        "--paths", f"chapter:{video_title_path}",
        video_url,
    ]
    #   "--output", f"{video_title_path}/%(title)s - %(section_number)02d.%(ext)s",
    err, out, rc = os_cmd(command, stream_output=True)
    if rc != 0:
        logging.error("Error during video processing: %s", err)
        return

    fname_path = Path("fname.txt")
    if not fname_path.exists():
        logging.error("fname.txt not found. Cannot retrieve the downloaded filename.")
        return

    try:
        with fname_path.open("r") as file:
            downloaded_file_name = Path(file.readline().strip())
            logging.info("Downloaded file: %s", downloaded_file_name)
    except Exception as e:
        logging.error("Error reading fname.txt: %s", e)
        return

    # Remove the source file for chapters
    parent_directory = downloaded_file_name.parent
    chapter_files = sorted(parent_directory.glob(f"{downloaded_file_name.stem}*"))
    if downloaded_file_name.exists():
        downloaded_file_name.unlink()
        chapter_files.remove(downloaded_file_name)

    # Rename the files
    video_id_with_dash = f"-[{video_id}]"
    for file in chapter_files:
        logging.info("Processing file: %s", file)

        # remove video ID
        new_name = file.name.replace(video_id_with_dash, "").replace("_", " ")

        # change nnn -> nn
        new_name = re.sub(r'-(\d{3})-', lambda x: f" - {int(x.group(1)):02d}-", new_name)

        dest = parent_directory / new_name
        shutil.move(str(file), str(dest))
        logging.info("Renamed and moved: %s -> %s", file, dest)

    logging.info("All chapter files processed successfully.")

    logging.info("Applying replaygain to: %s", parent_directory)
    apply_replaygain(parent_directory, progress_callback)

    return parent_directory


def apply_replaygain(video_title_path, progress_callback=None):
    """Apply ReplayGain normalization to MP3 files."""
    logging.info("Applying ReplayGain...")
    if progress_callback:
        progress_callback("Applying ReplayGain...")

    final_files = list(video_title_path.glob("*.mp3"))
    if not final_files:
        logging.warning("No MP3 files found for ReplayGain processing.")
        return

    for file in final_files:
        command = ["mp3gain", "-r", "-k", "-o", str(file)]
        err, out, rc = os_cmd(command)
        if rc == 0:
            logging.info("ReplayGain applied to %s", file)
        else:
            logging.error("Error applying ReplayGain to %s: %s", file, err)


def create_zip_file(target_path):
    """Create a ZIP archive of the processed files."""
    zip_path = f"{target_path}.zip"
    with zipfile.ZipFile(zip_path, "w") as zipf:
        if target_path.is_dir():
            for file in target_path.rglob("*"):
                zipf.write(file, arcname=file.relative_to(target_path))
        else:
            zipf.write(target_path, arcname=target_path.name)
    return zip_path


def main():
    st.title("YouTube Audio Downloader and Processor")
    st.write("Enter a YouTube URL to download audio, split chapters, and apply ReplayGain normalization.")

    video_url = st.text_input("YouTube URL", placeholder="Paste the video URL here...")
    audio_format = st.selectbox("Audio Format", ["mp3", "aac", "flac", "wav"], index=0)
    audio_quality = st.selectbox("Audio Quality", ["128k", "192k", "256k", "320k"], index=3)

    if st.button("Process Video"):
        if not video_url:
            st.error("Please provide a valid YouTube URL.")
            return

        try:
            progress_placeholder = st.empty()
            progress_placeholder.text("Starting video processing...")
            result_path = process_video(
                video_url=video_url,
                audio_format=audio_format,
                audio_quality=audio_quality,
                progress_callback=progress_placeholder.text,
            )
            if result_path:
                if result_path.is_dir():
                    download_file = create_zip_file(result_path)
                    mime_type = "application/zip"
                else:
                    download_file = result_path
                    mime_type = "audio/mpeg"

                st.success("Processing complete! Click the button below to download the files.")
                with open(download_file, "rb") as file:
                    st.download_button(
                        label="Download Processed Files",
                        data=file,
                        file_name=Path(download_file).name,
                        mime=mime_type,
                    )
        except Exception as e:
            st.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
