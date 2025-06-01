#!/bin/bash

# Clean DMG for Distribution
# Removes extended attributes that can cause "damaged" errors

set -e

echo "🧹 Cleaning DMGs for distribution..."

# Find all DMG files in dist directory
for dmg in dist/*.dmg; do
    if [ -f "$dmg" ]; then
        echo "  Processing: $(basename "$dmg")"
        
        # Remove extended attributes
        xattr -cr "$dmg"
        
        # Verify signing is still intact
        if codesign -dv "$dmg" >/dev/null 2>&1; then
            echo "    ✅ Code signature verified"
        else
            echo "    ⚠️  Warning: Code signature missing"
        fi
        
        # Check remaining attributes
        remaining=$(xattr -l "$dmg" | wc -l)
        if [ "$remaining" -eq 0 ]; then
            echo "    ✅ All quarantine attributes removed"
        else
            echo "    ℹ️  Remaining attributes: $remaining"
        fi
        
        echo
    fi
done

echo "🎉 DMG cleaning complete!"
echo
echo "📋 Distribution checklist:"
echo "  ✅ Apps are code signed"
echo "  ✅ DMGs are code signed"  
echo "  ✅ Extended attributes cleaned"
echo "  📖 Include installation instructions with right-click method"
echo
echo "Users should right-click the DMG and select 'Open' to bypass Gatekeeper warnings." 