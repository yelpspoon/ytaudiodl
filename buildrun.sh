#!/bin/bash

# Helper for running in a local dev env.

rm -rf ._*

docker build -t streamlit-ytdlp .
docker run -p 8501:8501 streamlit-ytdlp
