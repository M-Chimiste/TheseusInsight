from __future__ import annotations

import os
import tempfile
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional
from pathlib import Path

from .harvester import ArxivOAIHarvester
from .kaggle_harvester import KaggleArxivHarvester


class UnifiedArxivHarvester:
    """Unified ArXiv harvester that tries OAI-PMH first and falls back to Kaggle dataset.
    
    This harvester provides a seamless experience by automatically trying the live
    OAI-PMH API first, and falling back to the Kaggle dataset if the API is down
    or unresponsive.
    
    Environment Variables:
        KAGGLE_ARXIV_PATH: Path to the Kaggle ArXiv dataset JSON file
        FORCE_KAGGLE: Set to "true" to skip OAI-PMH and use Kaggle directly
        DEBUG: Set to "true" for detailed logging
        KAGGLE_USERNAME: Kaggle username for API access
        KAGGLE_KEY: Kaggle API key for authentication
        AUTO_DOWNLOAD: Set to "true" to enable automatic Kaggle dataset download
    """

    def __init__(
        self,
        category: str,
        date_from: str,
        date_until: str,
        *,
        subcategories: Optional[List[str]] = None,
        max_results: Optional[int] = None,
        timeout: int = 300,
        verbose: bool = False,
        kaggle_dataset_path: Optional[str] = None,
    ):
        """Initialize the unified harvester.

        Args:
            category (str): ArXiv category (e.g., 'cs')
            date_from (str): Start date for harvesting (YYYY-MM-DD)
            date_until (str): End date for harvesting (YYYY-MM-DD)
            subcategories (Optional[List[str]], optional): List of subcategories
            max_results (Optional[int], optional): Maximum number of results
            timeout (int, optional): Timeout for OAI-PMH requests. Defaults to 300.
            verbose (bool, optional): Whether to print progress. Defaults to False.
            kaggle_dataset_path (Optional[str], optional): Path to Kaggle dataset. 
                If None, uses KAGGLE_ARXIV_PATH environment variable.
        """
        self.category = category
        self.date_from = date_from
        self.date_until = date_until
        self.subcategories = subcategories
        self.max_results = max_results
        self.timeout = timeout
        self.verbose = verbose

        # Determine Kaggle dataset path
        self.kaggle_dataset_path = (
            kaggle_dataset_path or 
            os.getenv("KAGGLE_ARXIV_PATH") or
            "data/arxiv-metadata-oai-snapshot.json"  # Default relative path
        )

        self._debug_mode = os.getenv("DEBUG", "").lower() == "true"
        self._force_kaggle = os.getenv("FORCE_KAGGLE", "").lower() == "true"
        self._auto_download = os.getenv("AUTO_DOWNLOAD", "true").lower() == "true"  # Default to true
        self._temp_dir = None
        self._downloaded_dataset = False
        
        # Initialize harvesters
        self.oai_harvester = ArxivOAIHarvester(
            category=category,
            date_from=date_from,
            date_until=date_until,
            subcategories=subcategories,
            max_results=max_results,
            timeout=timeout,
            verbose=verbose,
        )
        
        self.kaggle_harvester = KaggleArxivHarvester(
            dataset_path=self.kaggle_dataset_path,
            category=category,
            date_from=date_from,
            date_until=date_until,
            subcategories=subcategories,
            max_results=max_results,
            verbose=verbose,
        )

        if self._debug_mode:
            self._debug_log("Unified ArXiv harvester initialized")
            self._debug_log(f"Force Kaggle mode: {self._force_kaggle}")
            self._debug_log(f"Auto download mode: {self._auto_download}")
            self._debug_log(f"Kaggle dataset path: {self.kaggle_dataset_path}")

    def _debug_log(self, msg: str) -> None:
        """Print debug message if DEBUG environment variable is 'true'."""
        if self._debug_mode:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[UNIFIED DEBUG {timestamp}] {msg}", flush=True)

    def _log(self, msg: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(msg, flush=True)

    def _install_kaggle_api(self) -> bool:
        """Install Kaggle API if not available.
        
        Returns:
            bool: True if Kaggle API is available after installation
        """
        try:
            import kaggle
            return True
        except ImportError:
            if not self._auto_download:
                return False
                
            self._debug_log("Kaggle API not found - attempting to install...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "kaggle"])
                import kaggle
                self._debug_log("Successfully installed Kaggle API")
                return True
            except Exception as e:
                self._debug_log(f"Failed to install Kaggle API: {e}")
                return False

    def _check_kaggle_credentials(self) -> bool:
        """Check if Kaggle API credentials are available.
        
        Returns:
            bool: True if credentials are properly configured
        """
        # Check environment variables
        username = os.getenv("KAGGLE_USERNAME")
        key = os.getenv("KAGGLE_KEY")
        
        if username and key:
            self._debug_log("Found Kaggle credentials in environment variables")
            return True
            
        # Check for kaggle.json file
        kaggle_config_path = Path.home() / ".kaggle" / "kaggle.json"
        if kaggle_config_path.exists():
            self._debug_log(f"Found Kaggle credentials at {kaggle_config_path}")
            return True
            
        self._debug_log("No Kaggle credentials found")
        return False

    def _download_kaggle_dataset(self) -> Optional[str]:
        """Download the Kaggle ArXiv dataset to a temporary directory.
        
        Returns:
            Optional[str]: Path to the downloaded dataset file, or None if failed
        """
        if not self._auto_download:
            self._debug_log("Auto download is disabled")
            return None
            
        if not self._install_kaggle_api():
            self._debug_log("Kaggle API not available")
            return None
            
        if not self._check_kaggle_credentials():
            self._debug_log("Kaggle credentials not configured")
            return None
            
        try:
            import kaggle
            import threading
            import time
            
            # Create temporary directory
            self._temp_dir = tempfile.mkdtemp(prefix="arxiv_kaggle_")
            self._debug_log(f"Created temporary directory: {self._temp_dir}")
            
            # Download dataset
            self._log("📥 Downloading Kaggle ArXiv dataset (3.1GB - this will take several minutes)...")
            self._debug_log("Starting Kaggle dataset download...")
            
            # Track download progress
            download_complete = threading.Event()
            download_error = None
            
            def download_worker():
                nonlocal download_error
                try:
                    kaggle.api.dataset_download_files(
                        "cornell-university/arxiv",
                        path=self._temp_dir,
                        unzip=True
                    )
                except Exception as e:
                    download_error = e
                finally:
                    download_complete.set()
            
            # Start download in background thread
            download_thread = threading.Thread(target=download_worker, daemon=True)
            download_thread.start()
            
            # Monitor progress and send periodic updates
            progress_dots = 0
            while not download_complete.is_set():
                # Wait for 30 seconds or until download completes
                if download_complete.wait(timeout=30):
                    break
                    
                # Send periodic progress updates to keep connection alive
                progress_dots += 1
                dots = "." * (progress_dots % 4)
                self._log(f"📥 Still downloading{dots} (large file, please wait)")
                self._debug_log(f"Download progress check {progress_dots} - still downloading")
            
            # Wait for thread to complete
            download_thread.join(timeout=5)
            
            # Check for download errors
            if download_error:
                raise download_error
            
            # Find the JSON file
            dataset_path = Path(self._temp_dir) / "arxiv-metadata-oai-snapshot.json"
            if dataset_path.exists():
                file_size_mb = dataset_path.stat().st_size / (1024*1024)
                self._debug_log(f"Successfully downloaded dataset to: {dataset_path}")
                self._log(f"✅ Download complete: {file_size_mb:.1f} MB")
                self._downloaded_dataset = True
                return str(dataset_path)
            else:
                self._debug_log("Dataset file not found after download")
                return None
                
        except Exception as e:
            self._debug_log(f"Failed to download Kaggle dataset: {e}")
            self._log(f"❌ Download failed: {e}")
            return None

    def _cleanup_downloaded_dataset(self) -> None:
        """Clean up downloaded dataset files."""
        if self._downloaded_dataset and self._temp_dir and Path(self._temp_dir).exists():
            try:
                self._debug_log(f"Cleaning up temporary directory: {self._temp_dir}")
                shutil.rmtree(self._temp_dir)
                self._log("🧹 Cleaned up downloaded dataset")
                self._temp_dir = None
                self._downloaded_dataset = False
            except Exception as e:
                self._debug_log(f"Failed to cleanup temporary directory: {e}")

    def check_kaggle_availability(self) -> bool:
        """Check if Kaggle dataset is available (existing file or can be downloaded).
        
        Returns:
            bool: True if Kaggle dataset is available
        """
        # Check if existing file is available
        if self.kaggle_harvester.check_dataset_availability():
            return True
            
        # Check if we can download it
        if self._auto_download:
            return self._install_kaggle_api() and self._check_kaggle_credentials()
            
        return False

    def get_status(self) -> Dict[str, Any]:
        """Get status of both harvesting methods.
        
        Returns:
            Dict[str, Any]: Status information for both OAI-PMH and Kaggle
        """
        status = {
            "oai_pmh": {"available": False, "error": None},
            "kaggle": self.kaggle_harvester.get_dataset_info(),
            "force_kaggle": self._force_kaggle,
        }

        # Check OAI-PMH availability (quick test)
        try:
            if self.oai_harvester.check_service_health():
                status["oai_pmh"]["available"] = True
            else:
                status["oai_pmh"]["error"] = "Service health check failed"
        except Exception as e:
            status["oai_pmh"]["error"] = str(e)

        return status

    def harvest(self) -> List[Dict[str, Any]]:
        """Harvest ArXiv papers using OAI-PMH first, falling back to Kaggle.
        
        Returns:
            List[Dict[str, Any]]: List of harvested papers
            
        Raises:
            RuntimeError: If both methods fail
        """
        self._debug_log("Starting unified harvest")
        
        try:
            # Check if we should force Kaggle mode
            if self._force_kaggle:
                self._debug_log("FORCE_KAGGLE=true - using Kaggle dataset directly")
                self._log("Using Kaggle dataset (forced mode)")
                return self._harvest_with_kaggle()

            # Try OAI-PMH first
            try:
                self._debug_log("Attempting OAI-PMH harvest")
                self._log("Trying ArXiv OAI-PMH API...")
                
                records = self.oai_harvester.harvest()
                
                if records:
                    self._log(f"✅ OAI-PMH harvest successful: {len(records)} records")
                    self._debug_log(f"OAI-PMH harvest completed with {len(records)} records")
                    return records
                else:
                    self._log("⚠️  OAI-PMH returned no records, trying Kaggle fallback...")
                    self._debug_log("OAI-PMH returned empty results - trying Kaggle")
                    
            except Exception as e:
                self._log(f"❌ OAI-PMH failed: {e}")
                self._debug_log(f"OAI-PMH harvest failed: {e}")
                self._log("🔄 Falling back to Kaggle dataset...")

            # Fall back to Kaggle
            return self._harvest_with_kaggle()
            
        except Exception as e:
            # Ensure cleanup on any error
            if self._downloaded_dataset:
                self._cleanup_downloaded_dataset()
            raise e

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup."""
        if self._downloaded_dataset:
            self._cleanup_downloaded_dataset()

    def _harvest_with_kaggle(self) -> List[Dict[str, Any]]:
        """Harvest using Kaggle dataset.
        
        Returns:
            List[Dict[str, Any]]: List of harvested papers
            
        Raises:
            RuntimeError: If Kaggle harvest fails
        """
        try:
            # Check if we have an existing dataset file
            if not self.kaggle_harvester.check_dataset_availability():
                self._debug_log("Local Kaggle dataset not found - attempting download")
                
                # Try to download the dataset
                downloaded_path = self._download_kaggle_dataset()
                if downloaded_path:
                    # Update harvester to use downloaded file
                    self.kaggle_harvester.dataset_path = Path(downloaded_path)
                    self.kaggle_dataset_path = downloaded_path
                    self._debug_log(f"Updated harvester to use downloaded dataset: {downloaded_path}")
                else:
                    raise RuntimeError(
                        f"Kaggle dataset not available and download failed.\n"
                        f"Options:\n"
                        f"1. Download manually from: https://www.kaggle.com/datasets/Cornell-University/arxiv\n"
                        f"2. Set KAGGLE_ARXIV_PATH environment variable\n" 
                        f"3. Configure Kaggle API credentials (KAGGLE_USERNAME, KAGGLE_KEY)\n"
                        f"4. Place kaggle.json in ~/.kaggle/"
                    )

            self._debug_log("Starting Kaggle dataset harvest")
            records = self.kaggle_harvester.harvest()
            
            if records:
                self._log(f"✅ Kaggle harvest successful: {len(records)} records")
                self._debug_log(f"Kaggle harvest completed with {len(records)} records")
                return records
            else:
                raise RuntimeError("Kaggle dataset returned no matching records")
                
        except Exception as e:
            self._log(f"❌ Kaggle harvest failed: {e}")
            raise RuntimeError(f"Both OAI-PMH and Kaggle harvest methods failed. Last error: {e}")
        finally:
            # Always cleanup downloaded files
            if self._downloaded_dataset:
                self._cleanup_downloaded_dataset()

    def to_dataframe(self):
        """Convert harvested records to a pandas DataFrame.
        
        This method will attempt to harvest if no records are available.
        
        Returns:
            pandas.DataFrame: DataFrame containing harvested records
        """
        records = self.harvest()
        
        try:
            import pandas as pd
            return pd.DataFrame(records)
        except ImportError:
            raise RuntimeError("pandas is not installed (`pip install pandas`)")

    def get_harvest_info(self) -> Dict[str, Any]:
        """Get information about the harvesting setup and capabilities.
        
        Returns:
            Dict[str, Any]: Information about available harvest methods
        """
        return {
            "category": self.category,
            "date_range": f"{self.date_from} to {self.date_until}",
            "subcategories": self.subcategories,
            "max_results": self.max_results,
            "methods": {
                "oai_pmh": {
                    "available": True,
                    "timeout": self.timeout,
                },
                "kaggle": {
                    "available": self.check_kaggle_availability(),
                    "path": self.kaggle_dataset_path,
                    "info": self.kaggle_harvester.get_dataset_info(),
                }
            },
            "force_kaggle": self._force_kaggle,
        } 