#!/usr/bin/env python3
"""
Backend startup script for packaged Electron app.
This script sets up the correct paths and environment for the FastAPI backend.
"""

import os
import sys
import subprocess
from pathlib import Path

def setup_packaged_environment():
    """Setup environment variables for packaged app."""
    
    # Detect if we're running in a packaged Electron app
    is_packaged = os.getenv('ELECTRON_IS_PACKAGED', 'false').lower() == 'true'
    
    print(f"DEBUG: Is packaged: {is_packaged}")
    print(f"DEBUG: ELECTRON_RESOURCES_PATH: {os.getenv('ELECTRON_RESOURCES_PATH', 'Not set')}")
    
    # Show APP_SECRET_KEY status for debugging
    app_secret_key = os.getenv('APP_SECRET_KEY')
    if app_secret_key:
        print(f"DEBUG: APP_SECRET_KEY is set (length: {len(app_secret_key)} characters)")
    else:
        print("DEBUG: APP_SECRET_KEY is not set")
    
    if is_packaged:
        # In packaged app, adjust paths relative to the app bundle
        resources_path = os.getenv('ELECTRON_RESOURCES_PATH', '')
        if resources_path:
            app_root = os.path.join(resources_path, 'app')
        else:
            # Fallback - assume we're in the app directory
            app_root = os.path.dirname(os.path.abspath(__file__))
    else:
        # In development, use the parent directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        app_root = os.path.dirname(script_dir)
    
    print(f"DEBUG: App root: {app_root}")
    print(f"DEBUG: App root exists: {os.path.exists(app_root)}")

    # Add bundled Python dependencies to Python path
    python_deps_path = os.path.join(app_root, 'python_deps')
    if os.path.exists(python_deps_path):
        print(f"DEBUG: Found bundled Python dependencies: {python_deps_path}")
        if python_deps_path not in sys.path:
            sys.path.insert(0, python_deps_path)
        print(f"DEBUG: Added to sys.path: {python_deps_path}")
    else:
        print(f"DEBUG: Bundled Python dependencies not found: {python_deps_path}")
    
    # Set environment variables for config file locations
    config_dir = os.path.join(app_root, 'config')
    os.environ['THESEUS_CONFIG_DIR'] = config_dir
    os.environ['THESEUS_APP_ROOT'] = app_root
    
    print(f"DEBUG: Config dir: {config_dir}")
    print(f"DEBUG: Config dir exists: {os.path.exists(config_dir)}")
    
    # List config files if directory exists
    if os.path.exists(config_dir):
        try:
            config_files = os.listdir(config_dir)
            print(f"DEBUG: Config files found: {config_files}")
        except Exception as e:
            print(f"DEBUG: Error listing config files: {e}")
    
    # Ensure the config directory exists
    if not os.path.exists(config_dir):
        print(f"Warning: Config directory not found at {config_dir}")
    
    return app_root

def main():
    """Main entry point."""
    app_root = setup_packaged_environment()
    
    # Set working directory to app root
    os.chdir(app_root)
    
    # Add app root to Python path
    if app_root not in sys.path:
        sys.path.insert(0, app_root)
    
    # Set environment variables that would normally be set by Electron
    if not os.getenv('DATABASE_URL'):
        os.environ['DATABASE_URL'] = os.path.join(app_root, 'data', 'theseus.db')
    
    # Import and run the FastAPI app
    try:
        import uvicorn
        from theseus_insight.main import app
        
        print("Starting FastAPI server...")
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
    except ImportError as e:
        print(f"Error importing required modules: {e}")
        print("Make sure all dependencies are installed.")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 