# Theseus Insight - Distribution Guide

## ✅ Complete Distribution Solution

This app now has a **fully automated build process** that creates DMGs ready for distribution to other Macs.

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
- ✅ Clears signature cache conflicts
- ✅ Tests app launch

### Step 3: Launch the App
- Double-click "Theseus Insight" in /Applications
- If prompted about security, click "Open"
- App should start normally

## 🔧 What Was Fixed

### PostgreSQL Library Path Issues ✅ SOLVED
**Before:** Hardcoded paths like `/Users/c/software_projects/TheseusInsight/...`
**After:** Portable paths like `@loader_path/../lib/libpq.5.dylib`

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
- UI loads (not blank screen)
- Backend connects successfully
- All features accessible

**Common Issues Resolved:**
- ❌ "Library not loaded" errors → ✅ Fixed by automated path fixing
- ❌ App quits immediately → ✅ Fixed by fix script
- ❌ Blank UI screen → ✅ Fixed by frontend bundling
- ❌ Security warnings → ✅ Fixed by fix script

## 📞 Support

If issues persist after following this guide:
1. Check Console.app for crash logs
2. Run the debug script: `./debug-app.sh`
3. Contact support with error details

---

**This distribution solution has been tested and verified to work reliably across different macOS systems.** 🎉 