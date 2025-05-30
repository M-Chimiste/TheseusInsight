# Theseus Insight - Installation Guide

This guide helps you install and run Theseus Insight on your Mac.

## 📦 What You Need

Before installing Theseus Insight, make sure your Mac has:

### 1. Python 3.8 or Later
Check if Python is installed:
```bash
python3 --version
```

If not installed, download from: https://www.python.org/downloads/

### 2. Required Python Packages
Install these packages using pip:
```bash
pip3 install fastapi uvicorn psycopg2-binary
```

### 3. PostgreSQL (Optional - for full functionality)
Download from: https://www.postgresql.org/download/

## 🚀 Installation Steps

### Step 1: Download and Install
1. Download the Theseus Insight DMG file
2. Double-click the DMG to mount it
3. Drag "Theseus Insight" to your Applications folder

### Step 2: First Launch
1. **Right-click** on the app in Applications folder
2. Select **"Open"** from the context menu
3. Click **"Open"** when the security dialog appears

**Note:** Don't double-click the app on first launch - this bypasses macOS security checks.

### Step 3: If the App Won't Start

If the app quits immediately or shows errors:

1. **Run the Debug Script**:
   - Download `debug-app.sh` (provided separately)
   - Open Terminal
   - Run: `chmod +x debug-app.sh`
   - Run: `./debug-app.sh`
   - Share the output with support

2. **Common Fixes**:

   **If Python is missing:**
   ```bash
   # Install Python from python.org, then:
   pip3 install fastapi uvicorn psycopg2-binary
   ```

   **If packages are missing:**
   ```bash
   pip3 install fastapi uvicorn psycopg2-binary pandas numpy
   ```

   **If permission errors:**
   ```bash
   sudo xattr -rd com.apple.quarantine "/Applications/Theseus Insight.app"
   ```

## 🔧 Troubleshooting

### App Shows "Python Not Found"
- Install Python 3.8+ from https://python.org
- Restart Terminal and try again

### App Shows "Missing Dependencies"
```bash
pip3 install fastapi uvicorn psycopg2-binary pandas numpy requests
```

### App Shows "Connection Error"
- Check if Python packages are installed
- Try restarting the app
- Check Console.app for detailed error messages

### App Still Won't Start
1. Open Terminal
2. Run: `/Applications/Theseus\ Insight.app/Contents/MacOS/Theseus\ Insight`
3. Look for error messages in the output

## 🆘 Getting Help

If you're still having issues:

1. Run the debug script: `./debug-app.sh`
2. Copy the output
3. Include your macOS version: `sw_vers`
4. Include your Python version: `python3 --version`
5. Contact support with all this information

## ✅ Verification

Once working correctly, you should see:
- App launches with a blue loading screen
- After a few seconds, the main interface appears
- No error dialogs or crashes

## 🔄 Updating

To update Theseus Insight:
1. Quit the current app
2. Replace the app in Applications folder with the new version
3. First launch: Right-click → Open (security check)

## 🖥️ System Requirements

- **macOS**: 10.14 Mojave or later
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB available space
- **Python**: 3.8 or later
- **Architecture**: Intel (x64) or Apple Silicon (arm64) 