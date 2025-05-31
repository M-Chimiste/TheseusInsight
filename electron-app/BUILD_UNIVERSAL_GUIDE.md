# Universal Cross-Platform Build Guide

## Overview

The **Universal Turnkey Build System** creates self-contained, signed desktop applications for **macOS**, **Windows**, and **Linux** using a single harmonized script.

## Key Features

✅ **Cross-Platform**: Works on macOS, Windows, and Linux  
✅ **Self-Contained**: Bundles full Python runtime (no external dependencies)  
✅ **Fast Builds**: Optimized 3-step process (build → bundle → sign)  
✅ **Platform-Specific Signing**: Handles macOS code signing, Windows certificates, Linux AppImage  
✅ **Unified Interface**: Same commands work everywhere  

## Quick Start

```bash
# Build for current platform
npm run build-turnkey

# Build for specific platform
npm run build-turnkey:mac    # macOS (both x64 and arm64)
npm run build-turnkey:win    # Windows x64
npm run build-turnkey:linux  # Linux x64 (AppImage + deb)
```

## Platform Requirements

### macOS (Host)
- **Node.js 20+**
- **Python 3.9+**
- **Xcode Command Line Tools**
- **Developer ID Certificate** (for signing)

**Output**: `Theseus Insight.dmg` (signed, notarization-ready)

### Windows (Host or Cross-build)
- **Node.js 20+**  
- **Python 3.9+**
- **PowerShell** (for cleanup)
- **Code Signing Certificate** (optional)

**Output**: `Theseus Insight Setup.exe` (NSIS installer)

### Linux (Host or Cross-build)
- **Node.js 20+**
- **Python 3.9+**
- **Standard build tools**

**Output**: `Theseus Insight.AppImage` + `theseus-insight.deb`

## Build Process Overview

The universal script follows this optimized 3-step approach:

### 1. **Build Unsigned App** (Fast)
- Uses `CSC_IDENTITY_AUTO_DISCOVERY=false` to skip individual file signing
- Creates base Electron app without Python runtime
- Takes ~10-15 seconds instead of 5+ minutes

### 2. **Bundle Python Runtime**
- Creates standalone Python virtual environment with `--copies` flag
- Installs all dependencies from `requirements.txt`
- Cleans unnecessary files (tests, docs, media, bytecode)
- Copies runtime into app bundle

### 3. **Sign Complete App** (Platform-Specific)
- **macOS**: Uses `codesign --deep` with entitlements
- **Windows**: Uses `signtool.exe` (if certificate available)  
- **Linux**: No signing required (most distributions)

## Build Architecture

```
build-app-turnkey.js (Universal Script)
├── Platform Detection (mac/win/linux)
├── Python Runtime Bundling
│   ├── python3 -m venv --copies python_runtime
│   ├── pip install -r requirements.txt  
│   └── Cleanup (tests, docs, media files)
├── Frontend Build (React)
├── Unsigned Electron Build
├── Python Runtime Integration
└── Platform-Specific Signing
    ├── macOS: codesign + entitlements
    ├── Windows: signtool (optional)
    └── Linux: no signing needed
```

## Configuration

### Signing Certificates

**macOS**: 
```bash
# Current configuration in script
DEVELOPER_ID="Developer ID Application: Christian Merrill (4H8Z97B24M)"
```

**Windows**:
```bash
# Add your certificate thumbprint
$CERT_THUMBPRINT="YOUR_CERTIFICATE_THUMBPRINT"
signtool sign /sha1 $CERT_THUMBPRINT /t http://timestamp.comodoca.com /fd sha256 "$APP_PATH"
```

### Build Targets

Configured in `package.json`:

```json
{
  "mac": { "arch": ["x64", "arm64"], "target": "dmg" },
  "win": { "arch": ["x64"], "target": "nsis" },  
  "linux": { "arch": ["x64"], "target": ["AppImage", "deb"] }
}
```

## Cross-Platform Compatibility

### File Paths
- Uses `path.join()` for cross-platform paths
- Handles Windows backslashes vs Unix forward slashes

### Commands  
- **Windows**: PowerShell commands for file operations
- **Unix**: Standard bash commands (`find`, `cp`, `rm`)

### Python Runtime
- **Windows**: `python.exe`, `Scripts/` directory
- **Unix**: `python3`, `bin/` directory  

### App Bundle Structure
- **macOS**: `*.app/Contents/Resources/app/python_runtime`
- **Windows**: `*/resources/app/python_runtime`
- **Linux**: `*/resources/app/python_runtime`

## Performance Comparison

| Build Type | Time | Output Size | Dependencies |
|------------|------|-------------|--------------|
| **Original** | 5+ minutes | 245MB | System Python required |
| **Ultra-Minimal** | 86 seconds | 245MB | System Python required |
| **Turnkey (New)** | 22 seconds | 1.2GB | Self-contained |

## Troubleshooting

### Common Issues

**Python Runtime Bundling Fails**:
```bash
# Ensure Python is available
python3 --version  # Unix
python --version   # Windows

# Check virtual environment creation
python3 -m venv test_env --copies
```

**Build Fails on Windows**:
```bash
# Ensure PowerShell execution policy allows scripts
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Code Signing Fails on macOS**:
```bash
# Check certificate availability
security find-identity -v -p codesigning

# Verify entitlements exist
ls -la build/entitlements.mac.plist
```

### Debug Mode

Enable verbose logging:

```bash
# Set debug environment
export DEBUG=electron-builder

# Run with detailed output
node build-app-turnkey.js mac
```

## Advanced Usage

### Custom Architectures

```bash
# Build specific architecture
node build-app-turnkey.js mac arm64    # macOS ARM64 only
node build-app-turnkey.js win x64      # Windows x64 only
```

### CI/CD Integration

```yaml
# GitHub Actions example
name: Cross-Platform Build
on: [push]

jobs:
  build-mac:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
      - run: npm install
      - run: npm run build-turnkey:mac
        
  build-windows:
    runs-on: windows-latest  
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
      - run: npm install
      - run: npm run build-turnkey:win
        
  build-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3  
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
      - run: npm install
      - run: npm run build-turnkey:linux
```

## Distribution

### macOS
- **DMG**: Ready for distribution, Gatekeeper-compatible
- **Notarization**: Add notarization for seamless user experience
- **Size**: ~1.2GB (includes full Python runtime)

### Windows  
- **NSIS Installer**: Traditional Windows installer experience
- **Code Signing**: Reduces Windows Defender warnings
- **Size**: ~1.2GB (includes full Python runtime)

### Linux
- **AppImage**: Universal Linux format, works on most distributions
- **DEB Package**: Debian/Ubuntu package format  
- **Size**: ~1.2GB (includes full Python runtime)

## Migration from Old Scripts

**Replace**:
```bash
bash build-app-signed-turnkey.sh    # Old macOS-only script
```

**With**:
```bash
npm run build-turnkey               # New universal script
```

All functionality is preserved, with added cross-platform support!

## Support

For issues or questions:
1. Check this guide first
2. Review `TROUBLESHOOTING_GUIDE.md`  
3. Examine build logs for specific error messages
4. Test on a clean virtual environment

---

🚀 **The universal build system makes desktop app distribution simple and fast across all platforms!** 