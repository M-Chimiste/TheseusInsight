#!/bin/bash

# Bundle Python dependencies into the Electron app
# This creates a self-contained app that doesn't require external Python packages

echo "🐍 Bundling Python Dependencies for Distribution"
echo "==============================================="
echo ""

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Must be run from electron-app directory"
    echo "   Current directory: $(pwd)"
    echo "   Expected: .../TheseusInsight/electron-app"
    exit 1
fi

# Check if Python 3 is available
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Python 3 not found!"
    echo "   Please install Python 3 first"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1)
echo "✅ Found Python: $PYTHON_VERSION"
echo ""

# Create dependencies directory in the app structure
DEPS_DIR="python_deps"
rm -rf "$DEPS_DIR"
mkdir -p "$DEPS_DIR"

echo "📦 Installing all Python dependencies in one go..."
echo "   This avoids dependency conflicts and ensures compatibility"
echo ""

# List of required packages with specific versions for stability
packages=(
    "fastapi>=0.100.0"
    "uvicorn[standard]>=0.20.0"
    "sqlite-vec"
    "pydantic>=2.0.0"
    "python-multipart>=0.0.6"
    "jinja2>=3.1.0"
)

# Install all packages together to let pip resolve dependencies properly
all_packages="${packages[*]}"
echo "📦 Installing: $all_packages"

if python3 -m pip install --target "$DEPS_DIR" $all_packages --upgrade --quiet; then
    echo "✅ All packages installed successfully"
else
    echo "❌ Failed to install some packages"
    echo "🔧 Trying individual installation as fallback..."
    
    failed_packages=()
    successful_packages=()
    
    for package in "${packages[@]}"; do
        package_name=$(echo "$package" | cut -d'>' -f1 | cut -d'=' -f1)
        echo "📦 Installing $package_name..."
        
        if python3 -m pip install --target "$DEPS_DIR" "$package" --upgrade --quiet; then
            echo "   ✅ $package_name installed successfully"
            successful_packages+=("$package_name")
        else
            echo "   ❌ Failed to install $package_name"
            failed_packages+=("$package_name")
        fi
    done
    
    echo ""
    echo "📊 Individual Installation Summary:"
    echo "   ✅ Successful: ${#successful_packages[@]} packages"
    echo "   ❌ Failed: ${#failed_packages[@]} packages"
    
    if [ ${#failed_packages[@]} -gt 0 ]; then
        echo ""
        echo "❌ Failed packages: ${failed_packages[*]}"
    fi
fi

echo ""
echo "🧪 Testing bundled installation..."

# Get absolute path to deps directory
DEPS_ABS_PATH="$(pwd)/$DEPS_DIR"

# Test each critical package
critical_packages=("fastapi" "uvicorn" "pydantic")
test_failed=false

for package in "${critical_packages[@]}"; do
    echo "   🔍 Testing $package..."
    if env PYTHONPATH="$DEPS_ABS_PATH" python3 -c "import $package; print('Import successful')" >/dev/null 2>&1; then
        # Get version info
        version=$(env PYTHONPATH="$DEPS_ABS_PATH" python3 -c "import $package; print(getattr($package, '__version__', 'unknown'))" 2>/dev/null || echo "unknown")
        echo "   ✅ $package v$version working in bundle"
    else
        echo "   ❌ $package not working in bundle"
        # Show the actual error for debugging
        echo "   🔍 Error details:"
        env PYTHONPATH="$DEPS_ABS_PATH" python3 -c "import $package" 2>&1 | head -2 | sed 's/^/      /'
        test_failed=true
    fi
done

echo ""
if [ "$test_failed" = true ]; then
    echo "❌ Some packages failed to work in bundle"
    echo "   The bundled app may not work correctly"
    exit 1
else
    echo "🎉 All dependencies bundled successfully!"
    echo ""
    echo "📊 Bundle information:"
    echo "   📁 Bundle directory: $DEPS_DIR"
    echo "   📦 Bundle size: $(du -sh "$DEPS_DIR" | cut -f1)"
    echo "   📋 Package count: $(find "$DEPS_DIR" -name "*.dist-info" | wc -l | tr -d ' ') packages"
fi

echo ""
echo "📋 Next steps:"
echo "   1. Run ./build-app-debug.sh to build the app with bundled dependencies"
echo "   2. The built app will be completely self-contained"
echo "   3. Recipients won't need to install any Python packages" 