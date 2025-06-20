# Theseus Insight Installation and Startup Scripts

This directory contains scripts to help you quickly install dependencies and start Theseus Insight on different operating systems.

## Quick Start

### macOS / Linux
```bash
# Make the script executable
chmod +x scripts/install-and-start.sh

# Install and start (full setup)
./scripts/install-and-start.sh
```

### Windows (Command Prompt)
```cmd
# Install and start (full setup)
scripts\install-and-start.bat
```

### Windows (PowerShell)
```powershell
# Install and start (full setup)
.\scripts\install-and-start.ps1
```

## Available Scripts

### 1. `install-and-start.sh` (macOS/Linux)
**Usage:**
```bash
./scripts/install-and-start.sh [OPTIONS]
```

**Options:**
- `--install-only` - Only install dependencies, don't start servers
- `--start-only` - Only start servers (skip installation)
- `--help`, `-h` - Show help message

### 2. `install-and-start.bat` (Windows CMD)
**Usage:**
```cmd
scripts\install-and-start.bat [OPTIONS]
```

**Options:**
- `--install-only` - Only install dependencies, don't start servers
- `--start-only` - Only start servers (skip installation)
- `--help`, `-h`, `/?` - Show help message

### 3. `install-and-start.ps1` (Windows PowerShell)
**Usage:**
```powershell
.\scripts\install-and-start.ps1 [OPTIONS]
```

**Options:**
- `-InstallOnly` - Only install dependencies, don't start servers
- `-StartOnly` - Only start servers (skip installation)
- `-Help` - Show help message

## What These Scripts Do

### Installation Phase
1. **Check System Requirements**
   - Verify Python 3.8+ is installed
   - Verify Node.js and npm are installed
   - Provide installation instructions if missing

2. **Create Directory Structure**
   - Create `data/` directory and subdirectories
   - Create `config/` directory
   - Ensure proper directory permissions

3. **Setup Python Environment**
   - Create Python virtual environment (`venv/`)
   - Activate the virtual environment
   - Upgrade pip to latest version
   - Install all Python dependencies from `requirements.txt`

4. **Setup Frontend**
   - Install npm dependencies from `package.json`
   - Build the React frontend using Vite

5. **Create Default Configuration**
   - Generate default `config/research_interests.txt` if not present

### Startup Phase
1. **Start Backend Server**
   - Activate Python virtual environment
   - Start FastAPI server on `http://localhost:8000`
   - Enable auto-reload for development

2. **Start Frontend Development Server**
   - Start Vite development server on `http://localhost:5173`
   - Enable hot module replacement

3. **Provide Access Information**
   - Display URLs for frontend and backend
   - Show API documentation link
   - Explain how to stop the servers

## Prerequisites

### All Platforms
- **Python 3.8+** - Download from [python.org](https://www.python.org/downloads/)
- **Node.js 16+** - Download from [nodejs.org](https://nodejs.org/)

### Platform-Specific Instructions

#### macOS
**Option 1: Using Homebrew (Recommended)**
```bash
# Install Homebrew if not installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install python3 node
```

**Option 2: Download Installers**
- Download Python from [python.org](https://www.python.org/downloads/)
- Download Node.js from [nodejs.org](https://nodejs.org/)

#### Linux (Ubuntu/Debian)
```bash
# Update package index
sudo apt update

# Install Python
sudo apt install python3 python3-pip python3-venv

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt-get install -y nodejs
```

#### Linux (CentOS/RHEL)
```bash
# Install Python
sudo yum install python3 python3-pip

# Install Node.js
curl -fsSL https://rpm.nodesource.com/setup_lts.x | sudo bash -
sudo yum install nodejs
```

#### Windows
1. **Python:**
   - Download from [python.org](https://www.python.org/downloads/)
   - **Important:** Check "Add Python to PATH" during installation

2. **Node.js:**
   - Download from [nodejs.org](https://nodejs.org/)
   - Run the installer and follow prompts

## Common Usage Patterns

### First-Time Setup
```bash
# Full installation and startup
./scripts/install-and-start.sh
```

### Development Workflow
```bash
# Install once
./scripts/install-and-start.sh --install-only

# Start servers when needed
./scripts/install-and-start.sh --start-only
```

### Updating Dependencies
```bash
# Re-run installation to update packages
./scripts/install-and-start.sh --install-only
```

## Troubleshooting

### Common Issues

#### "Command not found" errors
- Ensure Python and Node.js are installed and in your PATH
- Restart your terminal/command prompt after installation
- On Windows, you may need to restart your computer

#### Permission denied (macOS/Linux)
```bash
# Make script executable
chmod +x scripts/install-and-start.sh
```

#### PowerShell execution policy (Windows)
```powershell
# Allow script execution (run as Administrator)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope LocalMachine

# Or run with bypass
powershell -ExecutionPolicy Bypass -File scripts\install-and-start.ps1
```

#### Virtual environment issues
```bash
# Remove existing environment and retry
rm -rf venv
./scripts/install-and-start.sh --install-only
```

#### Port conflicts
If ports 8000 or 5173 are already in use:
- Stop other applications using these ports
- Or modify the ports in the scripts and update your configuration

### Getting Help

1. **Check Prerequisites:** Ensure Python 3.8+ and Node.js 16+ are installed
2. **Run with Help Flag:** Use `--help` to see available options
3. **Check Logs:** Scripts provide detailed output about what's happening
4. **Manual Installation:** If scripts fail, you can install dependencies manually:

```bash
# Backend
python3 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate.bat on Windows
pip install -r requirements.txt

# Frontend
cd theseus-ui
npm install
npm run build
cd ..

# Start servers
uvicorn theseus_insight.main:app --host 0.0.0.0 --port 8000 --reload &
cd theseus-ui && npm run dev
```

## Script Locations

All scripts should be run from the **root directory** of the Theseus Insight project (where `requirements.txt` and `theseus-ui/` are located).

```
theseus-insight/
├── requirements.txt
├── theseus-ui/
├── theseus_insight/
└── scripts/
    ├── install-and-start.sh      # macOS/Linux
    ├── install-and-start.bat     # Windows CMD
    ├── install-and-start.ps1     # Windows PowerShell
    └── README.md                 # This file
```

## Environment Setup

After successful installation, you'll have:

- **Backend API:** Running on `http://localhost:8000`
- **Frontend UI:** Running on `http://localhost:5173`
- **API Docs:** Available at `http://localhost:8000/docs`
- **Virtual Environment:** Python dependencies in `venv/`
- **Built Frontend:** Production build in `theseus-ui/dist/`

The frontend development server includes hot reload, so changes to the UI will be reflected immediately. The backend also runs with auto-reload enabled for development. 