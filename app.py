# app.py
import streamlit as st
from ytdlp import process_video, StreamlitHandler, extract_video_info
from pathlib import Path
import shutil
import zipfile

# Function to prepare the downloaded audio for download via Streamlit
def prepare_download(video_url, log_enabled=False, progress_callback=None):
    # Extract video title and ID
    video_title, video_id = extract_video_info(video_url)

    # Process the video and get the output directory or file
    result = process_video(video_url, video_id, log_enabled, progress_callback, is_streamlit=True)

    # Check the result (file or directory)
    if isinstance(result, Path):
        # If result is a file, return it directly
        if result.suffix == '.mp3':
            return result
        # If result is a directory, zip it
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
