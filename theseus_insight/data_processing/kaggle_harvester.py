from __future__ import annotations

import json
import os
import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

from ..data_model.papers import ArxivRecord


class KaggleArxivHarvester:
    """Fallback harvester using Kaggle ArXiv dataset when OAI-PMH API is down.
    
    This harvester reads from the Kaggle ArXiv JSON dataset file and provides
    the same interface as the OAI-PMH harvester for seamless fallback.
    
    Dataset: https://www.kaggle.com/datasets/Cornell-University/arxiv
    
    Attributes:
        dataset_path (str): Path to the Kaggle ArXiv JSON dataset file
        category (str): ArXiv category to filter by (e.g., 'cs')
        date_from (str): Start date for filtering papers
        date_until (str): End date for filtering papers
        subcategories (List[str]): List of subcategories to include
        max_results (Optional[int]): Maximum number of results to return
        verbose (bool): Whether to print progress information
    """

    def __init__(
        self,
        dataset_path: str,
        category: str,
        date_from: str,
        date_until: str,
        *,
        subcategories: Optional[List[str]] = None,
        max_results: Optional[int] = None,
        verbose: bool = False,
    ):
        """Initialize the Kaggle ArXiv harvester.

        Args:
            dataset_path (str): Path to the Kaggle ArXiv JSON dataset file
            category (str): ArXiv category (e.g., 'cs')
            date_from (str): Start date for harvesting (YYYY-MM-DD)
            date_until (str): End date for harvesting (YYYY-MM-DD)
            subcategories (Optional[List[str]], optional): List of subcategories. Defaults to None.
            max_results (Optional[int], optional): Maximum number of results. Defaults to None.
            verbose (bool, optional): Whether to print progress. Defaults to False.
        """
        self.dataset_path = Path(dataset_path)
        self.category = category
        self.date_from = date_from
        self.date_until = date_until
        self.subcategories = [s.lower() for s in subcategories] if subcategories else None
        self.max_results = max_results
        self.verbose = verbose

        self._records: List[Dict[str, Any]] = []
        self._debug_mode = os.getenv("DEBUG", "").lower() == "true"

        if self._debug_mode:
            self._debug_log("Kaggle ArXiv harvester initialized")
            self._debug_log(f"Dataset path: {self.dataset_path}")
            self._debug_log(f"Category: {category}, Date range: {date_from} to {date_until}")
            self._debug_log(f"Subcategories: {subcategories}")

    def _debug_log(self, msg: str) -> None:
        """Print debug message if DEBUG environment variable is 'true'."""
        if self._debug_mode:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[KAGGLE DEBUG {timestamp}] {msg}", flush=True)

    def _log(self, msg: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(msg, flush=True)

    def _parse_kaggle_date(self, date_str: str) -> Optional[datetime.date]:
        """Parse various date formats from Kaggle dataset.
        
        Args:
            date_str (str): Date string from Kaggle dataset
            
        Returns:
            Optional[datetime.date]: Parsed date or None if invalid
        """
        if not date_str:
            return None
            
        # Common ArXiv date formats
        formats = [
            "%Y-%m-%d",      # 2024-01-15
            "%Y-%m",         # 2024-01 (assume day 1)
            "%Y",            # 2024 (assume Jan 1)
            "%a, %d %b %Y %H:%M:%S %Z",  # Full timestamp
        ]
        
        for fmt in formats:
            try:
                if fmt == "%Y-%m":
                    return datetime.datetime.strptime(date_str, fmt).replace(day=1).date()
                elif fmt == "%Y":
                    return datetime.datetime.strptime(date_str, fmt).replace(month=1, day=1).date()
                else:
                    return datetime.datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        self._debug_log(f"Could not parse date: {date_str}")
        return None

    def _matches_category(self, categories: str) -> bool:
        """Check if paper matches requested category and subcategories.
        
        Args:
            categories (str): Categories string from Kaggle dataset
            
        Returns:
            bool: True if matches, False otherwise
        """
        if not categories:
            return False
            
        categories_lower = categories.lower()
        
        # Check main category
        if self.category.lower() not in categories_lower:
            return False
            
        # Check subcategories if specified
        if self.subcategories:
            return any(sub in categories_lower for sub in self.subcategories)
            
        return True

    def _in_date_range(self, update_date: str) -> bool:
        """Check if paper is within the requested date range.
        
        Args:
            update_date (str): Update date from Kaggle dataset
            
        Returns:
            bool: True if in range, False otherwise
        """
        paper_date = self._parse_kaggle_date(update_date)
        if not paper_date:
            return False
            
        try:
            start_date = datetime.datetime.strptime(self.date_from, "%Y-%m-%d").date()
            end_date = datetime.datetime.strptime(self.date_until, "%Y-%m-%d").date()
            
            in_range = start_date <= paper_date <= end_date
            self._debug_log(f"Date check: {update_date} -> {paper_date}, in_range: {in_range}")
            return in_range
        except ValueError as e:
            self._debug_log(f"Date range parsing error: {e}")
            return False

    def _convert_to_arxiv_record(self, kaggle_record: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Kaggle dataset record to ArXiv record format.
        
        Args:
            kaggle_record (Dict[str, Any]): Record from Kaggle dataset
            
        Returns:
            Dict[str, Any]: Record in ArXiv format compatible with existing code
        """
        # Get the ArXiv ID and construct URLs
        arxiv_id = kaggle_record.get("id", "")
        
        # Construct standard ArXiv URLs based on ID
        arxiv_url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else ""
        
        # Map Kaggle fields to ArXiv record fields
        return {
            "id": arxiv_id,
            "url": arxiv_url,
            "pdf_url": pdf_url,
            "title": kaggle_record.get("title", ""),
            "authors": kaggle_record.get("authors", ""),
            "abstract": kaggle_record.get("abstract", ""),
            "categories": kaggle_record.get("categories", ""),
            "created": kaggle_record.get("update_date", ""),  # Use update_date as created
            "updated": kaggle_record.get("update_date", ""),
            "doi": kaggle_record.get("doi", ""),
            "affiliation": [],  # Kaggle dataset doesn't have affiliations, use empty list
            "submitter": kaggle_record.get("submitter", ""),
            "journal_ref": kaggle_record.get("journal-ref", ""),
            "report_no": kaggle_record.get("report-no", ""),
            "comments": kaggle_record.get("comments", ""),
            "license": kaggle_record.get("license", ""),
        }

    def harvest(self) -> List[Dict[str, Any]]:
        """Harvest records from the Kaggle ArXiv dataset.
        
        Returns:
            List[Dict[str, Any]]: List of harvested records
            
        Raises:
            FileNotFoundError: If dataset file doesn't exist
            RuntimeError: If dataset processing fails
        """
        self._debug_log("Starting Kaggle dataset harvest")
        self._records.clear()

        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Kaggle dataset file not found: {self.dataset_path}")

        self._log(f"Reading Kaggle ArXiv dataset from: {self.dataset_path}")
        
        processed_count = 0
        matched_count = 0
        filtered_category = 0
        filtered_date = 0
        
        try:
            with open(self.dataset_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if line_num % 10000 == 0:
                        self._log(f"Processed {line_num} lines, found {matched_count} matches...")
                    
                    try:
                        record = json.loads(line.strip())
                        processed_count += 1
                        
                        # Filter by category and subcategories
                        if not self._matches_category(record.get("categories", "")):
                            filtered_category += 1
                            continue
                            
                        # Filter by date range
                        if not self._in_date_range(record.get("update_date", "")):
                            filtered_date += 1
                            continue
                            
                        # Convert to ArXiv record format
                        arxiv_record = self._convert_to_arxiv_record(record)
                        self._records.append(arxiv_record)
                        matched_count += 1
                        
                        self._debug_log(f"Matched record {matched_count}: {arxiv_record['id']}")
                        
                        # Check max results limit
                        if self.max_results and len(self._records) >= self.max_results:
                            self._debug_log(f"Reached max_results limit: {self.max_results}")
                            break
                            
                    except json.JSONDecodeError as e:
                        self._debug_log(f"JSON decode error on line {line_num}: {e}")
                        continue
                        
        except Exception as e:
            raise RuntimeError(f"Failed to process Kaggle dataset: {e}")

        self._log(f"Kaggle harvest completed:")
        self._log(f"  Processed: {processed_count} records")
        self._log(f"  Filtered by category: {filtered_category}")
        self._log(f"  Filtered by date: {filtered_date}")
        self._log(f"  Final matches: {matched_count}")
        
        self._debug_log(f"Kaggle harvest summary: {len(self._records)} records collected")
        return self._records

    def check_dataset_availability(self) -> bool:
        """Check if the Kaggle dataset file is available.
        
        Returns:
            bool: True if dataset is available, False otherwise
        """
        available = self.dataset_path.exists() and self.dataset_path.is_file()
        self._debug_log(f"Kaggle dataset availability: {available} (path: {self.dataset_path})")
        return available

    def get_dataset_info(self) -> Dict[str, Any]:
        """Get information about the Kaggle dataset.
        
        Returns:
            Dict[str, Any]: Dataset information
        """
        if not self.check_dataset_availability():
            return {"available": False, "path": str(self.dataset_path)}
            
        try:
            size_mb = self.dataset_path.stat().st_size / (1024 * 1024)
            modified = datetime.datetime.fromtimestamp(self.dataset_path.stat().st_mtime)
            
            return {
                "available": True,
                "path": str(self.dataset_path),
                "size_mb": round(size_mb, 2),
                "last_modified": modified.strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as e:
            return {
                "available": False,
                "path": str(self.dataset_path),
                "error": str(e)
            }

    def to_dataframe(self):
        """Convert harvested records to a pandas DataFrame.
        
        Returns:
            pandas.DataFrame: DataFrame containing all harvested records
            
        Raises:
            RuntimeError: If pandas is not installed
        """
        try:
            import pandas as pd
        except ImportError:
            raise RuntimeError("pandas is not installed (`pip install pandas`)")
            
        if not self._records:
            self.harvest()
        return pd.DataFrame(self._records) 