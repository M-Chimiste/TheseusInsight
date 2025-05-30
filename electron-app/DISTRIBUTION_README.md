# Theseus Insight - Distribution Guide

## 🚚 **For App Recipients (Mac Users)**

### **Quick Setup (2 Steps)** ✨ **SIMPLIFIED!**
1. **Install the app**: Drag `Theseus Insight.app` to `/Applications`
2. **Fix app signatures**: Run `./fix-distributed-app.sh`

**🎉 That's it!** No Python installation required - everything is bundled!

---

## 📦 **What's Included**

- `Theseus Insight-X.X.X-arm64.dmg` - Main app for Apple Silicon Macs (Self-contained!)
- `fix-distributed-app.sh` - **Required** fix script for AMFI signature issues
- `debug-backend.sh` - Backend troubleshooting tool
- This README file

---

## 🔧 **Detailed Installation Steps**

### Step 1: Install the App
```bash
# Mount the DMG and drag to Applications
open "Theseus Insight-X.X.X-arm64.dmg"
# Drag the app to /Applications folder
```

### Step 2: Fix App Signatures (Required)
```bash
# Run the fix script
./fix-distributed-app.sh
```

**Why is this needed?** macOS requires code signatures for all app components. This script applies the necessary signatures to make the app work on your Mac.

---

## ✨ **What's New: Self-Contained App**

🎉 **No more Python installation required!** This version includes:

- ✅ **Bundled Python Dependencies**: FastAPI, uvicorn, PostgreSQL drivers, and all required packages
- ✅ **Embedded PostgreSQL**: Complete database system included
- ✅ **Self-Contained Frontend**: React UI bundled and optimized
- ✅ **Zero External Dependencies**: Works on any Mac without additional software

---

## 🚀 **First Launch**

After running the fix script:

1. **Launch the app**: Double-click `Theseus Insight` in Applications
2. **Wait for startup**: First launch takes 10-15 seconds (initializing database)
3. **Look for the UI**: App window should open automatically
4. **Check the dock**: App icon should appear in the dock

---

## 🔧 **Troubleshooting**

### App Won't Start
```bash
# Run the debug script for detailed diagnostics
./debug-backend.sh
```

### Common Issues

**"App is damaged" error:**
- Make sure you ran `./fix-distributed-app.sh`
- Try: `xattr -cr "/Applications/Theseus Insight.app"`

**App starts but shows blank screen:**
- Check Console.app for error messages
- Run `./debug-backend.sh` to check backend status

**"Services Starting" forever:**
- This should no longer happen with bundled dependencies
- If it does, run `./debug-backend.sh` for diagnosis

---

## 📊 **System Requirements**

- **macOS**: 10.15 (Catalina) or later
- **Architecture**: Apple Silicon (M1/M2/M3) or Intel
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 500MB free space
- **No Python installation required** ✨

---

## 🆘 **Getting Help**

If you encounter issues:

1. **Run diagnostics**: `./debug-backend.sh`
2. **Check Console.app** for error messages
3. **Try a clean install**: Delete app, reinstall, run fix script
4. **Contact support** with the diagnostic output

---

## 🔄 **Updates**

When a new version is released:
1. Delete the old app from Applications
2. Install the new DMG
3. Run the fix script again
4. Your data is preserved in `~/Library/Application Support/theseus-desktop`

## 🚀 For Developers: Building the App

**Simple One-Command Build:**
```bash
cd electron-app
./build-app-debug.sh
```

**What Happens Automatically:**
- ✅ React frontend is built and bundled
- ✅ PostgreSQL binaries are bundled with portable paths
- ✅ All hardcoded paths are automatically fixed
- ✅ Frontend and backend verification
- ✅ Proper asar/extraResources configuration
- ✅ DMG created for distribution

**Build Output:**
```
✅ PostgreSQL bundled successfully
✅ PostgreSQL paths verified - no hardcoded paths found
✅ Frontend bundled successfully (36 assets)
🎉 Debug build complete!
```

