"""Stage 4: Generate newsletter sections from paper PDFs (extracted from run_async, B9)."""
import concurrent.futures as cf
import os
import random
from typing import Callable, Optional

import json_repair
from tqdm import tqdm

from ...constants import INTRO_TEXT
from ...prompt import (
    NEWSLETTER_SYSTEM_PROMPT,
    NewsletterPromptData,
    SYSTEM_CONTENT_EXTRACTION_SUMMARY,
    SummaryPromptData,
    general_summary_prompt,
    newsletter_context_prompt,
)


async def run(
    ti,
    top_n_df,
    start_from: Optional[str],
    progress_callback: Optional[Callable],
):
    """Download PDFs concurrently, extract content, generate sections.

    Returns sections_data ({'sections', 'urls_and_titles'}); checkpoints
    as newsletter_sections.
    """
    sections_data = None

    if progress_callback:
        progress_callback("newsletter", 40, "Starting newsletter sections generation")
    if start_from is None or start_from in ['papers_ranked', 'newsletter_sections']:
        sections_data = await ti._load_checkpoint_async('newsletter_sections')
        if sections_data is None:
            if top_n_df is None:
                top_n_df = await ti._load_checkpoint_async('papers_ranked')
                if top_n_df is None:
                    raise ValueError("No ranked papers found to generate newsletter sections.")

            # Check if we have any papers to process
            if len(top_n_df) == 0:
                if ti.verbose:
                    print("No papers available for newsletter generation (none met criteria)")
                sections_data = {
                    'sections': [],
                    'urls_and_titles': []
                }
                await ti._save_checkpoint_async('newsletter_sections', sections_data)
            else:
                if ti.verbose:
                    print("Generating newsletter sections (paper-by-paper) ...")

                sections = []
                urls_and_titles = []
                successful_sections = 0
                target_sections = ti.top_n
                papers_processed = 0
                candidate_rows = [row.to_dict() for _, row in top_n_df.iterrows()]

                if ti.verbose:
                    print(f"Processing papers to generate {target_sections} newsletter sections...")
                    print(f"Available papers: {len(top_n_df)}")
                    print(
                        f"✅ Docling -> MarkItDown parser fallback enabled "
                        f"(parse timeout: {ti.pdf_conversion_timeout_sec}s, "
                        f"download workers: {ti.pdf_download_max_workers})"
                    )

                with tqdm(total=len(candidate_rows), desc="Sections") as section_progress:
                    download_executor = cf.ThreadPoolExecutor(
                        max_workers=min(ti.pdf_download_max_workers, len(candidate_rows))
                    )
                    download_futures: dict[cf.Future, dict] = {}
                    processed_futures = set()
                    next_candidate_index = 0

                    def submit_next_download():
                        nonlocal next_candidate_index
                        if next_candidate_index >= len(candidate_rows):
                            return
                        row = candidate_rows[next_candidate_index]
                        next_candidate_index += 1
                        future = download_executor.submit(ti._download_pdf_to_temp_file, row['pdf_url'])
                        download_futures[future] = row

                    try:
                        for _ in range(min(ti.pdf_download_max_workers, len(candidate_rows))):
                            submit_next_download()

                        while download_futures and successful_sections < target_sections:
                            done, _ = cf.wait(
                                list(download_futures.keys()),
                                return_when=cf.FIRST_COMPLETED,
                            )

                            for future in done:
                                if successful_sections >= target_sections:
                                    break
                                row = download_futures.pop(future)
                                processed_futures.add(future)
                                papers_processed += 1
                                intro_text = random.choice(INTRO_TEXT)
                                temp_pdf_path = None
                                markdown = None
                                pdf_conversion_failed = False

                                try:
                                    temp_pdf_path = future.result()
                                    if ti.verbose:
                                        print(f"Converting PDF {papers_processed}/{len(candidate_rows)}: {row['title'][:50]}...")
                                    markdown = ti._parse_downloaded_pdf_to_markdown(temp_pdf_path, row['pdf_url'])
                                    if ti.verbose:
                                        print("✅ PDF conversion successful")
                                except Exception as pdf_error:
                                    pdf_conversion_failed = True
                                    if ti.verbose:
                                        print(f"❌ PDF conversion error for {row['title']}: {pdf_error}")
                                        print(f"   PDF URL: {row['pdf_url']}")
                                        print("   Skipping this paper and trying next one...")
                                finally:
                                    if temp_pdf_path and os.path.exists(temp_pdf_path):
                                        try:
                                            os.unlink(temp_pdf_path)
                                        except OSError:
                                            if ti.verbose:
                                                print(f"Warning: Failed to remove temporary PDF: {temp_pdf_path}")

                                if pdf_conversion_failed:
                                    if ti.verbose:
                                        print(
                                            f"📝 Skipped paper {papers_processed} - "
                                            f"{successful_sections}/{target_sections} sections completed"
                                        )
                                    section_progress.update(1)
                                    submit_next_download()
                                    continue

                                # Summarize the PDF content (or abstract if PDF failed)
                                messages = [{"role": "user", "content": general_summary_prompt(markdown)}]

                                if ti.content_extraction_inference.provider == "ollama":
                                    resp = ti.content_extraction_inference.invoke(
                                        messages=messages,
                                        system_prompt=SYSTEM_CONTENT_EXTRACTION_SUMMARY,
                                        schema=SummaryPromptData
                                    )
                                else:
                                    resp = ti.content_extraction_inference.invoke(
                                        messages=messages,
                                        system_prompt=SYSTEM_CONTENT_EXTRACTION_SUMMARY
                                    )

                                # Parse JSON response with error handling
                                try:
                                    resp_json = json_repair.loads(resp)

                                    # Ensure resp_json is a dictionary
                                    if not isinstance(resp_json, dict):
                                        if ti.verbose:
                                            print(f"Warning: Content extraction expected dict, got {type(resp_json)}")
                                            print(f"Raw response: {resp[:200]}...")
                                        # Fallback: use the raw response
                                        summarized_paper = resp
                                    else:
                                        # Extract content from JSON response
                                        summarized_paper = resp_json.get('content', resp)

                                except Exception as json_error:
                                    if ti.verbose:
                                        print(f"Content extraction JSON parsing failed for paper: {row['title']}")
                                        print(f"Error: {json_error}")
                                        print(f"Raw response: {resp[:200]}...")
                                    # Fallback: use the raw response
                                    summarized_paper = resp

                                # Now produce the "newsletter section" for that paper
                                context = (
                                    f"Title: {row['title']}\n"
                                    f"Abstract: {row['abstract']}\n"
                                    f"Rationale: {row['rationale']}\n"
                                    f"Summary: {summarized_paper}"
                                )
                                messages = [
                                    {"role": "user", 
                                     "content": newsletter_context_prompt(ti.research_interests, context, intro_text)}
                                ]

                                if ti.newsletter_sections_inference.provider == "ollama":
                                    resp = ti.newsletter_sections_inference.invoke(
                                        messages=messages,
                                        system_prompt=NEWSLETTER_SYSTEM_PROMPT,
                                        schema=NewsletterPromptData
                                    )
                                else:
                                    resp = ti.newsletter_sections_inference.invoke(
                                        messages=messages,
                                        system_prompt=NEWSLETTER_SYSTEM_PROMPT
                                    )

                                # Parse JSON response with error handling
                                try:
                                    resp_json = json_repair.loads(resp)

                                    # Ensure resp_json is a dictionary
                                    if not isinstance(resp_json, dict):
                                        if ti.verbose:
                                            print(f"Warning: Expected dict from JSON parsing, got {type(resp_json)}")
                                            print(f"Raw response: {resp[:200]}...")
                                        # Fallback: use the raw response as the draft
                                        draft = f"## {row['title']}\n\n{resp}"
                                    else:
                                        # Extract draft from JSON response
                                        draft_content = resp_json.get('draft', resp)
                                        draft = f"## {row['title']}\n\n{draft_content}"

                                except Exception as json_error:
                                    if ti.verbose:
                                        print(f"JSON parsing failed for paper: {row['title']}")
                                        print(f"Error: {json_error}")
                                        print(f"Raw response: {resp[:200]}...")
                                    # Fallback: use the raw response as the draft
                                    draft = f"## {row['title']}\n\n{resp}"

                                sections.append(draft)
                                urls_and_titles.append(f"{row['title']}: {row['pdf_url']}")
                                successful_sections += 1

                                if ti.verbose:
                                    print(
                                        f"✅ Successfully processed paper {papers_processed} - "
                                        f"{successful_sections}/{target_sections} sections completed"
                                    )

                                section_progress.update(1)

                                if successful_sections < target_sections:
                                    submit_next_download()

                                if successful_sections >= target_sections and ti.verbose:
                                    print(f"✅ Reached target of {target_sections} sections, stopping")

                    finally:
                        download_executor.shutdown(wait=False, cancel_futures=True)

                        for future, row in download_futures.items():
                            if future.cancel():
                                continue
                            if future.done():
                                try:
                                    temp_pdf_path = future.result()
                                except Exception:
                                    continue
                                if temp_pdf_path and os.path.exists(temp_pdf_path):
                                    try:
                                        os.unlink(temp_pdf_path)
                                    except OSError:
                                        if ti.verbose:
                                            print(f"Warning: Failed to remove temporary PDF: {temp_pdf_path}")

                # Final summary
                if ti.verbose:
                    print(f"\n📊 Newsletter section generation summary:")
                    print(f"   Target sections: {target_sections}")
                    print(f"   Successful sections: {successful_sections}")
                    print(f"   Papers processed: {papers_processed}")
                    print(f"   Papers available: {len(top_n_df)}")
                    if successful_sections < target_sections:
                        print(f"   ⚠️ Only generated {successful_sections}/{target_sections} sections due to PDF conversion failures")
                    else:
                        print(f"   ✅ Successfully generated all {successful_sections} target sections")

                sections_data = {
                    'sections': sections,
                    'urls_and_titles': urls_and_titles
                }
                await ti._save_checkpoint_async('newsletter_sections', sections_data)
    if progress_callback:
        progress_callback("newsletter", 50, "Newsletter sections generation complete")


    return sections_data
