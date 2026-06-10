"""PDF download + markdown conversion with subprocess timeout isolation.

Extracted from TheseusInsight (B8). The fallback order is a documented
behavior: Docling first, MarkItDown second, skip the paper if both fail.
Workers run in spawn subprocesses so a hung parser can be terminated.
"""
import multiprocessing as mp
import os
import queue
import tempfile
import time
from pathlib import Path

import requests


def markitdown_convert_worker(pdf_path: str, result_queue):
    """Convert a local PDF file to markdown in a subprocess so hangs can be terminated."""
    try:
        import re
        from markitdown import MarkItDown

        converter = MarkItDown(enable_plugins=False)
        result = converter.convert(pdf_path)
        markdown = re.sub(r"\n{2,}", "\n", result.text_content or "").strip()
        if not markdown:
            raise ValueError(f"MarkItDown returned empty content for {pdf_path}")
        result_queue.put(("ok", markdown))
    except Exception as exc:
        result_queue.put(("error", f"{type(exc).__name__}: {exc}"))


def docling_convert_worker(pdf_path: str, result_queue):
    """Convert a local PDF file to markdown with Docling in a subprocess."""
    try:
        from theseus_insight.pdf.processing import DoclingDocProcessor

        processor = DoclingDocProcessor(
            export_tables=False,
            export_figures=False,
            save_text=False,
            remove_md_image_tags=True,
            verbose=False,
        )
        result = processor.process_document(pdf_path)
        markdown = (result.get("processed_data") or "").strip()
        if not markdown:
            raise ValueError(f"Docling returned empty content for {pdf_path}")
        result_queue.put(("ok", markdown))
    except Exception as exc:
        result_queue.put(("error", f"{type(exc).__name__}: {exc}"))


def download_pdf_to_temp_file(pdf_url: str, *, verbose: bool = False) -> str:
    """Download a PDF to a temporary local file with periodic progress logs."""
    temp_pdf_path = None
    downloaded_bytes = 0
    last_log_time = time.time()
    last_logged_bytes = 0
    chunk_size = 256 * 1024

    if verbose:
        print(f"   Downloading PDF from {pdf_url}")

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_pdf_path = temp_file.name

        with requests.Session() as session:
            response = session.get(
                pdf_url,
                timeout=(15, 60),
                stream=True,
                headers={
                    "User-Agent": "TheseusInsight/1.0 PDF fetcher",
                    "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
                },
            )
            response.raise_for_status()

            total_bytes = int(response.headers.get("Content-Length", "0") or 0)

            with open(temp_pdf_path, "wb") as temp_file:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if not chunk:
                        continue

                    temp_file.write(chunk)
                    downloaded_bytes += len(chunk)

                    should_log = (
                        downloaded_bytes - last_logged_bytes >= 5 * 1024 * 1024
                        or time.time() - last_log_time >= 10
                    )
                    if verbose and should_log:
                        downloaded_mb = downloaded_bytes / (1024 * 1024)
                        if total_bytes > 0:
                            total_mb = total_bytes / (1024 * 1024)
                            pct = (downloaded_bytes / total_bytes) * 100
                            print(
                                f"   Downloaded {downloaded_mb:.1f}/{total_mb:.1f} MB "
                                f"({pct:.0f}%)"
                            )
                        else:
                            print(f"   Downloaded {downloaded_mb:.1f} MB")
                        last_log_time = time.time()
                        last_logged_bytes = downloaded_bytes

        if verbose:
            final_mb = downloaded_bytes / (1024 * 1024)
            print(f"   PDF download complete ({final_mb:.1f} MB)")

        return temp_pdf_path

    except Exception:
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            try:
                os.unlink(temp_pdf_path)
            except OSError:
                pass
        raise


def run_pdf_parse_worker(
    worker_target,
    parser_name: str,
    temp_pdf_path: str,
    source_pdf_url: str,
    *,
    timeout_sec: float,
    verbose: bool = False,
) -> str:
    """Run a PDF parser subprocess with a hard timeout and return markdown text."""
    ctx = mp.get_context("spawn")
    result_queue = ctx.Queue(maxsize=1)
    process = ctx.Process(
        target=worker_target,
        args=(temp_pdf_path, result_queue),
        daemon=True,
    )
    if verbose:
        print(
            f"   Starting {parser_name} parse for local file "
            f"{Path(temp_pdf_path).name} "
            f"(source: {source_pdf_url}, timeout: {timeout_sec}s)"
        )
    process.start()
    deadline = time.monotonic() + timeout_sec

    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"{parser_name} parsing exceeded {timeout_sec}s for local file "
                    f"{Path(temp_pdf_path).name} (source: {source_pdf_url})"
                )

            try:
                status, payload = result_queue.get(timeout=min(1.0, remaining))
                break
            except queue.Empty:
                if process.exitcode is not None:
                    raise RuntimeError(
                        "PDF conversion subprocess exited without returning data "
                        f"(exit code: {process.exitcode})"
                    )

        if status == "error":
            raise RuntimeError(payload)

        return payload
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
            if process.is_alive():
                process.kill()
                process.join(timeout=1)
        else:
            process.join(timeout=1)
        result_queue.close()
        result_queue.join_thread()


def pdf_to_markdown(
    temp_pdf_path: str,
    source_pdf_url: str,
    *,
    timeout_sec: float,
    verbose: bool = False,
) -> str:
    """Convert a downloaded local PDF file to markdown using Docling, then MarkItDown as fallback."""
    parser_attempts = (
        ("Docling", docling_convert_worker),
        ("MarkItDown", markitdown_convert_worker),
    )
    parse_errors = []

    for parser_name, worker in parser_attempts:
        try:
            return run_pdf_parse_worker(
                worker_target=worker,
                parser_name=parser_name,
                temp_pdf_path=temp_pdf_path,
                source_pdf_url=source_pdf_url,
                timeout_sec=timeout_sec,
                verbose=verbose,
            )
        except Exception as exc:
            parse_errors.append(f"{parser_name}: {exc}")
            if verbose:
                print(f"   {parser_name} parse failed, trying next parser if available: {exc}")

    raise RuntimeError("All PDF parsers failed. " + " | ".join(parse_errors))
