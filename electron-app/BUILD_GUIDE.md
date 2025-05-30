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

**🔧 SOLUTION: Use the Fix Script**

The most common issues (quarantine attributes, permissions, code signature conflicts) are resolved with the included fix script.

**For Recipients of the DMG:**
1. Install the app: Drag to /Applications
2. Run the fix script:
   ```bash
   curl -O https://raw.githubusercontent.com/your-repo/fix-distributed-app.sh
   chmod +x fix-distributed-app.sh
   ./fix-distributed-app.sh
   ```
3. Launch the app normally

**What the Fix Script Does:**
- ✅ Removes quarantine attributes
- ✅ Clears problematic extended attributes  
- ✅ Sets proper file permissions
- ✅ Clears signature cache conflicts
- ✅ Tests app launch

**Manual Fix (if script unavailable):**
```bash
# Remove quarantine
xattr -r -d com.apple.quarantine "/Applications/Theseus Insight.app"

# Clear all extended attributes
xattr -cr "/Applications/Theseus Insight.app"

# Set permissions
chmod -R 755 "/Applications/Theseus Insight.app"
chmod +x "/Applications/Theseus Insight.app/Contents/MacOS/Theseus Insight"
```

### UI Shows Blank Screen

**This is usually caused by missing frontend files or backend startup issues:**

1. **Wait for Backend Startup:**
   - First launch takes 30-60 seconds
   - Backend must initialize PostgreSQL and load Python dependencies
   - Watch for "Ready" message in Console.app

2. **Check Build Verification:**
   The build scripts verify frontend bundling. Look for:
   ```
   ✅ Frontend bundled successfully (123 assets)
   ```

3. **Backend Path Issues:**
   Check Console.app for backend errors like:
   ```
   ERROR: Frontend serving failed
   Static assets directory not found
   ```

4. **Manual Verification:**
   ```bash
   # Check if frontend is bundled
   find "/Applications/Theseus Insight.app/Contents/Resources/app" -name "index.html"
   # Should find: .../app/theseus-ui/dist/index.html
   ```

### Performance Issues

**PostgreSQL Startup:**
- First launch takes longer (database initialization)
- Subsequent launches are much faster
- Check Console.app for startup logs

**Memory Usage:**
- Normal: 200-400MB
- High usage: Check for runaway Python processes

### **Crash on Startup** 

**This is the most common issue and is solved by the fix script above.**

**Root Cause:** macOS security features (quarantine attributes, Gatekeeper, code signature conflicts) prevent the app from running.

**Symptoms:**
- App quits immediately after double-click
- No error dialog shown
- Crash reports in Console.app mentioning "library not loaded"

**Solution:** Always include `fix-distributed-app.sh` with your DMG and instruct recipients to run it first.

### **AMFI Signature Issues** 

**This is now RESOLVED with the latest build configuration.**

**Root Cause:** macOS Apple Mobile File Integrity (AMFI) rejects unsigned Electron helper processes:
```
AMFI: '/Applications/Theseus Insight.app/Contents/Frameworks/Theseus Insight Helper (Renderer).app/Contents/MacOS/Theseus Insight Helper (Renderer)' has no CMS blob?
AMFI: Unrecoverable CT signature issue, bailing out.
```

**Solution:** The enhanced `fix-distributed-app.sh` script now applies ad-hoc signatures to all Electron helpers:
```bash
codesign --force --deep --sign - "Helper.app"
```

**Result:** Helpers become acceptable to macOS security while remaining distributable without a Developer ID.

### **Dual Bundling Conflicts**

**This is now RESOLVED with the proper asar configuration.**

**Root Cause:** Previously had both `app.asar` and `app/` directory causing code signature conflicts.

**Solution:** Proper asar configuration in `package.json`:
```json
"asar": true,
"asarUnpack": [
  "**/postgres/**/*",
  "**/theseus_insight/**/*",
  "**/run_theseus_insight.py",
  "**/requirements.txt"
]
```

**Result:** Main app code stays in asar (Electron standard) while PostgreSQL binaries are properly unpacked for external access.

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