# Theseus Insight Electron App Troubleshooting Guide

This guide provides information on common issues related to the packaged Theseus Insight Electron application, the fixes that have been implemented, and how to diagnose further problems.

## Summary of Issues Addressed

The primary challenges with distributing the Electron app, particularly on macOS, were related to:

1.  **Python Interpreter Path:** The application was using hardcoded paths to a specific user's Conda Python environment. This would cause the Python backend to fail on any other machine.
2.  **Python Dependency Loading:** Even if a system Python was found, it might not correctly locate and load the Python dependencies (`psycopg2`, `uvicorn`, `fastapi`, etc.) that are bundled with the application.
3.  **PostgreSQL Dynamic Libraries (macOS):** Packaged macOS applications require careful handling of dynamic library (`.dylib`) paths. The bundled PostgreSQL instance has several internal libraries and dependencies. If their paths are absolute or point to locations on the build machine, PostgreSQL will fail to start on another Mac. This is a common issue with Electron's `asar` packaging and macOS Gatekeeper/notarization.

## Implemented Fixes

To address these issues, the following changes were made:

### 1. Python Environment and Backend Startup (`main.js`)

*   **Removed Hardcoded Python Paths:** The Electron main process (`main.js`) no longer searches for Python in hardcoded Conda environments (e.g., `/Users/c/...`).
*   **Dynamic Python Detection:** It now attempts to find `python3` in the system's PATH. If not found, it falls back to `python`. An error is logged if neither is found.
*   **`PYTHONPATH` Configuration:**
    *   The `python_deps` directory (located at `YourApp.app/Contents/Resources/app/python_deps/` in the packaged app) is now explicitly added to the `PYTHONPATH` environment variable when launching the Python backend.
    *   The `projectRoot` (i.e., `YourApp.app/Contents/Resources/app/`) is also included in `PYTHONPATH` to ensure the backend's own modules (e.g., `theseus_insight`) are discoverable.
    *   This helps the Python interpreter locate all necessary bundled libraries.

### 2. Python Backend Scripts (`start_backend.py`, `start_backend_robust.py`)

*   **`sys.path` Modification:** Both Python backend startup scripts now explicitly add the `python_deps` directory to `sys.path` at runtime. This provides an additional layer of robustness, ensuring the bundled dependencies are discoverable even if `PYTHONPATH` inheritance has issues.

### 3. PostgreSQL Pathing on macOS (`scripts/afterPack.js`)

*   **Enhanced `afterPack` Script:** This script runs during the `electron-builder` packaging process for macOS.
    *   It uses `install_name_tool` to correct the internal paths of PostgreSQL's dynamic libraries (`.dylib` files) and executables.
    *   Hardcoded paths from the build machine (e.g., `/Users/builder/...` or absolute paths into the app bundle itself) are changed to be relative to the executables (`@loader_path/../lib/yourlibrary.dylib`).
    *   The script now has more detailed logging of its operations and a more comprehensive verification step that checks key PostgreSQL binaries (`postgres`, `initdb`, `psql`, `pg_ctl`) for any remaining problematic library paths.

## Debugging Further Issues

If the application still freezes or fails to start correctly on a new machine (especially after re-signing on macOS), here are some steps to diagnose the problem:

### 1. Electron Main Process Logs (Developer Console)

*   **How to Open:** In the Electron app, you can usually open the Developer Tools by navigating to `View > Toggle Developer Tools` in the application menu (if available), or by using a shortcut like `Option+Command+I` (macOS) or `Ctrl+Shift+I` (Windows/Linux).
*   **What to Look For:**
    *   Errors related to starting the Python backend.
    *   Messages from `main.js` about the Python command (`pythonCmd`) or `PYTHONPATH`.
    *   Errors from the PostgreSQL startup process.
    *   Any "Uncaught Exception" or "Unhandled Rejection" messages.
    *   Output from the `afterPack.js` script will be visible in the terminal during the build process, not in the app's console.

### 2. Python Backend Logs

*   The `main.js` script is configured to print the `stdout` and `stderr` from the Python backend process to its own console. These messages will appear in the Electron Developer Console (see above).
*   Look for:
    *   Python tracebacks (error messages).
    *   "DEBUG" messages from `start_backend.py` or `start_backend_robust.py` showing the paths being used (e.g., `app_root`, `python_deps_path`).
    *   Messages from `uvicorn` about the FastAPI server starting up or failing.
    *   Errors related to database connections (e.g., from `psycopg2`).

### 3. Verifying PostgreSQL Library Paths (macOS)

If you suspect PostgreSQL pathing issues on macOS, even after the `afterPack.js` script has run:

*   **Locate the App:** Find your packaged `.app` bundle (e.g., `Theseus Insight.app`).
*   **Find PostgreSQL Binaries:** The key PostgreSQL executables are typically located in:
    `Theseus Insight.app/Contents/Resources/app/postgres/darwin/bin/`
*   **Use `otool`:** Open a Terminal and use the `otool -L` command to inspect a binary. For example:
    ```bash
    otool -L "/path/to/Theseus Insight.app/Contents/Resources/app/postgres/darwin/bin/postgres"
    ```
*   **What to Look For:**
    *   Each line after the first one is a linked dynamic library.
    *   **Correct paths** start with:
        *   `@loader_path/...` (meaning relative to the executable)
        *   `/usr/lib/...` (system libraries)
        *   `/System/Library/...` (system libraries)
    *   **Problematic paths** might look like:
        *   `/Users/your_build_user/...` (absolute path from the build machine)
        *   An absolute path pointing back into the `.../postgres/darwin/lib/` directory inside the app bundle (e.g., `/Applications/Theseus Insight.app/Contents/Resources/app/postgres/darwin/lib/libpq.5.dylib` instead of `@loader_path/../lib/libpq.5.dylib`).
*   The `afterPack.js` script logs its verification results during the build process. Review these logs first.

### 4. Re-Signing on macOS

*   If you are re-signing the application (e.g., with a different certificate), ensure the signing process preserves ad-hoc signatures of internal executables and doesn't break the corrected dylib paths.
*   Use the `--deep` flag with `codesign` carefully, as it can sometimes be problematic. It's often better to sign files individually from the inside out if you encounter issues.
*   Verify entitlements are correct.

By following these steps, you should be able to gather more information about why the application might be failing on a different machine.
