#!/bin/bash

# Install Python dependencies for Theseus Insight
# This script ensures the backend can run on any Mac

echo "🐍 Theseus Insight Python Dependencies Installer"
echo "================================================"
echo ""

# Check if Python 3 is available
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Python 3 not found!"
    echo ""
    echo "📋 Please install Python 3 first:"
    echo "   Option 1: Install from python.org: https://www.python.org/downloads/"
    echo "   Option 2: Install with Homebrew: brew install python"
    echo "   Option 3: Install with Anaconda: https://www.anaconda.com/download"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1)
echo "✅ Found Python: $PYTHON_VERSION"
echo ""

# Check if pip is available
if ! python3 -m pip --version >/dev/null 2>&1; then
    echo "❌ pip not available!"
    echo ""
    echo "📋 Installing pip..."
    if curl -s https://bootstrap.pypa.io/get-pip.py | python3 -; then
        echo "✅ pip installed successfully"
    else
        echo "❌ Failed to install pip"
        echo "   Please install pip manually: https://pip.pypa.io/en/stable/installation/"
        exit 1
    fi
fi

echo "📦 Installing required packages..."
echo ""

# List of required packages
packages=(
    "fastapi>=0.100.0"
    "uvicorn[standard]>=0.20.0"
    "psycopg2-binary>=2.9.0"
    "sqlalchemy>=2.0.0"
    "pydantic>=2.0.0"
    "python-multipart>=0.0.6"
    "jinja2>=3.1.0"
    "asyncpg>=0.28.0"
    "alembic>=1.12.0"
)

failed_packages=()
successful_packages=()

for package in "${packages[@]}"; do
    package_name=$(echo "$package" | cut -d'>' -f1 | cut -d'=' -f1)
    echo "📦 Installing $package_name..."
    
    if python3 -m pip install --user "$package" --upgrade --quiet; then
        echo "   ✅ $package_name installed successfully"
        successful_packages+=("$package_name")
    else
        echo "   ❌ Failed to install $package_name"
        failed_packages+=("$package_name")
    fi
done

echo ""
echo "📊 Installation Summary:"
echo "   ✅ Successful: ${#successful_packages[@]} packages"
echo "   ❌ Failed: ${#failed_packages[@]} packages"

if [ ${#failed_packages[@]} -gt 0 ]; then
    echo ""
    echo "❌ Failed packages: ${failed_packages[*]}"
    echo ""
    echo "🔧 Troubleshooting suggestions:"
    echo "   1. Try upgrading pip: python3 -m pip install --upgrade pip"
    echo "   2. Install Xcode command line tools: xcode-select --install"
    echo "   3. Try without --user flag (may require sudo)"
    echo "   4. Consider using a virtual environment"
fi

echo ""
echo "🧪 Testing installation..."

# Test each critical package
critical_packages=("fastapi" "uvicorn" "psycopg2" "sqlalchemy" "pydantic")
test_failed=false

for package in "${critical_packages[@]}"; do
    if python3 -c "import $package; print(f'✅ {package.__name__} v{getattr(package, \"__version__\", \"unknown\")}')" 2>/dev/null; then
        echo "   ✅ $package working"
    else
        echo "   ❌ $package not working"
        test_failed=true
    fi
done

echo ""
if [ "$test_failed" = true ]; then
    echo "❌ Some packages failed to install or import properly"
    echo "   The app may not work correctly"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Review error messages above"
    echo "   2. Try manual installation: python3 -m pip install fastapi uvicorn psycopg2-binary"
    echo "   3. Consider using conda instead of pip"
    exit 1
else
    echo "🎉 All dependencies installed successfully!"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Run the app fix script: ./fix-distributed-app.sh"
    echo "   2. Launch Theseus Insight normally"
    echo "   3. The backend should now start properly"
fi

echo ""
echo "📊 Your Python environment:"
echo "   Python: $(which python3)"
echo "   Pip: $(python3 -m pip --version)"
echo "   Install location: $(python3 -m site --user-base)" 