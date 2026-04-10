from __future__ import annotations

# Standard library imports
import os
import random
import threading
import time
import datetime
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

# Third-party imports
import requests
import pandas as pd

from ..data_model.papers import ArxivRecord
from ..constants import _ARXIV_NS, _BASE_URL, _FALLBACK_URLS, _OAI_NS, _MIN_INTERVAL


class ArxivOAIHarvester:
    """A rate-limit-compliant OAI-PMH harvester for ArXiv papers.

    This harvester respects ArXiv's rate limits and provides functionality to
    download paper metadata in batches. It handles retries, backoff, and pagination
    automatically.

    Attributes:
        set (str): The ArXiv category to harvest (e.g., 'cs:AI').
        date_from (str): Start date for harvesting.
        date_until (str): End date for harvesting.
        max_results (Optional[int]): Maximum number of results to retrieve.
        timeout (int): Maximum time in seconds for the entire harvesting operation.
        base_delay (float): Base delay between requests in seconds.
        max_delay (float): Maximum delay between requests in seconds.
        verbose (bool): Whether to print progress information.
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
        base_delay: float = 1.5,
        max_delay: float = 60,
        verbose: bool = False,
        session: Optional[requests.Session] = None,
    ):
        """Initialize the ArXiv OAI harvester.

        Args:
            category (str): ArXiv category (e.g., 'cs').
            date_from (str): Start date for harvesting.
            date_until (str): End date for harvesting.
            subcategories (Optional[List[str]], optional): List of subcategories to harvest. (e.g. ["cs.ai", "cs.cl"]) Defaults to None.
            max_results (Optional[int], optional): Maximum number of results. Defaults to None.
            timeout (int, optional): Operation timeout in seconds. Defaults to 300.
            base_delay (float, optional): Base delay between requests. Defaults to 1.5.
            max_delay (float, optional): Maximum delay between requests. Defaults to 60.
            verbose (bool, optional): Whether to print progress. Defaults to False.
            session (Optional[requests.Session], optional): Custom requests session. Defaults to None.
        """
        self.set = category
        self.date_from = date_from
        self.date_until = date_until
        self.subcategories = [s.lower() for s in subcategories] if subcategories else None
        self.max_results = max_results
        self.timeout = timeout
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.verbose = verbose

        self._session = session or requests.Session()
        self._records: List[Dict[str, Any]] = []

        self._last_call = 0.0  # Unix-epoch timestamp
        self._lock = threading.Lock()
        
        # URL management
        self._current_url = _BASE_URL
        self._tried_urls = set()
        
        # Debug mode check
        self._debug_mode = os.getenv("DEBUG", "").lower() == "true"
        if self._debug_mode:
            self._debug_log("Debug mode enabled for ArxivOAIHarvester")
            self._debug_log(f"Initialized with: category={category}, date_from={date_from}, date_until={date_until}")
            self._debug_log(f"Subcategories: {subcategories}, max_results={max_results}, timeout={timeout}")
            self._debug_log(f"Available fallback URLs: {_FALLBACK_URLS}")

    def _try_next_url(self) -> bool:
        """Try the next available URL from the fallback list.
        
        Returns:
            bool: True if a new URL was set, False if no more URLs to try.
        """
        self._tried_urls.add(self._current_url)
        
        for url in _FALLBACK_URLS:
            if url not in self._tried_urls:
                self._debug_log(f"Switching from {self._current_url} to fallback URL: {url}")
                self._current_url = url
                return True
        
        self._debug_log("No more fallback URLs available")
        return False

    def check_service_health(self) -> bool:
        """Check if ArXiv OAI-PMH ListRecords endpoint is responsive.
        
        Returns:
            bool: True if service is healthy, False otherwise.
        """
        self._debug_log("Checking ArXiv OAI-PMH service health...")
        
        # Test basic connectivity first
        import socket
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(self._current_url)
            host = parsed_url.hostname
            port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
            
            self._debug_log(f"Testing network connectivity to {host}:{port}")
            sock = socket.create_connection((host, port), timeout=10)
            sock.close()
            self._debug_log(f"Network connectivity to {host}:{port} successful")
        except Exception as exc:
            self._debug_log(f"Network connectivity failed to {host}:{port}: {exc}")
            self._debug_log(f"Server {host} appears to be down or unreachable")
            
            # Try next URL if available
            if self._try_next_url():
                self._debug_log("Retrying health check with fallback URL...")
                return self.check_service_health()  # Recursive retry with new URL
            return False
        
        identify_params = {"verb": "Identify"}

        try:
            request_timeout = 10
            self._debug_log(f"Testing Identify endpoint at {self._current_url} with {request_timeout}s timeout")
            resp = self._session.get(self._current_url, params=identify_params, timeout=request_timeout)
            if resp.status_code != 200:
                self._debug_log(f"Identify test failed - HTTP {resp.status_code}")
                raise Exception(f"HTTP {resp.status_code}")
            self._debug_log("Identify test passed - ArXiv OAI-PMH is responsive")
            return True
        except Exception as exc:
            self._debug_log(f"Identify test failed - {exc}")
            is_connection_issue = any(keyword in str(exc).lower() for keyword in
                                    ['timeout', 'connection', 'unreachable', 'refused', 'reset', 'read timed out'])
            if is_connection_issue and self._try_next_url():
                self._debug_log("Identify failed with connection issue - trying fallback URL...")
                return self.check_service_health()
            return False

    def _log(self, msg: str) -> None:
        """Print a message if verbose mode is enabled.

        Args:
            msg (str): Message to print.
        """
        if self.verbose:
            print(msg, flush=True)
            
    def _debug_log(self, msg: str) -> None:
        """Print a debug message if DEBUG environment variable is 'true'.

        Args:
            msg (str): Debug message to print.
        """
        if self._debug_mode:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[DEBUG {timestamp}] {msg}", flush=True)

    def _exp_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter.

        Args:
            attempt (int): Current attempt number.

        Returns:
            float: Delay duration in seconds.
        """
        delay = min(self.max_delay, self.base_delay * 2**attempt)
        return delay + random.uniform(-0.25 * delay, 0.25 * delay)

    def _throttle(self, extra: float = 0.0) -> None:
        """Ensure minimum time between API calls.

        Args:
            extra (float, optional): Additional delay in seconds. Defaults to 0.0.
        """
        with self._lock:
            wait = max(0.0, (_MIN_INTERVAL + extra) - (time.time() - self._last_call))
            if wait:
                self._debug_log(f"Throttling request - waiting {wait:.2f}s (min_interval={_MIN_INTERVAL}, extra={extra})")
                time.sleep(wait)
            self._last_call = time.time()

    def _request(self, params: Dict[str, str]) -> ET.Element:
        """Make a rate-limited request to the ArXiv OAI-PMH API.

        Args:
            params (Dict[str, str]): Query parameters for the request.

        Returns:
            ET.Element: Parsed XML response.

        Raises:
            TimeoutError: If the aggregate timeout is exceeded.
            RuntimeError: If the request fails for other reasons.
        """
        start, attempt = time.time(), 0
        self._debug_log(f"Starting request with params: {params}")

        while True:
            elapsed = time.time() - start
            if elapsed > self.timeout:
                self._debug_log(f"Request timeout exceeded after {elapsed:.1f}s (limit: {self.timeout}s)")
                raise TimeoutError("Aggregate timeout exceeded")

            self._debug_log(f"Making request attempt {attempt + 1} to {self._current_url}")
            self._throttle()

            try:
                request_timeout = min(180, self.timeout)
                self._debug_log(f"Making HTTP request to {self._current_url} with {request_timeout}s timeout")
                resp = self._session.get(self._current_url, params=params, timeout=request_timeout)
                self._debug_log(f"Response received: status={resp.status_code}, content_length={len(resp.content)}")

                if resp.status_code == 503:
                    retry_hdr = resp.headers.get("Retry-After")
                    hdr_delay = float(retry_hdr) if retry_hdr and retry_hdr.isdigit() else 0
                    backoff = self._exp_backoff(attempt)
                    extra = max(hdr_delay, backoff)

                    self._debug_log(f"503 Service Unavailable - retry_after_header={retry_hdr}, calculated_delay={extra:.1f}s")
                    self._log(
                        f"503 → retry {attempt+1} after {extra:.1f}s "
                        f"(hdr={hdr_delay:.0f}, backoff={backoff:.1f})"
                    )
                    self._throttle(extra)
                    attempt += 1
                    continue

                resp.raise_for_status()
                self._debug_log(f"Request successful after {time.time() - start:.1f}s")
                return ET.fromstring(resp.content)

            except requests.RequestException as exc:
                self._debug_log(f"Request failed: {exc}")
                
                # Check if this is a connection/timeout issue that might benefit from fallback URL
                is_connection_error = any(keyword in str(exc).lower() for keyword in 
                                        ['timeout', 'connection', 'unreachable', 'refused', 'reset'])
                
                if is_connection_error:
                    self._debug_log(f"Connection issue detected: {exc}")
                    
                    # Try fallback URL first if available
                    if self._try_next_url():
                        self._debug_log("Retrying with fallback URL...")
                        attempt = 0  # Reset attempt counter for new URL
                        continue
                    
                    # If no fallback URLs, try normal retry logic
                    backoff = self._exp_backoff(attempt)
                    self._debug_log(f"Request timeout - retrying after {backoff:.1f}s (attempt {attempt + 1})")
                    self._log(f"Request timeout → retry {attempt+1} after {backoff:.1f}s")
                    self._throttle(backoff)
                    attempt += 1
                    if attempt < 3:  # Allow up to 3 timeout retries
                        continue
                        
                raise RuntimeError(f"OAI-PMH request failed after {attempt + 1} attempts: {exc}") from exc

    def _parse_record(self, rec_xml: ET.Element) -> Dict[str, Any]:
        """Parse a single record from XML.

        Args:
            rec_xml (ET.Element): XML element containing a single record.

        Returns:
            Dict[str, Any]: Parsed record as a dictionary, or empty dict if malformed.
        """
        try:
            meta = rec_xml.find(_OAI_NS + "metadata").find(_ARXIV_NS + "arXiv")
            if meta is None:
                self._debug_log("Record metadata not found - skipping malformed record")
                return {}
            
            parsed = ArxivRecord(meta).model_dump()
            self._debug_log(f"Parsed record: id={parsed.get('id', 'unknown')}, title={parsed.get('title', 'unknown')[:50]}...")
            return parsed
        except Exception as exc:
            self._debug_log(f"Failed to parse record: {exc}")
            return {}

    # ------------------------------------------------------------------ date filter
    def _created_in_range(self, created_str: str) -> bool:
        """Return ``True`` if the paper's *creation* date lies within the user-specified window."""
        try:
            created = datetime.datetime.strptime(created_str, "%Y-%m-%d").date()
            start   = datetime.datetime.strptime(self.date_from, "%Y-%m-%d").date()
            end     = datetime.datetime.strptime(self.date_until, "%Y-%m-%d").date()
            in_range = start <= created <= end
            self._debug_log(f"Date check: created={created_str}, range=[{self.date_from}, {self.date_until}], in_range={in_range}")
            return in_range
        except Exception as exc:
            # Malformed date? Treat as out‑of‑range so it gets skipped
            self._debug_log(f"Invalid date format '{created_str}': {exc} - treating as out of range")
            return False

    def harvest(self) -> List[Dict[str, Any]]:
        """Download and parse records from ArXiv.

        Returns:
            List[Dict[str, Any]]: List of parsed records.

        Raises:
            RuntimeError: If the OAI-PMH API returns an error.
        """
        self._debug_log("Starting harvest operation")
        self._records.clear()
        
        # Check if ArXiv service is healthy before starting
        # Allow skipping health check with environment variable for when service is slow but working
        skip_health_check = os.getenv("SKIP_HEALTH_CHECK", "").lower() == "true"
        
        if skip_health_check:
            self._debug_log("Skipping health check (SKIP_HEALTH_CHECK=true)")
        else:
            if not self.check_service_health():
                self._debug_log("Health check failed - you can bypass this with SKIP_HEALTH_CHECK=true if you think the service is working but slow")
                raise RuntimeError(
                    "ArXiv OAI-PMH ListRecords service appears to be down or unresponsive. "
                    "Please try again later or check ArXiv status at https://status.arxiv.org/. "
                    "If you believe the service is working but slow, set SKIP_HEALTH_CHECK=true"
                )

        params = {
            "verb": "ListRecords",
            "metadataPrefix": "arXiv",
            "from": self.date_from,
            "until": self.date_until,
        }
        # Only add set parameter if category is specified
        if self.set is not None:
            params["set"] = self.set
        self._debug_log(f"Initial harvest parameters: {params}")

        page_count = 0
        while True:
            page_count += 1
            self._debug_log(f"Processing page {page_count}")
            
            root = self._request(params)
            
            if self.verbose and not hasattr(self, "_total_records"):
                total = None
                try:
                    token_elem = root.find(_OAI_NS + "ListRecords").find(_OAI_NS + "resumptionToken")
                    if token_elem is not None and token_elem.get("completeListSize"):
                        total = int(token_elem.get("completeListSize"))
                    else:
                        total = len(root.findall(_OAI_NS + "ListRecords/" + _OAI_NS + "record"))
                except Exception:
                    total = None
                if total is not None:
                    if self.max_results:
                        total = min(total, self.max_results)
                    self._log(f"Total records available in range: {total}")
                    self._debug_log(f"Total records count determined: {total}")
                else:
                    self._log("Could not determine total record count; proceeding...")
                    self._debug_log("Could not determine total record count from response")
                self._total_records = total  # remember so we don't print again
                
            err = root.find(_OAI_NS + "error")
            if err is not None:
                error_code = err.attrib.get('code')
                error_text = err.text.strip() if err.text else 'No error text'
                self._debug_log(f"OAI-PMH API returned error: code={error_code}, text={error_text}")
                raise RuntimeError(
                    f"OAI-PMH error {error_code}: {error_text}"
                )

            records_in_page = root.findall(_OAI_NS + "ListRecords/" + _OAI_NS + "record")
            self._debug_log(f"Found {len(records_in_page)} records in page {page_count}")
            
            records_processed = 0
            records_filtered_subcategory = 0
            records_filtered_date = 0
            records_accepted = 0

            for rec in records_in_page:
                records_processed += 1
                parsed = self._parse_record(rec)
                
                if not parsed:  # Skip empty/malformed records
                    continue
                    
                # Skip records that do not match requested sub‑categories
                if (
                    self.subcategories
                    and not any(sub in parsed["categories"].lower() for sub in self.subcategories)
                ):
                    records_filtered_subcategory += 1
                    self._debug_log(f"Filtered by subcategory: {parsed['categories']} not in {self.subcategories}")
                    continue
                    
                # Skip records whose *creation* date is outside the requested range
                if not self._created_in_range(parsed["created"]):
                    records_filtered_date += 1
                    continue
                    
                if parsed:
                    records_accepted += 1
                    self._records.append(parsed)
                    self._debug_log(f"Accepted record {len(self._records)}: {parsed['id']}")
                    
                    if self.max_results and len(self._records) >= self.max_results:
                        self._log("Reached max_results limit; stopping.")
                        self._debug_log(f"Stopping at max_results limit: {self.max_results}")
                        return self._records

            self._debug_log(f"Page {page_count} summary: processed={records_processed}, "
                          f"filtered_subcategory={records_filtered_subcategory}, "
                          f"filtered_date={records_filtered_date}, accepted={records_accepted}")

            token = root.find(
                _OAI_NS + "ListRecords/" + _OAI_NS + "resumptionToken"
            )
            if token is None or not token.text:
                self._debug_log("No more pages - harvest complete")
                break

            self._debug_log(f"Found resumption token: {token.text[:50]}...")
            params = {"verb": "ListRecords", "resumptionToken": token.text}

        self._log(f"Harvested {len(self._records)} records")
        self._debug_log(f"Harvest completed: {len(self._records)} total records collected over {page_count} pages")
        return self._records

    def to_dataframe(self):
        """Convert harvested records to a pandas DataFrame.

        Returns:
            pandas.DataFrame: DataFrame containing all harvested records.

        Raises:
            RuntimeError: If pandas is not installed.
        """
        if "pd" not in globals() or pd is None:  # type: ignore
            raise RuntimeError("pandas is not installed (`pip install pandas`)")
        if not self._records:
            self.harvest()
        return pd.DataFrame(self._records)
