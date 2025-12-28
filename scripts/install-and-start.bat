@echo off
REM Installation and startup script for Theseus Insight (Windows)
REM This script installs all dependencies and starts both frontend and backend servers

setlocal enabledelayedexpansion

REM Colors for output (basic Windows CMD colors)
set "COLOR_INFO=echo [94m[INFO][0m"
set "COLOR_SUCCESS=echo [92m[SUCCESS][0m"
set "COLOR_WARNING=echo [93m[WARNING][0m"
set "COLOR_ERROR=echo [91m[ERROR][0m"

REM Function to print status messages
:print_status
echo [INFO] %~1
goto :eof

:print_success
echo [SUCCESS] %~1
goto :eof

:print_warning
echo [WARNING] %~1
goto :eof

:print_error
echo [ERROR] %~1
goto :eof

REM Function to check if command exists
:command_exists
where %1 >nul 2>&1
if errorlevel 1 (
    exit /b 1
) else (
    exit /b 0
)

REM Function to check Python installation
:check_python
call :print_status "Checking Python installation..."
call :command_exists python
if errorlevel 1 (
    call :command_exists python3
    if errorlevel 1 (
        call :print_error "Python is not installed or not in PATH."
        echo.
        echo Installation instructions:
        echo   1. Download Python 3.8+ from: https://www.python.org/downloads/
        echo   2. Make sure to check "Add Python to PATH" during installation
        echo   3. Restart command prompt and try again
        echo.
        pause
        exit /b 1
    ) else (
        set PYTHON_CMD=python3
    )
) else (
    set PYTHON_CMD=python
)

call :print_success "Python found: "
%PYTHON_CMD% --version
goto :eof

REM Function to check Node.js installation
:check_nodejs
call :print_status "Checking Node.js installation..."
call :command_exists node
if errorlevel 1 (
    call :print_error "Node.js is not installed or not in PATH."
    echo.
    echo Installation instructions:
    echo   1. Download Node.js LTS from: https://nodejs.org/
    echo   2. Run the installer and follow the prompts
    echo   3. Restart command prompt and try again
    echo.
    pause
    exit /b 1
)

call :command_exists npm
if errorlevel 1 (
    call :print_error "npm is not installed or not in PATH."
    echo.
    echo npm should come with Node.js. Please reinstall Node.js from:
    echo https://nodejs.org/
    echo.
    pause
    exit /b 1
)

call :print_success "Node.js and npm found:"
node --version
npm --version
goto :eof

REM Function to create directories
:create_directories
call :print_status "Creating necessary directories..."

if not exist "data" mkdir "data"
if not exist "data\newsletters" mkdir "data\newsletters"
if not exist "data\podcasts" mkdir "data\podcasts"
if not exist "data\visualizations" mkdir "data\visualizations"
if not exist "data\temp" mkdir "data\temp"
if not exist "config" mkdir "config"

call :print_success "Directory structure created"
goto :eof

REM Function to setup Python environment
:setup_python_env
call :print_status "Setting up Python environment..."

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    call :print_status "Creating virtual environment..."
    %PYTHON_CMD% -m venv venv
    if errorlevel 1 (
        call :print_error "Failed to create virtual environment"
        pause
        exit /b 1
    )
)

REM Activate virtual environment
call :print_status "Activating virtual environment..."
call venv\Scripts\activate.bat
if errorlevel 1 (
    call :print_error "Failed to activate virtual environment"
    pause
    exit /b 1
)

REM Upgrade pip
call :print_status "Upgrading pip..."
python -m pip install --upgrade pip
if errorlevel 1 (
    call :print_warning "Failed to upgrade pip, continuing anyway..."
)

REM Install Python dependencies
call :print_status "Installing Python dependencies from requirements.txt..."
pip install -r requirements.txt
if errorlevel 1 (
    call :print_error "Failed to install Python dependencies"
    pause
    exit /b 1
)

call :print_success "Python environment setup complete"
goto :eof

REM Function to setup frontend
:setup_frontend
call :print_status "Setting up frontend dependencies..."

cd theseus-ui
if errorlevel 1 (
    call :print_error "theseus-ui directory not found"
    pause
    exit /b 1
)

