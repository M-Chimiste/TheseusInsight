# Theseus Insight Electron App Build Guide

## Problem Summary

You were experiencing issues where:
1. **Settings page showed a blank grey box** in the built Electron app
2. **Config folder wasn't being bundled** properly
3. **No default .env file** was provided for initial setup

## Solution Implemented

### 1. Fixed Path Resolution

**Problem**: The FastAPI backend was using hardcoded relative paths that broke in the packaged Electron app.

**Solution**: Created a comprehensive path resolution system:
- `theseus_insight/utils/path_resolver.py` - Handles development vs packaged paths
- Environment variables (`THESEUS_CONFIG_DIR`, `THESEUS_APP_ROOT`) for path detection
- Updated all config file loading to use the new path resolver

### 2. Enhanced Build Configuration

**Problem**: Config files and environment templates weren't being bundled correctly.

**Solution**: Updated `package.json` build configuration:
```json
"extraResources": [
  {
    "from": "../",
    "to": "app",
    "filter": [
      "theseus_insight/**", 
      "theseus-ui/dist/**", 
      "config/**", 
      "run_theseus_insight.py", 
      "requirements.txt", 
      "postgres/**"
    ]
  },
  {
    "from": "env.template",
    "to": ".env"
  }
]
```

### 3. Created Default Environment Template

**Problem**: No default .env file for users to configure the app.

**Solution**: Created `electron-app/env.template` with all necessary environment variables:
- API credentials (OpenAI, Anthropic, Google)
- Email configuration (Gmail)
- Database settings
- Security settings
- Development options

### 4. Automatic Security Key Generation

**Problem**: APP_SECRET_KEY was hardcoded to an insecure default value.

**Solution**: Implemented automatic generation of secure APP_SECRET_KEY:
- Generates a cryptographically secure 256-bit (64 character) hex key on first startup
- Stores it persistently in user data directory:
  - **macOS**: `~/Library/Application Support/theseus-desktop/app_secret.key`
  - **Windows**: `%APPDATA%/theseus-desktop/app_secret.key`  
  - **Linux**: `~/.config/theseus-desktop/app_secret.key`
- File is created with restrictive permissions (readable only by owner)
- Reuses the same key on subsequent startups for data consistency
- Falls back to session-only key if file access fails

### 5. Enhanced Startup Scripts

**Problem**: Backend startup didn't handle packaged vs development environments.

**Solution**: 
- Enhanced `main.js` with proper environment detection
- Created `start_backend.py` wrapper for packaged apps
- Added comprehensive debugging output
- Implemented intelligent shared memory health checks:
  - **Process Detection**: Checks for active PostgreSQL processes using the data directory
  - **Attachment Analysis**: Verifies if shared memory segments have active attachments
  - **Key Pattern Validation**: Ensures segments match PostgreSQL memory patterns
  - **Lock File Correlation**: Cross-references with PostgreSQL lock files
  - **Safe Cleanup**: Only removes confirmed orphaned segments

## How to Build Your App

### Quick Build (Recommended)

```bash
cd electron-app
npm run build-app
```

This automated script:
1. ✅ Builds the React UI
2. ✅ Verifies config files exist
3. ✅ Builds the Electron app
4. ✅ Shows detailed output

### Manual Build Process

1. **Build the UI first**:
   ```bash
   cd theseus-ui
   npm run build
   ```

2. **Build Electron app**:
   ```bash
   cd electron-app
   npm run build        # Current platform
   npm run build:mac    # macOS
   npm run build:win    # Windows
   npm run build:linux  # Linux
   ```

### Platform-Specific Builds

```bash
# Build for specific platforms
./build-app.sh mac     # macOS
./build-app.sh win     # Windows
./build-app.sh linux   # Linux
```

## What Gets Bundled

Your built Electron app now includes:

