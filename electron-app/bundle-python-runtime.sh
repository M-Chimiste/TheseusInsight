#!/bin/bash

# Bundle a standalone Python runtime with required dependencies for Theseus Insight
# Creates a local virtual environment under electron-app/python_runtime
# This allows the packaged Electron application to run without system Python

set -e

RUNTIME_DIR="python_runtime"

# Remove old runtime
rm -rf "$RUNTIME_DIR"

# Create virtual environment
python3 -m venv "$RUNTIME_DIR"

# Upgrade pip inside the venv
"$RUNTIME_DIR/bin/pip" install --upgrade pip >/dev/null

# Required packages
packages=(
    "fastapi>=0.100.0"
    "uvicorn[standard]>=0.20.0"
    "sqlite-vec"
    "pydantic>=2.0.0"
    "python-multipart>=0.0.6"
    "jinja2>=3.1.0"
)

# Install packages into the venv
"$RUNTIME_DIR/bin/pip" install "${packages[@]}" >/dev/null

echo "✅ Python runtime bundled in $RUNTIME_DIR"
