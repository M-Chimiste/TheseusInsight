# Gatekeeper "Damaged DMG" Workaround Guide

## 🔍 **The Issue**

When sharing your DMG, users get this error:
> "Theseus Insight.dmg" is damaged and can't be opened. You should move it to the Trash.

This happens because:
- ✅ **App is code signed** (Developer ID verified)
- ❌ **App is NOT notarized** (Apple hasn't scanned it)

## ✅ **Current Status: Properly Signed**

Your DMG and app are now **properly code signed**:

```bash
# Verify DMG signature
$ codesign -dv "dist/Theseus Insight-0.9.4-arm64.dmg"
Authority=Developer ID Application: Christian Merrill (4H8Z97B24M)
Authority=Developer ID Certification Authority  
Authority=Apple Root CA

# Verify app signature  
$ codesign -dv "dist/mac/Theseus Insight.app"
Authority=Developer ID Application: Christian Merrill (4H8Z97B24M)
```

## 🛠️ **User Workarounds**

### Option 1: Right-Click Method (Recommended)
1. **Right-click** the DMG file
2. Select **"Open"** from context menu  
3. Click **"Open"** in the warning dialog
4. DMG will mount successfully

### Option 2: Terminal Method
```bash
# Remove quarantine flag
xattr -d com.apple.quarantine "/path/to/Theseus Insight.dmg"

# Or mount directly  
hdiutil attach "/path/to/Theseus Insight.dmg"
```

### Option 3: System Settings (One-time)
1. Go to **System Settings → Privacy & Security**
2. Under **Security**, click **"Open Anyway"** (appears after first attempt)

## 🚀 **Developer Solutions**

### Quick Fix: Remove Extended Attributes
Before sharing, clean the DMG:

```bash
# Remove all extended attributes
xattr -cr "dist/Theseus Insight-0.9.4-arm64.dmg"

# Verify clean
xattr -l "dist/Theseus Insight-0.9.4-arm64.dmg"
```

### Permanent Fix: Notarization
Add Apple notarization to eliminate the warning completely:

```bash
# 1. Upload to Apple for scanning
xcrun notarytool submit "dist/Theseus Insight.dmg" \
  --apple-id "your-apple-id@example.com" \
  --password "app-specific-password" \
  --team-id "4H8Z97B24M" \
  --wait

# 2. Staple the notarization ticket
xcrun stapler staple "dist/Theseus Insight.dmg"
```

**Requirements for notarization:**
- Apple ID with App-Specific Password
- Hardened Runtime enabled ✅ (already configured)
- All binaries signed ✅ (already done)

## 📋 **Distribution Strategy**

### Current Approach (Code Signed Only)
**Pros:**
- ✅ Identifies you as verified developer  
- ✅ Shows your Developer ID in signature
- ✅ Works with right-click workaround
- ✅ Fast build process (no Apple upload wait)

**Cons:**  
- ⚠️ Shows Gatekeeper warning on first open
- ⚠️ Requires user to right-click → "Open"

### With Notarization (Future Enhancement)
**Pros:**
- ✅ No Gatekeeper warnings
- ✅ Seamless user experience  
- ✅ Can be downloaded directly from web

**Cons:**
- ⏱️ Longer build process (5-15 min Apple scanning)
- 🔑 Requires Apple ID app-specific password

## 🎯 **Recommendation**

**For now:** Continue with **code signed** distribution:
1. Include installation instructions with your DMG
2. Document the right-click workaround
3. This is common for many indie macOS apps

**For production:** Add notarization when ready for wider distribution:
1. Set up Apple ID app-specific password
2. Add notarization to build script
3. Test the full notarized workflow

## 📖 **User Instructions to Include**

Include this with your DMG distribution:

```
🍎 macOS Installation Instructions:

1. Download Theseus Insight.dmg
2. RIGHT-CLICK the DMG file and select "Open"
3. Click "Open" in the security dialog
4. Drag Theseus Insight.app to your Applications folder

This app is code signed with Apple Developer ID but not notarized.
Right-clicking bypasses the initial security warning.
```

---

**Your app is now properly signed and secure! The "damaged" error is just a Gatekeeper notification requirement, not an actual security issue.** 🛡️ 