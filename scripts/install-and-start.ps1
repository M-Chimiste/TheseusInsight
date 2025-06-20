# Installation and startup script for Theseus Insight (Windows PowerShell)
# This script installs all dependencies and starts both frontend and backend servers

param(
    [switch]$InstallOnly,
    [switch]$StartOnly,
    [switch]$Help
)

# Colors for output
$InfoColor = "Cyan"
$SuccessColor = "Green"
$WarningColor = "Yellow"
$ErrorColor = "Red"

# Function to print colored messages
function Write-Status {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor $InfoColor
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor $SuccessColor
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor $WarningColor
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor $ErrorColor
}

# Function to check if command exists
function Test-Command {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

# Function to check Python installation
function Test-Python {
    Write-Status "Checking Python installation..."
    
    $pythonCmd = $null
    if (Test-Command "python") {
        $pythonCmd = "python"
    }
    elseif (Test-Command "python3") {
        $pythonCmd = "python3"
    }
    
    if (-not $pythonCmd) {
        Write-Error "Python is not installed or not in PATH."
        Write-Host ""
        Write-Host "Installation instructions:"
        Write-Host "  1. Download Python 3.8+ from: https://www.python.org/downloads/"
        Write-Host "  2. Make sure to check 'Add Python to PATH' during installation"
        Write-Host "  3. Restart PowerShell and try again"
        Write-Host ""
        return $false
    }
    
    Write-Success "Python found:"
    & $pythonCmd --version
    $script:PythonCommand = $pythonCmd
    return $true
}

# Function to check Node.js installation
function Test-NodeJS {
    Write-Status "Checking Node.js installation..."
    
    if (-not (Test-Command "node")) {
        Write-Error "Node.js is not installed or not in PATH."
        Write-Host ""
        Write-Host "Installation instructions:"
        Write-Host "  1. Download Node.js LTS from: https://nodejs.org/"
        Write-Host "  2. Run the installer and follow the prompts"
        Write-Host "  3. Restart PowerShell and try again"
        Write-Host ""
        return $false
    }
    
    if (-not (Test-Command "npm")) {
        Write-Error "npm is not installed or not in PATH."
        Write-Host ""
        Write-Host "npm should come with Node.js. Please reinstall Node.js from:"
        Write-Host "https://nodejs.org/"
        Write-Host ""
        return $false
    }
    
    Write-Success "Node.js and npm found:"
    node --version
    npm --version
    return $true
}

# Function to create directories
function New-Directories {
    Write-Status "Creating necessary directories..."
    
    $directories = @(
        "data",
        "data\newsletters",
        "data\podcasts", 
        "data\visualizations",
        "data\temp",
        "config"
    )
    
    foreach ($dir in $directories) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
            Write-Status "Created directory: $dir"
        }
    }
    
    Write-Success "Directory structure created"
}

# Function to setup Python environment
function Initialize-PythonEnvironment {
    Write-Status "Setting up Python environment..."
    
    # Create virtual environment if it doesn't exist
    if (-not (Test-Path "venv")) {
        Write-Status "Creating virtual environment..."
        & $script:PythonCommand -m venv venv
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to create virtual environment"
            return $false
        }
    }
    
    # Activate virtual environment
    Write-Status "Activating virtual environment..."
    & "venv\Scripts\Activate.ps1"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to activate virtual environment"
        return $false
    }
    
    # Upgrade pip
    Write-Status "Upgrading pip..."
    & python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Failed to upgrade pip, continuing anyway..."
    }
    
    # Install Python dependencies
    Write-Status "Installing Python dependencies from requirements.txt..."
    & pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install Python dependencies"
        return $false
    }
    
    Write-Success "Python environment setup complete"
    return $true
}

# Function to setup frontend
function Initialize-Frontend {
    Write-Status "Setting up frontend dependencies..."
    
    if (-not (Test-Path "theseus-ui")) {
        Write-Error "theseus-ui directory not found"
        return $false
    }
    
    Push-Location "theseus-ui"
    
    try {
        # Install npm dependencies
        Write-Status "Installing npm dependencies..."
        & npm install
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to install npm dependencies"
            return $false
        }
        
        # Build the frontend
        Write-Status "Building frontend..."
        & npm run build
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to build frontend"
            return $false
        }
        
        Write-Success "Frontend setup complete"
        return $true
    }
    finally {
        Pop-Location
    }
}

