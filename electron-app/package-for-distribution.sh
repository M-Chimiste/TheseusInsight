#!/bin/bash

# Package Theseus Insight for distribution
# This script creates a complete distribution package with all fix scripts

echo "📦 Theseus Insight Distribution Packager"
echo "========================================"
echo ""

# Check if build exists
DMG_ARM64="dist/Theseus Insight-0.9.4-arm64.dmg"
DMG_X64="dist/Theseus Insight-0.9.4.dmg"

if [ ! -f "$DMG_ARM64" ]; then
    echo "❌ ARM64 DMG not found: $DMG_ARM64"
    echo "   Run ./build-app-debug.sh first"
    exit 1
fi

echo "✅ Found build files"

# Create distribution directory
DIST_DIR="ThseusInsight-Distribution"
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

echo "📁 Creating distribution package..."

# Copy DMG files
cp "$DMG_ARM64" "$DIST_DIR/"
if [ -f "$DMG_X64" ]; then
    cp "$DMG_X64" "$DIST_DIR/"
    echo "✅ Copied both ARM64 and x64 DMGs"
else
    echo "ℹ️  Copied ARM64 DMG only"
fi

# Copy fix scripts
cp "fix-distributed-app.sh" "$DIST_DIR/"
cp "debug-backend.sh" "$DIST_DIR/"
cp "DISTRIBUTION_README.md" "$DIST_DIR/"

echo "✅ Distribution package created: $DIST_DIR"
echo ""
echo "📋 Package contents:"
echo "   📱 Theseus Insight DMG (self-contained with bundled Python dependencies)"
echo "   🔧 fix-distributed-app.sh (required for AMFI signature fixes)"
echo "   🔍 debug-backend.sh (troubleshooting tool)"
echo "   📄 DISTRIBUTION_README.md (setup instructions)"

# Create a quick start script
cat > "$DIST_DIR/QUICK_START.sh" << 'EOF'
#!/bin/bash

echo "🚀 Theseus Insight Quick Setup"
echo "============================="
echo ""
echo "This will install and fix Theseus Insight in 2 steps:"
echo "1. Fix app signatures (required for macOS security)"
echo "2. Test the app"
echo ""
echo "ℹ️  Note: Python dependencies are now bundled - no installation needed!"
echo ""

read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled"
    exit 1
fi

echo ""
echo "Step 1: Fixing app signatures..."
if ./fix-distributed-app.sh; then
    echo "✅ App signatures fixed"
else
    echo "❌ App signature fixing failed"
    echo "   Please check the error messages above"
    exit 1
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Launch Theseus Insight from Applications"
echo "   2. Wait 10-15 seconds for services to start"
echo "   3. If issues persist, run ./debug-backend.sh"
echo ""
echo "✨ Enjoy your self-contained Theseus Insight app!"
EOF

chmod +x "$DIST_DIR/QUICK_START.sh"

# Create archive
ARCHIVE_NAME="ThseusInsight-v0.9.4-Complete.zip"
echo ""
echo "📦 Creating archive: $ARCHIVE_NAME"

zip -r "$ARCHIVE_NAME" "$DIST_DIR" >/dev/null 2>&1

echo "✅ Archive created successfully"

# Show contents
echo ""
echo "📋 Distribution package contents:"
ls -la "$DIST_DIR"

echo ""
echo "📊 Package size:"
du -sh "$DIST_DIR"
du -sh "$ARCHIVE_NAME"

echo ""
echo "🎉 Distribution package ready!"
echo ""
echo "📧 Share with recipients:"
echo "   1. Send them: $ARCHIVE_NAME"
echo "   2. Instructions: Unzip and run QUICK_START.sh"
echo "   3. Or manual: Follow README.md step by step"
echo ""
echo "🔧 For troubleshooting:"
echo "   - Recipients can run debug-backend.sh"
echo "   - All scripts include detailed error messages"
echo "   - README.md has comprehensive troubleshooting guide" 