1. **✅ React UI** - Built from `theseus-ui/dist`
2. **✅ Python Backend** - Complete FastAPI application
3. **✅ Config Files** - All files from `config/` directory
4. **✅ Default .env** - Pre-populated environment template
5. **✅ PostgreSQL** - Embedded database binaries
6. **✅ Path Resolution** - Automatic development/production detection

## Environment Configuration

The built app automatically:

1. **Loads .env file** from the correct location (packaged vs development)
2. **Detects environment** using `ELECTRON_IS_PACKAGED`
3. **Resolves config paths** using environment variables
4. **Provides defaults** for all required settings

## Troubleshooting

### Settings Page Still Blank?

1. **Check the console output** when running the built app:
   ```bash
   # On macOS, run the app from terminal to see logs
   ./dist/mac/Theseus\ Insight.app/Contents/MacOS/Theseus\ Insight
   ```

2. **Verify UI was built**:
   ```bash
   ls -la theseus-ui/dist/
   # Should contain index.html and assets/
   ```

3. **Check config files**:
   ```bash
   ls -la config/
   # Should contain orchestration.json, research_interests.txt, etc.
   ```

### Backend Not Starting?

1. **Check Python environment** - Ensure all dependencies are installed
2. **Verify paths** - Look for DEBUG output in console
3. **Check permissions** - Ensure `start_backend.py` is executable

### API Calls Failing?

1. **Backend not ready** - Wait for "Server is ready!" message
2. **Port conflicts** - Ensure ports 8000 and 55432 are available
3. **Config loading** - Check for config file loading errors

### APP_SECRET_KEY Issues?

1. **Key not generating** - Check console for "Generated new APP_SECRET_KEY" message
2. **Permission errors** - Ensure app can write to user data directory
3. **Encryption/decryption failures** - Check that the key file hasn't been corrupted
4. **Development override** - Uncomment `APP_SECRET_KEY=` in .env if needed

**Security Note**: The APP_SECRET_KEY is used to encrypt sensitive data like API keys in the database. If this key is lost or changed, previously encrypted data cannot be recovered. The key file should be backed up with your user data if migrating between machines.

## Development vs Production

### Development Mode
- Uses Vite dev server (`localhost:5173`)
- Hot reload for UI changes
- Direct uvicorn startup
- Relative config paths

### Production Mode (Built App)
- Uses FastAPI static serving (`localhost:8000`)
- Bundled UI from `dist/`
- Python wrapper script startup
- Environment-based config paths

## Next Steps

1. **Test the build**:
   ```bash
   cd electron-app
   npm run build-app
   ```

2. **Run the built app** and check if settings page loads correctly

3. **Configure environment** by editing the `.env` file in the built app

4. **Distribute** the built installer from the `dist/` directory

## Shared Memory Health Checks

The enhanced shared memory cleanup system performs multiple safety checks:

1. **Active Process Detection**: Scans for PostgreSQL processes using the same data directory
2. **Attachment Count Analysis**: Checks if segments have active memory attachments
3. **Key Pattern Validation**: Verifies shared memory keys match PostgreSQL patterns
4. **Lock File Correlation**: Ensures cleanup doesn't interfere with running instances
5. **Conservative Approach**: When in doubt, preserves segments to avoid system disruption

This prevents interference with system PostgreSQL installations and other applications.

## Files Modified/Created

### New Files:
- `electron-app/env.template` - Environment configuration template
- `electron-app/start_backend.py` - Python backend wrapper
- `electron-app/build-app.sh` - Automated build script
- `electron-app/BUILD_GUIDE.md` - This guide
- `theseus_insight/utils/path_resolver.py` - Path resolution utilities

### Modified Files:
- `electron-app/package.json` - Enhanced build configuration
- `electron-app/main.js` - Environment detection, debugging, and intelligent cleanup
- `electron-app/DEVELOPMENT.md` - Updated with build instructions
- `theseus_insight/main.py` - Updated to use path resolver

The settings page should now load correctly in your built Electron app! 🎉