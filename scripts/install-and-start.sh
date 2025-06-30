#!/bin/bash
# Installation and startup script for Theseus Insight (macOS and Linux)
# This script installs all dependencies and starts both frontend and backend servers

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to detect OS
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    else
        echo "unknown"
    fi
}

# Function to install Python if needed
install_python() {
    if command_exists python3; then
        print_success "Python3 is already installed"
        python3 --version
    else
        print_error "Python3 is not installed. Please install Python 3.8+ and try again."
        print_status "Installation instructions:"
        case $(detect_os) in
            "macos")
                print_status "  macOS: brew install python3 (requires Homebrew)"
                print_status "  Or download from: https://www.python.org/downloads/"
                ;;
            "linux")
                print_status "  Ubuntu/Debian: sudo apt update && sudo apt install python3 python3-pip python3-venv"
                print_status "  CentOS/RHEL: sudo yum install python3 python3-pip"
                ;;
        esac
        exit 1
    fi
}

# Function to install Node.js if needed
install_nodejs() {
    if command_exists node && command_exists npm; then
        print_success "Node.js and npm are already installed"
        node --version
        npm --version
    else
        print_error "Node.js and npm are not installed. Please install them and try again."
        print_status "Installation instructions:"
        case $(detect_os) in
            "macos")
                print_status "  macOS: brew install node (requires Homebrew)"
                print_status "  Or download from: https://nodejs.org/"
                ;;
            "linux")
                print_status "  Ubuntu/Debian: curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt-get install -y nodejs"
                print_status "  Or download from: https://nodejs.org/"
                ;;
        esac
        exit 1
    fi
}

# Function to create virtual environment and install Python dependencies
setup_python_env() {
    print_status "Setting up Python environment..."
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        print_status "Creating virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    print_status "Activating virtual environment..."
    source venv/bin/activate
    
    # Upgrade pip
    print_status "Upgrading pip..."
    pip install --upgrade pip
    
    # Install Python dependencies
    print_status "Installing Python dependencies from requirements.txt..."
    pip install -r requirements.txt
    
    print_success "Python environment setup complete"
}

# Function to setup frontend dependencies
setup_frontend() {
    print_status "Setting up frontend dependencies..."
    
    cd theseus-ui
    
    # Install npm dependencies
    print_status "Installing npm dependencies..."
    npm install
    
    # Build the frontend
    print_status "Building frontend..."
    npm run build
    
    cd ..
    print_success "Frontend setup complete"
}

# Function to create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    directories=(
        "data"
        "data/newsletters"
        "data/podcasts"
        "data/visualizations"
        "data/temp"
        "config"
    )
    
    for dir in "${directories[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            print_status "Created directory: $dir"
        fi
    done
    
    print_success "Directory structure created"
}

# Function to check PostgreSQL installation
check_postgresql() {
    print_status "Checking PostgreSQL availability..."
    
    if command_exists psql; then
        print_success "PostgreSQL client (psql) is available"
        return 0
    else
        print_warning "PostgreSQL client (psql) not found in PATH"
        print_status "Database setup will be skipped. You can:"
        print_status "  1. Install PostgreSQL locally and run scripts/setup_database.sh"
        print_status "  2. Use Docker Compose which includes PostgreSQL"
        print_status "  3. Use an external PostgreSQL instance"
        return 1
    fi
}

# Function to setup database
setup_database() {
    print_status "Setting up PostgreSQL database..."
    
    # Check if we should skip database setup
    if [ "$SKIP_DB_SETUP" = "true" ]; then
        print_warning "Skipping database setup (SKIP_DB_SETUP=true)"
        return 0
    fi
    
    # Check if PostgreSQL is available
    if ! check_postgresql; then
        print_warning "Skipping database setup - PostgreSQL not available"
        return 0
    fi
    
    # Check if we're in Docker environment (skip local DB setup)
    if [ "$RUNNING_IN_DOCKER" = "true" ] || [ -n "$DATABASE_URL" ]; then
        print_status "Docker/external database detected - skipping local database setup"
        return 0
    fi
    
    # Run the database setup script
    if [ -f "scripts/setup_database.sh" ]; then
        print_status "Running database setup script..."
        bash scripts/setup_database.sh
        if [ $? -eq 0 ]; then
            print_success "Database setup completed"
        else
            print_error "Database setup failed"
            print_status "You can run 'bash scripts/setup_database.sh' manually later"
            print_status "Or use Docker Compose which includes PostgreSQL"
        fi
    else
        print_warning "Database setup script not found at scripts/setup_database.sh"
    fi
}

