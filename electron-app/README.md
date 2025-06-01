# 🚀 Theseus Insight - Universal Build System

**One script to rule them all!** This consolidated build system creates complete, self-contained, signed desktop applications for macOS, Windows, and Linux.

## ✨ Features

- ✅ **Cross-platform** - macOS, Windows, Linux
- ✅ **Self-contained** - Full Python runtime bundled (~1GB)
- ✅ **Code signing** - Developer ID signed for macOS
- ✅ **Fast builds** - 22-85 seconds (vs 5+ minute hangs)
- ✅ **Multi-architecture** - x64, ARM64 support
- ✅ **Distribution ready** - DMG/installer creation
- ✅ **Automatic cleanup** - Optimized for sharing

## 🚀 Quick Start

```bash
# Build for current platform (recommended)
npm run build

# Platform-specific builds
npm run build:mac     # macOS (both x64 + arm64)
npm run build:win     # Windows x64
npm run build:linux   # Linux x64

# Architecture-specific builds
npm run build:mac:arm64   # macOS ARM64 only
npm run build:mac:x64     # macOS x64 only
```

## 📋 Build Output

### macOS
- **Output**: `Theseus Insight-0.9.4-arm64.dmg` (signed DMG)
- **Size**: ~355MB (compressed), ~1.2GB installed
- **Distribution**: Share DMG, users right-click → "Open"

### Windows
- **Output**: `Theseus Insight Setup 0.9.4.exe` (NSIS installer)
- **Size**: ~350MB installer, ~1.2GB installed
- **Distribution**: Standard installer experience

### Linux
- **Output**: `Theseus Insight-0.9.4.AppImage` + `.deb` package
- **Size**: ~350MB files, ~1.2GB installed
- **Distribution**: Universal AppImage or DEB for Debian/Ubuntu

## 🏗️ Build Process

The unified script handles everything:

1. **Prerequisites** - Checks certificates, dependencies
2. **Python Runtime** - Creates standalone virtual environment
3. **Frontend** - Builds React UI from `../theseus-ui`
4. **Backend Bundle** - Packages Python backend
5. **Electron Build** - Creates unsigned app
6. **Code Signing** - Signs with Developer ID (macOS)
7. **Packaging** - Creates DMG/installer
8. **Distribution Prep** - Optimizes for sharing

## 📦 What's Included

### Complete Python Environment
```
python_runtime/
├── bin/python3          # Standalone Python interpreter
├── lib/python3.x/       # Full Python standard library
├── site-packages/       # All dependencies from requirements.txt
└── include/             # Python headers
```

### Frontend Assets
```
theseus-ui/dist/         # Built React application
├── index.html           # Main HTML file
├── assets/              # JS, CSS, images
└── ...                  # Optimized production build
```

### Backend Application
```
theseus_insight/         # Complete Python backend
├── main modules         # Core application logic
├── config/              # Configuration files
└── data/                # Application data
```

## 🔐 Code Signing

### macOS (Automatic)
- **Certificate**: Developer ID Application: Christian Merrill (4H8Z97B24M)
- **Entitlements**: Hardened Runtime enabled
- **Verification**: Automatic signature verification
- **Gatekeeper**: Right-click to open (non-notarized)

### Windows (Certificate Required)
- **Status**: Ready for certificate-based signing
- **Setup**: Add certificate thumbprint to script
- **Signing**: `signtool.exe` integration available

### Linux (No Signing Required)
- **Status**: No code signing needed
- **Distribution**: AppImage + DEB packages
- **Security**: Standard Linux package verification

## 🎯 Distribution Instructions

### For macOS Users:
```
🍎 Installation Instructions:

1. Download Theseus Insight.dmg
2. RIGHT-CLICK the DMG and select "Open"
3. Click "Open" in the security dialog
4. Drag Theseus Insight to Applications folder

Note: Right-clicking bypasses the "damaged" error safely.
This app is code signed but not notarized by Apple.
```

### For Windows Users:
```
🪟 Installation Instructions:

1. Download Theseus Insight Setup.exe
2. Run the installer
3. Follow installation wizard
4. Launch from Start Menu or Desktop

Windows Defender may show a warning for unsigned apps.
Click "More info" → "Run anyway" if prompted.
```

### For Linux Users:
```
🐧 Installation Instructions:

AppImage (Universal):
1. Download Theseus Insight.AppImage
2. Make executable: chmod +x Theseus*.AppImage
3. Double-click to run

DEB Package (Debian/Ubuntu):
1. Download theseus-insight.deb
2. Install: sudo dpkg -i theseus-insight.deb
3. Run from applications menu
```

## 🔧 Troubleshooting

### "Damaged DMG" Error (macOS)
**Solution**: Right-click the DMG and select "Open"
- This is normal for non-notarized apps
- The app is properly signed and safe
- Right-clicking bypasses Gatekeeper warning

### Build Fails
```bash
# Clean everything and retry
rm -rf dist/ python_runtime/ node_modules/.cache/
npm install
npm run build
```

### Missing Dependencies
```bash
# Ensure required tools are installed
node --version    # Requires Node.js 20+
python3 --version # Requires Python 3.9+

# macOS: Install Xcode Command Line Tools
xcode-select --install
```

## 📁 File Structure

```
electron-app/
├── build-app-turnkey.js        # 🎯 MAIN BUILD SCRIPT
├── package.json                # NPM configuration
├── main.js                     # Electron main process
├── icons/                      # App icons (mac/win/linux)
├── build/                      # Build configuration
│   ├── entitlements.mac.plist  # macOS entitlements
│   └── ...
├── dist/                       # Build outputs
├── archive/                    # Old scripts (preserved)
└── docs/
    ├── BUILD_UNIVERSAL_GUIDE.md      # Detailed build guide
    ├── GATEKEEPER_WORKAROUND.md      # macOS signing guide
    └── TROUBLESHOOTING_GUIDE.md      # Common issues
```

## 🚀 Advanced Usage

### Environment Variables
```bash
# Debug mode
DEBUG=electron-builder npm run build

# Skip certificate check (not recommended)
SKIP_CERT_CHECK=true npm run build
```

### CI/CD Integration
```yaml
# GitHub Actions
- name: Build macOS
  run: npm run build:mac
  
- name: Build Windows  
  run: npm run build:win
  
- name: Build Linux
  run: npm run build:linux
```

## 📈 Performance

| Build Type | Time | Output Size | Dependencies |
|------------|------|-------------|--------------|
| **Turnkey** | 22-85s | ~355MB | None (self-contained) |
| **Original** | 5+ min | ~245MB | Requires system Python |

## 🎉 Ready to Ship!

The consolidated build system makes desktop app distribution simple and fast across all platforms. One command builds everything you need to share with users!

```bash
npm run build
# → Ready for distribution! 🚀
```
