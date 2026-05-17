from __future__ import annotations

import datetime
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import requests


class ArxivApiHarvester:
    """Harvester that pulls ArXiv papers via the public REST API.

    Used as a fallback path when OAI-PMH is unavailable or returning errors.
    Mirrors the public surface of ``ArxivOAIHarvester`` so it can be swapped
    into ``UnifiedArxivHarvester`` without touching downstream code.
    """

    BASE_URL = "http://export.arxiv.org/api/query"
    PAGE_SIZE = 2000  # ArXiv API hard cap per request
    REQUEST_INTERVAL = 3.0  # ArXiv guidance: ≥3 s between requests

    NS = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
        "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
    }

    _ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})")

    def __init__(
        self,
        category: str,
        date_from: str,
        date_until: str,
        *,
        subcategories: Optional[List[str]] = None,
        max_results: Optional[int] = None,
        timeout: int = 300,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        verbose: bool = False,
        session: Optional[requests.Session] = None,
    ):
        self.category = category
        self.date_from = date_from
        self.date_until = date_until
        self.subcategories = [s.lower() for s in subcategories] if subcategories else None
        self.max_results = max_results
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.verbose = verbose

        self._session = session or requests.Session()
        self._records: List[Dict[str, Any]] = []
        self._last_call = 0.0
        self._lock = threading.Lock()

        self._debug_mode = os.getenv("DEBUG", "").lower() == "true"
        if self._debug_mode:
            self._debug_log(
                f"Initialized ArxivApiHarvester: category={category}, "
                f"date_from={date_from}, date_until={date_until}, "
                f"subcategories={self.subcategories}, max_results={max_results}"
            )

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)

    def _debug_log(self, msg: str) -> None:
        if self._debug_mode:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[API DEBUG {timestamp}] {msg}", flush=True)

    def _throttle(self) -> None:
        with self._lock:
            wait = max(0.0, self.REQUEST_INTERVAL - (time.time() - self._last_call))
            if wait:
                self._debug_log(f"Throttling request - waiting {wait:.2f}s")
                time.sleep(wait)
            self._last_call = time.time()

    def _build_query(self) -> str:
        if self.subcategories:
            cat_clause = " OR ".join(f"cat:{sub}" for sub in self.subcategories)
            cat_clause = f"({cat_clause})"
        elif self.category:
            cat_clause = f"cat:{self.category}.*"
        else:
            raise ValueError("Either category or subcategories must be provided")

        date_from = self.date_from.replace("-", "")
        date_until = self.date_until.replace("-", "")
        date_clause = f"submittedDate:[{date_from}0000 TO {date_until}2359]"

        return f"{cat_clause} AND {date_clause}"

    def _request(self, params: Dict[str, Any], harvest_start: float) -> ET.Element:
        attempt = 0
        delay = 2.0
        request_timeout = min(60, self.timeout)

        while True:
            elapsed = time.time() - harvest_start
            if elapsed > self.timeout:
                raise TimeoutError(
                    f"Aggregate timeout exceeded ({elapsed:.1f}s > {self.timeout}s)"
                )

            self._throttle()
            try:
                self._debug_log(
                    f"GET {self.BASE_URL} params={params} timeout={request_timeout}s"
                )
                resp = self._session.get(
                    self.BASE_URL, params=params, timeout=request_timeout
                )
                if resp.status_code == 429:
                    raise requests.exceptions.RetryError(
                        "Rate limit reached (429)", response=resp
                    )
                resp.raise_for_status()
                return ET.fromstring(resp.content)
            except (
                requests.exceptions.RetryError,
                requests.exceptions.RequestException,
                ET.ParseError,
            ) as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise RuntimeError(
                        f"ArXiv REST API request failed after {self.max_retries} retries: {exc}"
                    ) from exc
                self._log(
                    f"Retrying ArXiv API request in {delay:.1f}s "
                    f"(attempt {attempt}/{self.max_retries}): {exc}"
                )
                time.sleep(delay)
                delay *= self.backoff_factor

    @staticmethod
    def _clean_text(text: Optional[str]) -> str:
        if not text:
            return ""
        return re.sub(r"\s+", " ", text).strip()

    def _extract_arxiv_id(self, id_url: str) -> str:
        match = self._ARXIV_ID_RE.search(id_url or "")
        if match:
            return match.group(1)
        # Fallback for older-style IDs (e.g. cs/0501001)
        if id_url and "/abs/" in id_url:
            tail = id_url.split("/abs/")[-1]
            return re.sub(r"v\d+$", "", tail)
        return ""

    def _parse_entry(self, entry: ET.Element) -> Dict[str, Any]:
        id_text = entry.findtext("atom:id", default="", namespaces=self.NS)
        arxiv_id = self._extract_arxiv_id(id_text)

        title = self._clean_text(entry.findtext("atom:title", default="", namespaces=self.NS))
        abstract = self._clean_text(
            entry.findtext("atom:summary", default="", namespaces=self.NS)
        )
        published = entry.findtext("atom:published", default="", namespaces=self.NS)
        updated = entry.findtext("atom:updated", default="", namespaces=self.NS)
        doi = entry.findtext("arxiv:doi", default="", namespaces=self.NS) or ""

        categories = " ".join(
            cat.attrib.get("term", "")
            for cat in entry.findall("atom:category", self.NS)
            if cat.attrib.get("term")
        )

        authors = [
            (author.findtext("atom:name", default="", namespaces=self.NS) or "").strip()
            for author in entry.findall("atom:author", self.NS)
        ]
        authors = [a for a in authors if a]

        return {
            "id": arxiv_id,
            "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else "",
            "title": title,
            "abstract": abstract,
            "categories": categories,
            "created": published[:10],
            "updated": updated[:10],
            "doi": doi,
            "authors": authors,
            "affiliation": [],
        }

    def harvest(self) -> List[Dict[str, Any]]:
        self._records.clear()
        harvest_start = time.time()

        query = self._build_query()
        self._log(f"Searching ArXiv API: {query}")
        self._debug_log(f"Built query: {query}")

        start = 0
        page_num = 0
        total_results: Optional[int] = None

        while True:
            page_num += 1
            page_size = self.PAGE_SIZE
            if self.max_results:
                remaining = self.max_results - len(self._records)
                if remaining <= 0:
                    break
                page_size = min(page_size, remaining)

            params = {
                "search_query": query,
                "start": start,
                "max_results": page_size,
                "sortBy": "submittedDate",
                "sortOrder": "ascending",
            }

            root = self._request(params, harvest_start)

            if total_results is None:
                total_text = root.findtext("opensearch:totalResults", namespaces=self.NS)
                try:
                    total_results = int(total_text) if total_text else None
                except ValueError:
                    total_results = None
                if total_results is not None:
                    capped = min(total_results, self.max_results) if self.max_results else total_results
                    self._log(f"Total records available: {total_results} (will fetch up to {capped})")

            entries = root.findall("atom:entry", self.NS)
            page_count = 0
            for entry in entries:
                parsed = self._parse_entry(entry)
                if not parsed.get("id"):
                    self._debug_log("Skipping entry with no extractable arXiv ID")
                    continue
                self._records.append(parsed)
                page_count += 1
                if self.max_results and len(self._records) >= self.max_results:
                    break

            self._log(
                f"📥 Fetched page {page_num}: {page_count} entries "
                f"({len(self._records)}"
                + (f"/{total_results}" if total_results is not None else "")
                + " total)"
            )

            if self.max_results and len(self._records) >= self.max_results:
                self._debug_log(f"Reached max_results limit: {self.max_results}")
                break
            if total_results is not None and len(self._records) >= total_results:
                break
            if len(entries) < page_size:
                break

            start += page_size

        self._log(f"✅ ArXiv REST API harvest complete: {len(self._records)} records")
        return self._records

    def to_dataframe(self):
        try:
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError("pandas is not installed (`pip install pandas`)") from exc
        return pd.DataFrame(self._records)
