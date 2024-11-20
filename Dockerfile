FROM python:3.9-slim-bullseye

# Install required dependencies
RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    curl \
    mp3gain \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install Python dependencies
RUN /usr/local/bin/python -m pip install --upgrade pip
RUN pip install git+https://github.com/yt-dlp/yt-dlp.git streamlit

# Set working directory
WORKDIR "/root"

# Copy application scripts
COPY ytdlp.py /root
COPY app.py /root

# Expose Streamlit default port
EXPOSE 8501

# Set entry point to run the Streamlit app
ENTRYPOINT ["streamlit", "run"]

# Run the Streamlit app
CMD ["app.py"]