# Function to create default config files if they don't exist
create_default_configs() {
    print_status "Creating default configuration files..."
    
    # Create default research interests if it doesn't exist
    if [ ! -f "config/research_interests.txt" ]; then
        cat > config/research_interests.txt << 'EOF'
# Research Interests
# Add your research interests here, one per line
# Example:
# machine learning
# natural language processing
# computer vision
# artificial intelligence
# deep learning
EOF
        print_status "Created default config/research_interests.txt"
    fi
    
    # Create default .env file if it doesn't exist
    if [ ! -f ".env" ]; then
        cat > .env << 'EOF'
# Theseus Insight Configuration
# Copy this file to .env and update with your values

# Database Configuration (PostgreSQL)
DATABASE_URL=postgresql://theseus:theseus@localhost:5432/theseusdb

# API Keys (obtain from respective providers)
# OPENAI_API_KEY=your_openai_api_key_here
# ANTHROPIC_API_KEY=your_anthropic_api_key_here
# GOOGLE_API_KEY=your_google_api_key_here

# Optional: Local Ollama server
OLLAMA_URL=http://127.0.0.1:11434

# Optional: Gmail for newsletters
# GMAIL_SENDER_ADDRESS=your_email@gmail.com
# GMAIL_APP_PASSWORD=your_app_password

# Optional: Debug mode
# DEBUG=true
EOF
        print_status "Created default .env file"
        print_warning "Please edit .env file with your configuration"
    fi
    
    print_success "Configuration files ready"
}

# Function to start the backend server
start_backend() {
    print_status "Starting backend server..."
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Start the FastAPI server
    print_status "Starting FastAPI server on http://localhost:8000"
    uvicorn theseus_insight.main:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!
    
    # Wait a moment for server to start
    sleep 3
    
    # Check if backend started successfully
    if kill -0 $BACKEND_PID 2>/dev/null; then
        print_success "Backend server started successfully (PID: $BACKEND_PID)"
    else
        print_error "Failed to start backend server"
        exit 1
    fi
}

# Function to start the frontend development server
start_frontend() {
    print_status "Starting frontend development server..."
    
    cd theseus-ui
    
    # Start the Vite development server
    print_status "Starting Vite development server on http://localhost:5173"
    npm run dev &
    FRONTEND_PID=$!
    
    cd ..
    
    # Wait a moment for server to start
    sleep 3
    
    # Check if frontend started successfully
    if kill -0 $FRONTEND_PID 2>/dev/null; then
        print_success "Frontend development server started successfully (PID: $FRONTEND_PID)"
    else
        print_error "Failed to start frontend development server"
        exit 1
    fi
}

# Function to cleanup on script exit
cleanup() {
    print_status "Cleaning up..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    print_status "Servers stopped"
}

# Function to wait for user interrupt
wait_for_interrupt() {
    print_success "🚀 Theseus Insight is running!"
    echo ""
    print_status "Frontend (UI): http://localhost:5173"
    print_status "Backend (API): http://localhost:8000"
    print_status "API Documentation: http://localhost:8000/docs"
    echo ""
    print_warning "Press Ctrl+C to stop both servers"
    echo ""
    
    # Wait for interrupt
    trap cleanup EXIT
    while true; do
        sleep 1
    done
}

# Main execution
main() {
    echo "🔧 Theseus Insight Installation and Startup Script"
    echo "=================================================="
    echo ""
    
    print_status "Detected OS: $(detect_os)"
    echo ""
    
    # Check if we're in the right directory
    if [ ! -f "requirements.txt" ] || [ ! -d "theseus-ui" ]; then
        print_error "Please run this script from the Theseus Insight root directory"
        print_status "Expected files/directories: requirements.txt, theseus-ui/"
        exit 1
    fi
    
    # Parse command line arguments
    INSTALL_ONLY=false
    START_ONLY=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --install-only)
                INSTALL_ONLY=true
                shift
                ;;
            --start-only)
                START_ONLY=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --install-only    Only install dependencies, don't start servers"
                echo "  --start-only      Only start servers (skip installation)"
                echo "  --help, -h        Show this help message"
                echo ""
                echo "Default behavior: Install dependencies and start servers"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    if [ "$START_ONLY" = false ]; then
        # Installation phase
        print_status "🔍 Checking system requirements..."
        install_python
        install_nodejs
        echo ""
        
        print_status "📦 Installing dependencies..."
        create_directories
        setup_python_env
        echo ""
        setup_frontend
        echo ""
        create_default_configs
        echo ""
        setup_database
        echo ""
        
        print_success "✅ Installation complete!"
        echo ""
    fi
    
    if [ "$INSTALL_ONLY" = false ]; then
        # Start servers
        print_status "🚀 Starting servers..."
        start_backend
        echo ""
        start_frontend
        echo ""
        
        # Wait for user to stop
        wait_for_interrupt
    else
        print_success "Installation complete! Run with --start-only to start servers."
    fi
}

# Run main function
main "$@" 