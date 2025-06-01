#!/usr/bin/env python3
"""
Simple Backend Startup Script for Theseus Insight
Focuses on getting the core FastAPI server running with minimal complexity.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting Theseus Insight backend (simple mode)")
    
    # Get the project root directory
    if hasattr(sys, '_MEIPASS'):
        # Running from PyInstaller bundle
        project_root = Path(sys._MEIPASS)
    else:
        # Running from source
        project_root = Path(__file__).parent.parent
    
    logger.info(f"Project root: {project_root}")
    
    # Ensure we can import theseus_insight
    sys.path.insert(0, str(project_root))
    
    try:
        # Try importing the main app to validate environment
        from theseus_insight.main import app
        logger.info("Successfully imported Theseus Insight application")
        
        # Start the server using uvicorn
        import uvicorn
        
        logger.info("Starting uvicorn server on http://0.0.0.0:8000")
        uvicorn.run(
            "theseus_insight.main:app",
            host="0.0.0.0",
            port=8000,
            log_level="info",
            reload=False  # Disable reload in production
        )
        
    except ImportError as e:
        logger.error(f"Failed to import Theseus Insight: {e}")
        logger.error("This might indicate missing dependencies or incorrect project structure")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"Unexpected error starting backend: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 