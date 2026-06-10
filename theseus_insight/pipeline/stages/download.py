"""Stage 1: Download papers from arXiv (extracted from run_async, B9)."""
from typing import Callable, Optional, Tuple

import pandas as pd

from ...data_processing.arxiv import ArxivDataProcessor


async def run(
    ti,
    start_from: Optional[str],
    progress_callback: Optional[Callable],
) -> Tuple[Optional[pd.DataFrame], bool]:
    """Download papers or resume from the 'papers_downloaded' checkpoint.

    Returns (data_df, exit_early). exit_early=True means no papers were
    found and the pipeline should stop (the no-papers notification has
    already been handled).
    """
    data_df = None

    if progress_callback:
        progress_callback("download", 0, "Starting paper download", {"papers_discovered": 0})

    if not start_from:
        # no stage specified, do we have an existing checkpoint for 'papers_downloaded'?
        data_df = ti._load_checkpoint('papers_downloaded')
        if ti.verbose:
            if data_df is None:
                print("No 'papers_downloaded' checkpoint. Starting fresh: downloading papers.")
            else:
                print(f"⚠️ DEBUG: Loaded 'papers_downloaded' checkpoint with {len(data_df) if hasattr(data_df, '__len__') else 'unknown'} papers")

        if data_df is None:
            process_data = ArxivDataProcessor(start_date=ti.start_date, end_date=ti.end_date)
            data_df = process_data.download_and_process_data()

            # Check if no papers were found and handle gracefully
            if data_df.empty:
                ti._handle_no_papers_found()
                return None, True  # Exit early since there's nothing to process

            ti._save_checkpoint('papers_downloaded', data_df)
    else:
        # If we have a forced stage, see if the user wants to skip some
        if start_from == 'papers_downloaded':
            data_df = ti._load_checkpoint('papers_downloaded')
            if data_df is None:
                if ti.verbose:
                    print("Forcing download stage.")
                process_data = ArxivDataProcessor(start_date=ti.start_date, end_date=ti.end_date)
                data_df = process_data.download_and_process_data()

                # Check if no papers were found and handle gracefully
                if data_df.empty:
                    ti._handle_no_papers_found()
                    return None, True  # Exit early since there's nothing to process

                ti._save_checkpoint('papers_downloaded', data_df)

    if progress_callback:
        progress_callback("download", 10, "Paper download complete", {"papers_discovered": len(data_df)})

    return data_df, False
