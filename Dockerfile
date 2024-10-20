FROM python:3.11-bullseye

# Open port 7860 for http service
ENV FAST_API_PORT=7860
EXPOSE 7860

# Install Python dependencies
COPY *.py .
COPY ./requirements.txt requirements.txt

ENV DAILY_API_KEY=${DAILY_API_KEY}
ENV DAILY_SAMPLE_ROOM_URL=${DAILY_SAMPLE_ROOM_URL}
ENV OPENAI_API_KEY=${OPENAI_API_KEY}

RUN pip3 install --no-cache-dir --upgrade -r requirements.txt

# Start the FastAPI server
CMD python3 realtime_server.py --port ${FAST_API_PORT}