REM Install npm dependencies
call :print_status "Installing npm dependencies..."
npm install
if errorlevel 1 (
    call :print_error "Failed to install npm dependencies"
    cd ..
    pause
    exit /b 1
)

REM Build the frontend
call :print_status "Building frontend..."
npm run build
if errorlevel 1 (
    call :print_error "Failed to build frontend"
    cd ..
    pause
    exit /b 1
)

cd ..
call :print_success "Frontend setup complete"
goto :eof

REM Function to check PostgreSQL installation
:check_postgresql
call :print_status "Checking PostgreSQL availability..."

call :command_exists psql
if errorlevel 1 (
    call :print_warning "PostgreSQL client (psql) not found in PATH"
    echo Database setup will be skipped. You can:
    echo   1. Install PostgreSQL locally and run scripts\setup_database.bat
    echo   2. Use Docker Compose which includes PostgreSQL
    echo   3. Use an external PostgreSQL instance
    exit /b 1
) else (
    call :print_success "PostgreSQL client (psql) is available"
    exit /b 0
)

REM Function to setup database
:setup_database
call :print_status "Setting up PostgreSQL database..."

REM Check if we should skip database setup
if "%SKIP_DB_SETUP%"=="true" (
    call :print_warning "Skipping database setup (SKIP_DB_SETUP=true)"
    goto :eof
)

REM Check if PostgreSQL is available
call :check_postgresql
if errorlevel 1 (
    call :print_warning "Skipping database setup - PostgreSQL not available"
    goto :eof
)

REM Check if we're in Docker environment (skip local DB setup)
if "%RUNNING_IN_DOCKER%"=="true" (
    call :print_status "Docker environment detected - skipping local database setup"
    goto :eof
)
if not "%DATABASE_URL%"=="" (
    call :print_status "External database detected - skipping local database setup"
    goto :eof
)

REM Run the database setup script
if exist "scripts\setup_database.bat" (
    call :print_status "Running database setup script..."
    call scripts\setup_database.bat
    if errorlevel 1 (
        call :print_error "Database setup failed"
        echo You can run 'scripts\setup_database.bat' manually later
        echo Or use Docker Compose which includes PostgreSQL
    ) else (
        call :print_success "Database setup completed"
    )
) else (
    call :print_warning "Database setup script not found at scripts\setup_database.bat"
)

goto :eof

REM Function to create default config files
:create_default_configs
call :print_status "Creating default configuration files..."

if not exist "config\research_interests.txt" (
    echo # Research Interests > config\research_interests.txt
    echo # Add your research interests here, one per line >> config\research_interests.txt
    echo # Example: >> config\research_interests.txt
    echo # machine learning >> config\research_interests.txt
    echo # natural language processing >> config\research_interests.txt
    echo # computer vision >> config\research_interests.txt
    echo # artificial intelligence >> config\research_interests.txt
    echo # deep learning >> config\research_interests.txt
    call :print_status "Created default config\research_interests.txt"
)

if not exist ".env" (
    echo # Theseus Insight Configuration > .env
    echo # Copy this file to .env and update with your values >> .env
    echo. >> .env
    echo # Database Configuration (PostgreSQL) >> .env
    echo DATABASE_URL=postgresql://theseus:theseus@localhost:5432/theseusdb >> .env
    echo. >> .env
    echo # API Keys (obtain from respective providers) >> .env
    echo # OPENAI_API_KEY=your_openai_api_key_here >> .env
    echo # ANTHROPIC_API_KEY=your_anthropic_api_key_here >> .env
    echo # GOOGLE_API_KEY=your_google_api_key_here >> .env
    echo. >> .env
    echo # Optional: Local Ollama server >> .env
    echo OLLAMA_URL=http://127.0.0.1:11434 >> .env
    echo. >> .env
    echo # Optional: Gmail for newsletters >> .env
    echo # GMAIL_SENDER_ADDRESS=your_email@gmail.com >> .env
    echo # GMAIL_APP_PASSWORD=your_app_password >> .env
    echo. >> .env
    echo # Optional: Debug mode >> .env
    echo # DEBUG=true >> .env
    call :print_status "Created default .env file"
    call :print_warning "Please edit .env file with your configuration"
)

