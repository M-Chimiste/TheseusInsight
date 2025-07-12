"""Optimized Kaggle dataset processor with date indexing and caching."""

import json
import os
import pickle
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Iterator, Tuple
from dataclasses import dataclass
import mmap
import bisect


@dataclass
class DateIndex:
    """Index entry for quick date-based lookups."""
    date: str
    file_position: int
    line_number: int


class OptimizedKaggleProcessor:
    """Optimized processor for Kaggle ArXiv dataset with date indexing."""
    
    def __init__(self, dataset_path: str, index_dir: Optional[str] = None):
        """Initialize the optimized processor.
        
        Args:
            dataset_path: Path to the Kaggle JSON dataset
            index_dir: Directory to store index files (default: same as dataset)
        """
        self.dataset_path = Path(dataset_path)
        self.index_dir = Path(index_dir) if index_dir else self.dataset_path.parent
        self.index_dir.mkdir(exist_ok=True)
        
        # Index file paths
        self.date_index_path = self.index_dir / f"{self.dataset_path.stem}_date_index.pkl"
        self.metadata_path = self.index_dir / f"{self.dataset_path.stem}_metadata.json"
        
        self._date_index: Optional[List[DateIndex]] = None
        self._metadata: Optional[Dict] = None
        self._file_handle = None
        self._mmap = None
    
    def _load_or_build_index(self, force_rebuild: bool = False) -> None:
        """Load existing index or build a new one."""
        if not force_rebuild and self.date_index_path.exists():
            # Load existing index
            print("📂 Loading existing date index...")
            with open(self.date_index_path, 'rb') as f:
                self._date_index = pickle.load(f)
            
            # Load metadata
            if self.metadata_path.exists():
                with open(self.metadata_path, 'r') as f:
                    self._metadata = json.load(f)
            
            print(f"✅ Loaded index with {len(self._date_index)} entries")
            print(f"   Date range: {self._date_index[0].date} to {self._date_index[-1].date}")
        else:
            # Build new index
            print("🔨 Building date index (this is a one-time operation)...")
            self._build_date_index()
    
    def _build_date_index(self) -> None:
        """Build a date-based index of the dataset."""
        index_entries = []
        line_count = 0
        earliest_date = None
        latest_date = None
        
        with open(self.dataset_path, 'r', encoding='utf-8') as f:
            file_position = 0
            
            for line_num, line in enumerate(f, 1):
                if line_num % 100000 == 0:
                    print(f"   Processed {line_num:,} lines...")
                
                # Record position before reading line
                line_start = file_position
                file_position = f.tell()
                
                try:
                    # Quick JSON parse to get date
                    record = json.loads(line.strip())
                    update_date = record.get("update_date", "")
                    
                    if update_date:
                        # Normalize date to YYYY-MM-DD format
                        parsed_date = self._parse_date_fast(update_date)
                        if parsed_date:
                            date_str = parsed_date.strftime("%Y-%m-%d")
                            
                            # Create index entry
                            entry = DateIndex(
                                date=date_str,
                                file_position=line_start,
                                line_number=line_num
                            )
                            index_entries.append(entry)
                            
                            # Track date range
                            if not earliest_date or date_str < earliest_date:
                                earliest_date = date_str
                            if not latest_date or date_str > latest_date:
                                latest_date = date_str
                    
                    line_count = line_num
                    
                except (json.JSONDecodeError, KeyError):
                    # Skip malformed records
                    continue
        
        # Sort index by date
        index_entries.sort(key=lambda x: x.date)
        
        # Save index
        with open(self.date_index_path, 'wb') as f:
            pickle.dump(index_entries, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        # Save metadata
        metadata = {
            "total_lines": line_count,
            "indexed_records": len(index_entries),
            "earliest_date": earliest_date,
            "latest_date": latest_date,
            "file_size": self.dataset_path.stat().st_size,
            "index_created": datetime.datetime.now().isoformat()
        }
        with open(self.metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self._date_index = index_entries
        self._metadata = metadata
        
        print(f"✅ Index built successfully!")
        print(f"   Total records: {line_count:,}")
        print(f"   Indexed records: {len(index_entries):,}")
        print(f"   Date range: {earliest_date} to {latest_date}")
    
    def _parse_date_fast(self, date_str: str) -> Optional[datetime.datetime]:
        """Fast date parsing optimized for common formats."""
        if not date_str:
            return None
        
        # Most common format in ArXiv: YYYY-MM-DD
        if len(date_str) >= 10 and date_str[4] == '-' and date_str[7] == '-':
            try:
                return datetime.datetime.strptime(date_str[:10], "%Y-%m-%d")
            except ValueError:
                pass
        
        # Fallback to other formats
        formats = ["%Y-%m", "%Y"]
        for fmt in formats:
            try:
                return datetime.datetime.strptime(date_str[:len(fmt)], fmt)
            except ValueError:
                continue
        
        return None
    
    def get_records_in_date_range(
        self,
        start_date: str,
        end_date: str,
        category: Optional[str] = None,
        subcategories: Optional[List[str]] = None,
        max_results: Optional[int] = None
    ) -> Iterator[Dict]:
        """Get records in a specific date range using the index.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            category: Optional category filter
            subcategories: Optional subcategory filters
            max_results: Maximum number of results
            
        Yields:
            Matching records as dictionaries
        """
        # Ensure index is loaded
        if self._date_index is None:
            self._load_or_build_index()
        
        # Find date range in index using binary search
        start_idx = bisect.bisect_left(self._date_index, start_date, key=lambda x: x.date)
        end_idx = bisect.bisect_right(self._date_index, end_date, key=lambda x: x.date)
        
        print(f"🔍 Searching date range {start_date} to {end_date}")
        print(f"   Index range: {start_idx} to {end_idx} ({end_idx - start_idx} potential matches)")
        
        # Open file with memory mapping for fast random access
        with open(self.dataset_path, 'rb') as f:
            # Memory map the file for efficient random access
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mmapped_file:
                count = 0
                
                # Process only the relevant date range
                for i in range(start_idx, end_idx):
                    if max_results and count >= max_results:
                        break
                    
                    entry = self._date_index[i]
                    
                    # Seek to the line position
                    mmapped_file.seek(entry.file_position)
                    
                    # Read until newline
                    line = mmapped_file.readline()
                    
                    try:
                        record = json.loads(line.decode('utf-8').strip())
                        
                        # Apply category filter if specified
                        if category or subcategories:
                            categories = record.get("categories", "")
                            if not self._matches_category(categories, category, subcategories):
                                continue
                        
                        count += 1
                        yield record
                        
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
        
        print(f"✅ Returned {count} records")
    
    def _matches_category(
        self,
        categories: str,
        category: Optional[str],
        subcategories: Optional[List[str]]
    ) -> bool:
        """Check if record matches category filters."""
        if not category and not subcategories:
            return True
        
        categories_lower = categories.lower()
        
        # Check main category
        if category and f"{category}." not in categories_lower:
            return False
        
        # Check subcategories
        if subcategories:
            return any(subcat.lower() in categories_lower for subcat in subcategories)
        
        return True
    
    def get_date_range(self) -> Tuple[str, str]:
        """Get the date range covered by the dataset."""
        if self._metadata is None:
            self._load_or_build_index()
        
        return self._metadata["earliest_date"], self._metadata["latest_date"]
    
    def estimate_records_in_range(self, start_date: str, end_date: str) -> int:
        """Estimate number of records in date range without reading them."""
        if self._date_index is None:
            self._load_or_build_index()
        
        start_idx = bisect.bisect_left(self._date_index, start_date, key=lambda x: x.date)
        end_idx = bisect.bisect_right(self._date_index, end_date, key=lambda x: x.date)
        
        return end_idx - start_idx