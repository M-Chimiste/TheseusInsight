#!/usr/bin/env python3
"""
Robust backend startup script for packaged Electron app.
This script handles dependency installation and provides better error handling.
"""

import os
import sys
import subprocess
import importlib.util
from pathlib import Path
import json

def print_debug(message):
    """Print debug message with timestamp."""
    import datetime
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] DEBUG: {message}")

def check_and_install_package(package_name, import_name=None):
    """Check if package is available, try to install if not."""
    if import_name is None:
        import_name = package_name
    
    try:
        # Try to import the package
        __import__(import_name)
        print_debug(f"✅ {package_name} is available")
        return True
    except ImportError:
        print_debug(f"❌ {package_name} not found in bundled dependencies")
        print_debug(f"   This suggests the app was not built with bundled dependencies")
        print_debug(f"   Attempting installation as fallback...")
        
        try:
            # Try to install via pip as fallback
            result = subprocess.run([
                sys.executable, '-m', 'pip', 'install', package_name, '--user'
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                print_debug(f"✅ Successfully installed {package_name}")
                # Try import again
                __import__(import_name)
                return True
            else:
                print_debug(f"❌ Failed to install {package_name}: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print_debug(f"❌ Installation of {package_name} timed out")
            return False
        except Exception as e:
            print_debug(f"❌ Error installing {package_name}: {e}")
            return False

def setup_environment():
    """Setup environment for the backend."""
    print_debug("Setting up environment...")
    
    # Detect if we're running in a packaged Electron app
    is_packaged = os.getenv('ELECTRON_IS_PACKAGED', 'false').lower() == 'true'
    print_debug(f"Is packaged: {is_packaged}")
    
    # Get app root directory
    if is_packaged:
        resources_path = os.getenv('ELECTRON_RESOURCES_PATH', '')
        if resources_path:
            app_root = os.path.join(resources_path, 'app')
        else:
            app_root = os.path.dirname(os.path.abspath(__file__))
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        app_root = os.path.dirname(script_dir)
    
    print_debug(f"App root: {app_root}")
    print_debug(f"App root exists: {os.path.exists(app_root)}")
    
    # Set working directory
    os.chdir(app_root)
    print_debug(f"Working directory: {os.getcwd()}")
    
    # Add bundled Python dependencies to Python path
    python_deps_path = os.path.join(app_root, 'python_deps')
    if os.path.exists(python_deps_path):
        print_debug(f"✅ Found bundled Python dependencies: {python_deps_path}")
        if python_deps_path not in sys.path:
            sys.path.insert(0, python_deps_path)
        print_debug(f"Added to Python path: {python_deps_path}")
    else:
        print_debug(f"❌ Bundled Python dependencies not found: {python_deps_path}")
    
    # Add app root to Python path
    if app_root not in sys.path:
        sys.path.insert(0, app_root)
    
    # Set environment variables
    os.environ['THESEUS_APP_ROOT'] = app_root
    # DATABASE_URL is now expected to be set by the Electron main process (main.js)
    # if not os.getenv('DATABASE_URL'):
    #     os.environ['DATABASE_URL'] = 'postgresql://theseus:theseus@localhost:55432/theseusdb'
    
    return app_root

def check_backend_files(app_root):
    """Check if all required backend files exist."""
    print_debug("Checking backend files...")
    
    required_paths = [
        os.path.join(app_root, 'theseus_insight'),
        os.path.join(app_root, 'theseus_insight', 'main.py'),
        os.path.join(app_root, 'theseus_insight', '__init__.py'),
    ]
    
    missing_files = []
    for path in required_paths:
        if not os.path.exists(path):
            missing_files.append(path)
            print_debug(f"❌ Missing: {path}")
        else:
            print_debug(f"✅ Found: {path}")
    
    if missing_files:
        print_debug(f"❌ Missing required files: {missing_files}")
        return False
    
    return True

def install_required_packages():
    """Install required Python packages."""
    print_debug("Checking required packages...")
    
    required_packages = [
        ('fastapi', 'fastapi'),
        ('uvicorn', 'uvicorn'),
        # ('psycopg2-binary', 'psycopg2'), # Removed
        ('sqlite-vec', 'sqlite_vec'),   # Added, assuming 'sqlite_vec' is the import name
        ('sqlalchemy', 'sqlalchemy'),
        ('pydantic', 'pydantic'),
    ]
    
    failed_packages = []
    
    for package_name, import_name in required_packages:
        if not check_and_install_package(package_name, import_name):
            failed_packages.append(package_name)
    
    if failed_packages:
        print_debug(f"❌ Failed to install packages: {failed_packages}")
        return False
    
    print_debug("✅ All required packages are available")
    return True

def start_simple_server(app_root):
    """Start a simple HTTP server as fallback."""
    print_debug("Starting simple fallback server...")
    
    try:
        import http.server
        import socketserver
        from threading import Thread
        
        # Find the frontend files
        frontend_paths = [
            os.path.join(app_root, 'theseus-ui', 'dist'),
            os.path.join(app_root, 'theseus-ui', 'build'),
            os.path.join(app_root, 'frontend', 'dist'),
            os.path.join(app_root, 'static'),
        ]
        
        static_dir = None
        for path in frontend_paths:
            if os.path.exists(path):
                static_dir = path
                break
        
        if not static_dir:
            print_debug("❌ No frontend files found, creating minimal server")
            # Create a minimal response
            class MinimalHandler(http.server.SimpleHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'''
                    <html>
                    <body>
                        <h1>Theseus Insight</h1>
                        <p>Backend services are starting up...</p>
                        <p>If this message persists, there may be a configuration issue.</p>
                    </body>
                    </html>
                    ''')
            
            handler = MinimalHandler
        else:
            print_debug(f"✅ Serving frontend from: {static_dir}")
            os.chdir(static_dir)
            handler = http.server.SimpleHTTPRequestHandler
        
        with socketserver.TCPServer(("", 8000), handler) as httpd:
            print_debug("✅ Simple server started on port 8000")
            httpd.serve_forever()
            
    except Exception as e:
        print_debug(f"❌ Failed to start simple server: {e}")

def start_fastapi_server():
    """Start the full FastAPI server."""
    print_debug("Starting FastAPI server...")
    
    try:
        import uvicorn
        from theseus_insight.main import app
        
        print_debug("✅ Starting full FastAPI application")
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
    except Exception as e:
        print_debug(f"❌ Failed to start FastAPI server: {e}")
        raise

def main():
    """Main entry point."""
    print_debug("=== Theseus Insight Backend Startup ===")
    
    try:
        # Setup environment
        app_root = setup_environment()
        
        # Check if backend files exist
        if not check_backend_files(app_root):
            print_debug("❌ Backend files missing, starting simple server")
            start_simple_server(app_root)
            return
        
        # Try to install required packages
        if not install_required_packages():
            print_debug("❌ Package installation failed, starting simple server")
            start_simple_server(app_root)
            return
        
        # Try to start the full FastAPI server
        start_fastapi_server()
        
    except KeyboardInterrupt:
        print_debug("Backend stopped by user")
    except Exception as e:
        print_debug(f"❌ Unexpected error: {e}")
        print_debug("Starting fallback simple server...")
        try:
            app_root = setup_environment()
            start_simple_server(app_root)
        except Exception as e2:
            print_debug(f"❌ Even fallback server failed: {e2}")
            sys.exit(1)

if __name__ == "__main__":
    main() 