# Function to create default config files
function New-DefaultConfigs {
    Write-Status "Creating default configuration files..."
    
    if (-not (Test-Path "config\research_interests.txt")) {
        $content = @"
# Research Interests
# Add your research interests here, one per line
# Example:
# machine learning
# natural language processing
# computer vision
# artificial intelligence
# deep learning
"@
        $content | Out-File -FilePath "config\research_interests.txt" -Encoding UTF8
        Write-Status "Created default config\research_interests.txt"
    }
    
    Write-Success "Configuration files ready"
}

# Function to start backend server
function Start-BackendServer {
    Write-Status "Starting backend server..."
    
    # Activate virtual environment
    & "venv\Scripts\Activate.ps1"
    
    # Start FastAPI server in background
    Write-Status "Starting FastAPI server on http://localhost:8000"
    $backendJob = Start-Job -ScriptBlock {
        & uvicorn theseus_insight.main:app --host 0.0.0.0 --port 8000 --reload
    }
    
    # Wait for server to start
    Start-Sleep -Seconds 5
    
    Write-Success "Backend server started (Job ID: $($backendJob.Id))"
    return $backendJob
}

# Function to start frontend development server
function Start-FrontendServer {
    Write-Status "Starting frontend development server..."
    
    Push-Location "theseus-ui"
    
    try {
        # Start Vite development server in background
        Write-Status "Starting Vite development server on http://localhost:5173"
        $frontendJob = Start-Job -ScriptBlock {
            Set-Location $using:PWD
            & npm run dev
        }
        
        # Wait for server to start
        Start-Sleep -Seconds 3
        
        Write-Success "Frontend development server started (Job ID: $($frontendJob.Id))"
        return $frontendJob
    }
    finally {
        Pop-Location
    }
}

# Function to show completion message
function Show-Completion {
    Write-Host ""
    Write-Success "🚀 Theseus Insight is running!"
    Write-Host ""
    Write-Host "[INFO] Frontend (UI): http://localhost:5173" -ForegroundColor $InfoColor
    Write-Host "[INFO] Backend (API): http://localhost:8000" -ForegroundColor $InfoColor
    Write-Host "[INFO] API Documentation: http://localhost:8000/docs" -ForegroundColor $InfoColor
    Write-Host ""
    Write-Warning "Press Ctrl+C to stop both servers"
    Write-Host ""
}

# Function to show help
function Show-Help {
    Write-Host "Usage: .\install-and-start.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -InstallOnly      Only install dependencies, don't start servers"
    Write-Host "  -StartOnly        Only start servers (skip installation)"
    Write-Host "  -Help             Show this help message"
    Write-Host ""
    Write-Host "Default behavior: Install dependencies and start servers"
    Write-Host ""
}

# Main execution
function Main {
    if ($Help) {
        Show-Help
        return
    }
    
    Write-Host "🔧 Theseus Insight Installation and Startup Script (PowerShell)" -ForegroundColor Magenta
    Write-Host "=================================================================" -ForegroundColor Magenta
    Write-Host ""
    
    # Check if we're in the right directory
    if (-not (Test-Path "requirements.txt") -or -not (Test-Path "theseus-ui")) {
        Write-Error "Please run this script from the Theseus Insight root directory"
        Write-Status "Expected files/directories: requirements.txt, theseus-ui/"
        return
    }
    
    if (-not $StartOnly) {
        # Installation phase
        Write-Status "🔍 Checking system requirements..."
        if (-not (Test-Python)) { return }
        if (-not (Test-NodeJS)) { return }
        
        Write-Host ""
        Write-Status "📦 Installing dependencies..."
        New-Directories
        if (-not (Initialize-PythonEnvironment)) { return }
        
        Write-Host ""
        if (-not (Initialize-Frontend)) { return }
        
        Write-Host ""
        New-DefaultConfigs
        
        Write-Host ""
        Write-Success "✅ Installation complete!"
        Write-Host ""
    }
    
    if (-not $InstallOnly) {
        # Start servers
        Write-Status "🚀 Starting servers..."
        $backendJob = Start-BackendServer
        
        Write-Host ""
        $frontendJob = Start-FrontendServer
        
        Write-Host ""
        Show-Completion
        
        # Wait for user interrupt
        try {
            while ($true) {
                Start-Sleep -Seconds 1
            }
        }
        finally {
            Write-Status "Stopping servers..."
            if ($backendJob) { Stop-Job $backendJob; Remove-Job $backendJob }
            if ($frontendJob) { Stop-Job $frontendJob; Remove-Job $frontendJob }
            Write-Status "Servers stopped"
        }
    }
    else {
        Write-Success "Installation complete! Run with -StartOnly to start servers."
    }
}

# Run main function
Main 