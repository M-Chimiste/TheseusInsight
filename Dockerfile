# Stage 1: Build React Frontend
FROM node:18-alpine AS frontend-builder

WORKDIR /app/theseus-ui

# Copy package files and install dependencies
COPY ./theseus-ui/package.json ./
COPY ./theseus-ui/package-lock.json ./
# If using yarn, copy yarn.lock instead and use yarn install
RUN npm install

# Copy the rest of the frontend application code
COPY ./theseus-ui/ .

# Build the frontend application
RUN npm run build

# Stage 2: Python Backend
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV POETRY_NO_INTERACTION 1
ENV RUNNING_IN_DOCKER true

# Install system dependencies
# ffmpeg is optional, include if your backend directly processes audio/video with it
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-noto-cjk \
    fontconfig \
    # Add any other system dependencies your application might need
    # For example, if your app uses libraries that need compilation tools: build-essential
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    fc-cache -f -v

# Set working directory for the backend
WORKDIR /app

# Install Python dependencies
# Assuming requirements.txt is in the project root
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the backend application code
# Adjust these COPY commands based on your project structure
COPY ./theseus_insight ./theseus_insight
COPY ./config ./config
COPY main.py .
# Add any other necessary files/folders for the backend (e.g., scripts, utils)

# Copy built frontend from the builder stage
COPY --from=frontend-builder /app/theseus-ui/dist ./static_frontend

# Create the data directory that will be used as a volume mount point
RUN mkdir -p /app/data/newsletters /app/data/podcasts /app/data/visualizations /app/data/temp
# Ensure the directory for the SQLite DB exists within /app/data if it's not at /app/data/papers.db directly
# Example: if DB_PATH is data/papers.db, then /app/data is fine.
# If DB_PATH is data/db/papers.db, then RUN mkdir -p /app/data/db

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
# The host 0.0.0.0 makes it accessible from outside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 