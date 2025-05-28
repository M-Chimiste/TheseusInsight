from __future__ import annotations

# Standard library imports
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
from ..constants import _ARXIV_NS, _BASE_URL, _OAI_NS, _MIN_INTERVAL


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

    def _log(self, msg: str) -> None:
        """Print a message if verbose mode is enabled.

        Args:
            msg (str): Message to print.
        """
        if self.verbose:
            print(msg, flush=True)

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

        while True:
            if time.time() - start > self.timeout:
                raise TimeoutError("Aggregate timeout exceeded")

            self._throttle()

            try:
                resp = self._session.get(_BASE_URL, params=params, timeout=30)

                if resp.status_code == 503:
                    retry_hdr = resp.headers.get("Retry-After")
                    hdr_delay = float(retry_hdr) if retry_hdr and retry_hdr.isdigit() else 0
                    backoff = self._exp_backoff(attempt)
                    extra = max(hdr_delay, backoff)

                    self._log(
                        f"503 → retry {attempt+1} after {extra:.1f}s "
                        f"(hdr={hdr_delay:.0f}, backoff={backoff:.1f})"
                    )
                    self._throttle(extra)
                    attempt += 1
                    continue

                resp.raise_for_status()
                return ET.fromstring(resp.content)

            except requests.RequestException as exc:
                raise RuntimeError(f"OAI-PMH request failed: {exc}") from exc

    @staticmethod
    def _parse_record(rec_xml: ET.Element) -> Dict[str, Any]:
        """Parse a single record from XML.

        Args:
            rec_xml (ET.Element): XML element containing a single record.

        Returns:
            Dict[str, Any]: Parsed record as a dictionary, or empty dict if malformed.
        """
        meta = rec_xml.find(_OAI_NS + "metadata").find(_ARXIV_NS + "arXiv")
        if meta is None:
            return {}
        return ArxivRecord(meta).model_dump()

    # ------------------------------------------------------------------ date filter
    def _created_in_range(self, created_str: str) -> bool:
        """Return ``True`` if the paper's *creation* date lies within the user-specified window."""
        try:
            created = datetime.datetime.strptime(created_str, "%Y-%m-%d").date()
            start   = datetime.datetime.strptime(self.date_from, "%Y-%m-%d").date()
            end     = datetime.datetime.strptime(self.date_until, "%Y-%m-%d").date()
            return start <= created <= end
        except Exception:
            # Malformed date? Treat as out‑of‑range so it gets skipped
            return False

    def harvest(self) -> List[Dict[str, Any]]:
        """Download and parse records from ArXiv.

        Returns:
            List[Dict[str, Any]]: List of parsed records.

        Raises:
            RuntimeError: If the OAI-PMH API returns an error.
        """
        self._records.clear()

        params = {
            "verb": "ListRecords",
            "metadataPrefix": "arXiv",
            "from": self.date_from,
            "until": self.date_until,
            "set": self.set,
        }

        while True:
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
                else:
                    self._log("Could not determine total record count; proceeding...")
                self._total_records = total  # remember so we don't print again
                
            err = root.find(_OAI_NS + "error")
            if err is not None:
                raise RuntimeError(
                    f"OAI-PMH error {err.attrib.get('code')}: {err.text.strip()}"
                )

            for rec in root.findall(_OAI_NS + "ListRecords/" + _OAI_NS + "record"):
                parsed = self._parse_record(rec)
                # Skip records that do not match requested sub‑categories
                if (
                    self.subcategories
                    and not any(sub in parsed["categories"].lower() for sub in self.subcategories)
                ):
                    continue
                # Skip records whose *creation* date is outside the requested range
                if not self._created_in_range(parsed["created"]):
                    continue
                if parsed:
                    self._records.append(parsed)
                    if self.max_results and len(self._records) >= self.max_results:
                        self._log("Reached max_results limit; stopping.")
                        return self._records

            token = root.find(
                _OAI_NS + "ListRecords/" + _OAI_NS + "resumptionToken"
            )
            if token is None or not token.text:
                break

            params = {"verb": "ListRecords", "resumptionToken": token.text}

        self._log(f"Harvested {len(self._records)} records")
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