call :print_success "Configuration files ready"
goto :eof

REM Function to start backend server
:start_backend
call :print_status "Starting backend server..."

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Start FastAPI server in background
call :print_status "Starting FastAPI server on http://localhost:8000"
start "Theseus Backend" cmd /c "uvicorn theseus_insight.main:app --host 0.0.0.0 --port 8000 --reload"

REM Wait for server to start
timeout /t 5 /nobreak >nul

call :print_success "Backend server started"
goto :eof

REM Function to start frontend development server
:start_frontend
call :print_status "Starting frontend development server..."

cd theseus-ui

REM Start Vite development server in background
call :print_status "Starting Vite development server on http://localhost:5173"
start "Theseus Frontend" cmd /c "npm run dev"

cd ..

REM Wait for server to start
timeout /t 3 /nobreak >nul

call :print_success "Frontend development server started"
goto :eof

REM Function to show completion message
:show_completion
echo.
call :print_success "🚀 Theseus Insight is running!"
echo.
echo [INFO] Frontend (UI): http://localhost:5173
echo [INFO] Backend (API): http://localhost:8000
echo [INFO] API Documentation: http://localhost:8000/docs
echo.
call :print_warning "Both servers are running in separate windows."
call :print_warning "Close those windows to stop the servers."
echo.
goto :eof

REM Main execution
:main
echo 🔧 Theseus Insight Installation and Startup Script (Windows)
echo ==============================================================
echo.

REM Check if we're in the right directory
if not exist "requirements.txt" (
    call :print_error "requirements.txt not found!"
    call :print_status "Please run this script from the Theseus Insight root directory"
    pause
    exit /b 1
)

if not exist "theseus-ui" (
    call :print_error "theseus-ui directory not found!"
    call :print_status "Please run this script from the Theseus Insight root directory"
    pause
    exit /b 1
)

REM Parse command line arguments
set INSTALL_ONLY=false
set START_ONLY=false

:parse_args
if "%1"=="--install-only" (
    set INSTALL_ONLY=true
    shift
    goto parse_args
)
if "%1"=="--start-only" (
    set START_ONLY=true
    shift
    goto parse_args
)
if "%1"=="--help" goto show_help
if "%1"=="-h" goto show_help
if "%1"=="/?" goto show_help

if "%START_ONLY%"=="false" (
    REM Installation phase
    call :print_status "🔍 Checking system requirements..."
    call :check_python
    if errorlevel 1 exit /b 1
    
    call :check_nodejs
    if errorlevel 1 exit /b 1
    
    echo.
    call :print_status "📦 Installing dependencies..."
    call :create_directories
    call :setup_python_env
    if errorlevel 1 exit /b 1
    
    echo.
    call :setup_frontend
    if errorlevel 1 exit /b 1
    
    echo.
    call :create_default_configs
    
    echo.
    call :setup_database
    
    echo.
    call :print_success "✅ Installation complete!"
    echo.
    call :print_status "🎯 Profile Features Enabled:"
    call :print_status "  • Multiple research profiles with separate interests"
    call :print_status "  • Profile-specific paper scoring and recommendations"
    call :print_status "  • Profile-aware trends analysis"
    call :print_status "  • Newsletter generation for specific profiles"
    call :print_status "  • Smart profile selection UI in the frontend"
    echo.
)

if "%INSTALL_ONLY%"=="false" (
    REM Start servers
    call :print_status "🚀 Starting servers..."
    call :start_backend
    
    echo.
    call :start_frontend
    
    echo.
    call :show_completion
) else (
    call :print_success "Installation complete! Run with --start-only to start servers."
    pause
)

goto :eof

:show_help
echo Usage: %0 [OPTIONS]
echo.
echo Options:
echo   --install-only    Only install dependencies, don't start servers
echo   --start-only      Only start servers (skip installation)
echo   --help, -h, /?    Show this help message
echo.
echo Default behavior: Install dependencies and start servers
echo.
pause
goto :eof

REM Call main function
call :main %* 