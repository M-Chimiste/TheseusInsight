# Theseus Insight - macOS Distribution Guide

This guide explains how to build and distribute the Theseus Insight Electron app for macOS, including solutions for the "silent quit" issue when moving to other Macs.

## 🚨 Common Issue: Silent Quit on Other Macs

When your app silently quits on other Macs, it's usually due to:
1. **Code signing issues** - macOS Gatekeeper blocking unsigned apps
2. **Architecture mismatch** - Intel vs Apple Silicon compatibility
3. **Missing entitlements** - Required permissions not granted
4. **Hardcoded paths** - Dependencies not found in expected locations

## 🛠️ Solutions Provided

### Files Added/Fixed:
- ✅ `build/entitlements.mac.plist` - Required macOS permissions
- ✅ `scripts/notarize.js` - Code signing and notarization script
- ✅ `build-app-debug.sh` - Debug build without signing
- ✅ Updated `package.json` - Universal binary and improved config

## 📦 Building Options

### Option 1: Debug Build (Recommended for Testing)

For testing on multiple Macs without Apple Developer account:

```bash
cd electron-app
./build-app-debug.sh
```

**Pros:**
- ✅ No Apple Developer account needed
- ✅ Works on most Macs with Security & Privacy override
- ✅ Quick build process

**Cons:**
- ⚠️ Requires manual security approval on each Mac
- ⚠️ May show "unidentified developer" warnings

### Option 2: Universal Binary (Best Compatibility)

For maximum compatibility across Intel and Apple Silicon Macs:

```bash
cd electron-app
npm install
npm run build:mac-universal
```

### Option 3: Production Build with Code Signing

For official distribution (requires Apple Developer account):

```bash
# Set environment variables
export APPLE_ID="your-apple-id@example.com"
export APPLE_ID_PASSWORD="your-app-specific-password"
export APPLE_TEAM_ID="YOUR_TEAM_ID"

cd electron-app
./build-app.sh mac
```

## 🔧 Installation Instructions for Recipients

### For Debug Builds:
1. **Download and extract** the DMG file
2. **Drag app to Applications** folder
3. **First launch:** Right-click app → "Open" → "Open Anyway"
4. **Alternative:** System Preferences → Security & Privacy → "Open Anyway"

### If App Still Won't Start:

#### Check Console Logs:
```bash
# Open Console app and search for "Theseus Insight" or look for crash logs
Console.app → Reports → System Reports
```

#### Terminal Debugging:
```bash
# Try running from Terminal to see error messages
cd /Applications
./Theseus\ Insight.app/Contents/MacOS/Theseus\ Insight
```

#### Reset Quarantine (if needed):
```bash
# Remove quarantine attribute
sudo xattr -rd com.apple.quarantine "/Applications/Theseus Insight.app"
```

## 🏗️ Architecture Support

The updated configuration builds **Universal Binaries** that work on:
- ✅ Intel Macs (x64)
- ✅ Apple Silicon Macs (arm64)
- ✅ Rosetta 2 translation layer

## 🔐 Security Entitlements

The `entitlements.mac.plist` file grants necessary permissions for:
- **JIT compilation** (required for Electron)
- **Child processes** (Python backend, PostgreSQL)
- **Network access** (API communication)
- **File system access** (data storage)
- **Audio/video** (podcast features)

## 🐛 Troubleshooting

### App Crashes Immediately:
1. **Check architecture:** Use Universal build
2. **Verify entitlements:** Ensure `entitlements.mac.plist` exists
3. **Try debug build:** Use `build-app-debug.sh` first

### "App is damaged" Message:
1. **Remove quarantine:** `sudo xattr -rd com.apple.quarantine "/path/to/app"`
2. **Rebuild with signing:** Use production build with Apple Developer credentials

### Missing Dependencies:
1. **Check bundled resources:** Ensure Python, PostgreSQL included
2. **Verify paths:** Check `main.js` for hardcoded paths
3. **Test locally first:** Ensure app works on build machine

### Network/Permission Issues:
1. **Check entitlements:** Verify all required permissions granted
2. **Firewall settings:** Allow app through macOS firewall
3. **Privacy settings:** Grant necessary permissions in System Preferences

## 📋 Build Checklist

Before distributing:
- [ ] App starts successfully on build machine
- [ ] All features work (database, backend, UI)
- [ ] No hardcoded paths to build machine
- [ ] Universal binary built for architecture compatibility
- [ ] Tested on both Intel and Apple Silicon if possible
- [ ] Security settings documented for recipients

## 💡 Best Practices

1. **Always test locally first** before distributing
2. **Use Universal builds** for maximum compatibility
3. **Provide clear installation instructions** to recipients
4. **Consider getting Apple Developer account** for smoother distribution
5. **Test on clean machines** when possible
6. **Document any special requirements** or setup steps

## 🆘 Still Having Issues?

If the app still won't run on other Macs:

1. **Share crash logs** from Console.app
2. **Try terminal debugging** to see error messages
3. **Check system compatibility** (macOS version, architecture)
4. **Verify all bundled resources** are included in build
5. **Consider temporary code signing** with ad-hoc certificate 