## 📦 For Recipients: Installing the App

### Step 1: Install the App
- Download and mount the DMG
- Drag "Theseus Insight.app" to /Applications

### Step 2: Run the Fix Script
Download and run the fix script to resolve macOS security issues:

```bash
curl -O https://raw.githubusercontent.com/your-repo/fix-distributed-app.sh
chmod +x fix-distributed-app.sh
./fix-distributed-app.sh
```

**What the Fix Script Does:**
- ✅ Removes quarantine attributes
- ✅ Clears problematic extended attributes  
- ✅ Sets proper file permissions
- ✅ **Applies ad-hoc signatures to Electron helpers** (fixes AMFI crashes)
- ✅ Re-signs main app with ad-hoc signature
- ✅ Clears signature cache conflicts
- ✅ Tests app launch

### Step 3: Launch the App
- Double-click "Theseus Insight" in /Applications
- If prompted about security, click "Open"
- App should start normally

## 🔧 What Was Fixed

### AMFI Signature Issues ✅ SOLVED
**Before:** `AMFI: Unrecoverable CT signature issue, bailing out`
**After:** Ad-hoc signatures make Electron helpers acceptable to macOS security

### PostgreSQL Library Path Issues ✅ SOLVED
**Before:** Hardcoded paths like `/Users/c/software_projects/TheseusInsight/...`
**After:** Portable paths like `@loader_path/../lib/libpq.5.dylib`

### Dual Bundling Conflicts ✅ SOLVED
**Before:** Both `app.asar` and `app/` directory causing code signature conflicts
**After:** Proper asar configuration with asarUnpack for resources that need to be external

### macOS Security Issues ✅ SOLVED
**Before:** App crashes with quarantine attributes and code signature conflicts
**After:** Fix script resolves all security barriers

### UI Loading Issues ✅ SOLVED
**Before:** Blank screens due to missing frontend files
**After:** Frontend properly bundled and served

### Build Complexity ✅ SOLVED
**Before:** Multiple manual steps, easy to forget path fixing
**After:** Single command builds everything automatically

## 📋 Distribution Checklist

**For Developers:**
- [ ] Run `./build-app-debug.sh`
- [ ] Verify build completes successfully
- [ ] Include `fix-distributed-app.sh` with DMG
- [ ] Test on a different Mac

**For Recipients:**
- [ ] Install app to /Applications
- [ ] Run fix script: `./fix-distributed-app.sh`
- [ ] Launch app normally
- [ ] Verify UI loads and backend connects

## 🎯 Success Indicators

**App Working Correctly:**
- App launches without crashes
- No AMFI signature errors in console
- UI loads (not blank screen)
- Backend connects successfully
- All features accessible

**Common Issues Resolved:**
- ❌ "Library not loaded" errors → ✅ Fixed by automated path fixing
- ❌ AMFI signature crashes → ✅ Fixed by ad-hoc signing
- ❌ App quits immediately → ✅ Fixed by fix script
- ❌ Blank UI screen → ✅ Fixed by frontend bundling
- ❌ Security warnings → ✅ Fixed by fix script

## 🧬 Technical Solution

**asar Configuration:**
```json
"asar": true,
"asarUnpack": [
  "**/postgres/**/*",
  "**/theseus_insight/**/*",
  "**/run_theseus_insight.py",
  "**/requirements.txt"
]
```

**Ad-hoc Signing:**
```bash
codesign --force --deep --sign - "Helper.app"
```

This approach:
- Keeps main app code in asar (Electron standard)
- Unpacks resources that need external access
- Applies ad-hoc signatures for macOS security compatibility
- Maintains full distribution compatibility

## 📞 Support

If issues persist after following this guide:
1. Check Console.app for crash logs
2. Run the debug script: `./debug-app.sh`
3. Contact support with error details

---

**This distribution solution has been tested and verified to work reliably across different macOS systems.** 🎉 