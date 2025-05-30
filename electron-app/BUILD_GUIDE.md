# Theseus Insight Electron App Build Guide

## Overview

This guide covers building the Theseus Insight desktop application for macOS. The build process has been streamlined with automatic PostgreSQL path fixing integrated directly into the build scripts.

## Quick Start

### Prerequisites

1. **Node.js & npm** (version 16 or later)
2. **Xcode Command Line Tools** (for macOS builds)
   ```bash
   xcode-select --install
   ```

### Simple Build Process

The easiest way to build the app:

```bash
cd electron-app
./build-app-debug.sh    # For testing/development
# OR
./build-app.sh          # For production distribution
```

That's it! The scripts handle everything automatically.

## Build Scripts

### 🔧 `build-app-debug.sh` (Recommended for Development)

**Use for:** Local testing, development, sharing with other developers

**Features:**
- ✅ **Automatic PostgreSQL path fixing** - Makes DMGs work on other Macs
- ✅ **No code signing** - Easy to test and distribute 
- ✅ **Architecture detection** - Builds for current Mac (Intel or Apple Silicon)
- ✅ **Build verification** - Confirms paths were fixed correctly
- ✅ **Fast iteration** - Optimized for development workflow

**What it does:**
1. **Step 1:** Fixes PostgreSQL library paths for portability
2. **Step 2:** Builds React UI from `theseus-ui/`
3. **Step 3:** Builds Electron app for current architecture
4. **Step 4:** Verifies no hardcoded paths remain

### 🚀 `build-app.sh` (For Production)

**Use for:** Final distribution, production releases

**Features:**
- ✅ **Automatic PostgreSQL path fixing** 
- ✅ **Cross-platform builds** - Can build for specific architectures
- ✅ **Prerequisites checking** - Validates build environment
- ✅ **Production optimized** - Ready for code signing and notarization

**Usage:**
```bash
./build-app.sh          # Current platform
./build-app.sh mac      # macOS specific
./build-app.sh win      # Windows (future)
./build-app.sh linux    # Linux (future)
```

## What Gets Built

Your built Electron app includes:

- **✅ React UI** - Complete frontend from `theseus-ui/dist`
- **✅ Python Backend** - FastAPI application with all dependencies
- **✅ PostgreSQL** - Self-contained database with **portable paths**
- **✅ Configuration** - All config files and environment templates
- **✅ Assets** - Icons, resources, and static files

## Distribution

### The Path Fixing Solution

**Problem Solved:** Previously, built apps would crash on other Macs with "Library not loaded" errors due to hardcoded PostgreSQL library paths.

**Automatic Solution:** Both build scripts now automatically:
1. Scan PostgreSQL binaries for hardcoded paths like `/Users/c/software_projects/...`
2. Convert them to relative paths using `@loader_path/../lib/`
3. Update both binary dependencies and library IDs
4. Verify the fixes worked correctly

**Result:** DMGs now work immediately on any Mac (after security approval).

### Security & Installation

**For Recipients:**
1. Download and install the DMG
2. First launch: Right-click app → "Open" → "Open" (bypasses Gatekeeper)
3. Or: System Preferences → Security & Privacy → "Open Anyway"

**No Additional Steps Required** - the app is fully self-contained with portable PostgreSQL.

## Troubleshooting

### Build Fails

**Check Prerequisites:**
```bash
node --version    # Should be 16+
npm --version     # Should be 8+
which git         # Should exist
```

**UI Build Issues:**
```bash
cd ../theseus-ui
rm -rf node_modules package-lock.json
npm install
npm run build
```

**Electron Build Issues:**
```bash
cd electron-app
rm -rf node_modules package-lock.json
npm install
```

### App Won't Start on Other Macs

**Check Path Fixing:**
The build scripts include verification. Look for this message:
```
✅ Verification passed: No hardcoded paths in built app
✅ Frontend verification passed: index.html found in built app
```

If you see warnings about missing frontend files:
```
❌ Warning: Frontend directory not found in built app
```

This means the UI wasn't properly bundled. Try:
1. Ensure the UI builds successfully: `cd ../theseus-ui && npm run build`
2. Check that `theseus-ui/dist/` contains `index.html` and `assets/` directory
3. Rebuild the Electron app

**Check Frontend Bundling:**
The build verification shows exactly what's bundled. Look for:
```
✅ Frontend verification passed: index.html found in built app
✅ Frontend assets found: X files in assets directory
```

### UI Shows Blank Screen

**This is usually caused by missing frontend files in the packaged app:**

1. **Verify Frontend Build:**
   ```bash
   cd theseus-ui
   ls -la dist/
   # Should show index.html and assets/ directory
   ```

2. **Check Build Verification Output:**
   The build scripts now verify that frontend files are included. Look for warnings like:
   ```
   ❌ Warning: Frontend directory not found in built app
   ```

3. **Manual Verification:**
   You can manually check if the frontend is bundled:
   ```bash
   # After building, check the app bundle
   find "dist/Theseus Insight.app/Contents/Resources/app" -name "index.html"
   # Should find: .../app/theseus-ui/dist/index.html
   ```

4. **Backend Path Issues:**
   The FastAPI backend includes detailed error messages for frontend serving issues. Check the logs for:
   ```
   ERROR: Frontend serving failed. Details: {...}
   ```

**Use Debug Script:**
Give recipients the `debug-app.sh` script to diagnose issues:
```bash
./debug-app.sh
```

### Performance Issues

**PostgreSQL Startup:**
- First launch takes longer (database initialization)
- Subsequent launches are much faster
- Check Console.app for startup logs

**Memory Usage:**
- Normal: 200-400MB
- High usage: Check for runaway Python processes

## Advanced Options

### Custom Universal Builds

For single DMG supporting both Intel and Apple Silicon:
```bash
npm run build:mac-universal-custom
```

Uses the custom `build-universal.js` script with proper PostgreSQL handling.

### Code Signing & Notarization

For App Store distribution:
1. Get Apple Developer account
2. Configure signing certificate in `package.json`
3. Set up notarization credentials
4. Use production build script

## File Structure

```
electron-app/
├── build-app.sh           # Main production build
├── build-app-debug.sh     # Development build  
├── package.json           # Electron configuration
├── main.js               # Electron main process
├── icons/                # App icons
├── postgres/             # PostgreSQL binaries (auto-fixed)
├── dist/                 # Build output
└── BUILD_GUIDE.md        # This guide
```

## Recent Improvements

### ✅ Integrated PostgreSQL Path Fixing
- **Before:** Required separate `fix-postgres-paths.sh` script
- **Now:** Automatic in both build scripts
- **Benefit:** One-step build process, impossible to forget

### ✅ Architecture Detection
- **Auto-detects:** Intel vs Apple Silicon
- **Builds appropriately:** Avoids universal binary conflicts
- **User-friendly:** Clear messaging about what's being built

### ✅ Build Verification
- **Automatic checking:** Confirms path fixes worked
- **Clear feedback:** Success/failure reporting
- **Debug info:** Helps troubleshoot issues

## Next Steps

1. **Build your app:** Start with `./build-app-debug.sh`
2. **Test locally:** Run the built app on your Mac
3. **Test distribution:** Send DMG to another Mac and verify it works
4. **Production build:** Use `./build-app.sh` for final distribution

The build process is now fully automated and reliable! 🚀