"""Stage 5: Assemble the full newsletter (extracted from run_async, B9)."""
import asyncio
from typing import Callable, Optional, Tuple

import json_repair

from ...data_access import NewsletterRepository
from ...data_model.papers import Newsletter
from ...prompt import NEWSLETTER_SYSTEM_PROMPT, NewsletterPromptData, newsletter_intro_prompt
from ...utils import TODAY


async def run(
    ti,
    sections_data,
    start_from: Optional[str],
    progress_callback: Optional[Callable],
) -> Tuple[Optional[str], Optional[dict]]:
    """Generate the intro, join sections, checkpoint + persist the newsletter.

    Returns (newsletter_content, sections_data) — sections_data may have
    been hydrated from its checkpoint on later-stage resume.
    """
    newsletter_content = None

    if progress_callback:
        progress_callback("newsletter", 60, "Starting newsletter content generation")
    if start_from is None or start_from in ['newsletter_sections', 'newsletter_content']:
        newsletter_content = await ti._load_checkpoint_async('newsletter_content')
        if newsletter_content is None:
            if sections_data is None:
                sections_data = await ti._load_checkpoint_async('newsletter_sections')
                if sections_data is None:
                    raise ValueError("No newsletter sections found to build the final newsletter.")

            if ti.verbose:
                print("Building the final newsletter content + intro ...")

            sections = sections_data['sections']

            # Handle case where there are no sections
            if len(sections) == 0:
                newsletter_content = "No new papers found for this newsletter period. No papers met the criteria for inclusion."
                if ti.verbose:
                    print("No sections available - generating empty newsletter message")
            else:
                joined_sections = "\n\n".join(sections)
                intro_prompt = newsletter_intro_prompt(joined_sections)
                messages = [{"role": "user", "content": intro_prompt}]

                # Model call for the newsletter's intro with retry logic
                # Gemini API can throw 504 Deadline Exceeded errors on long requests
                max_retries = 3
                retry_delay = 5  # seconds
                resp = None
                last_error = None

                for attempt in range(max_retries):
                    try:
                        if attempt > 0:
                            if ti.verbose:
                                print(f"Retrying newsletter intro generation (attempt {attempt + 1}/{max_retries}) after {retry_delay}s...")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff

                        if ti.newsletter_intro_inference.provider == "ollama":
                            resp = ti.newsletter_intro_inference.invoke(
                                messages=messages,
                                system_prompt=NEWSLETTER_SYSTEM_PROMPT,
                                schema=NewsletterPromptData
                            )
                        else:
                            resp = ti.newsletter_intro_inference.invoke(
                                messages=messages,
                                system_prompt=NEWSLETTER_SYSTEM_PROMPT
                            )
                        break  # Success, exit retry loop

                    except Exception as invoke_error:
                        last_error = invoke_error
                        error_str = str(invoke_error)
                        # Check if this is a retryable error (timeout, deadline exceeded, etc.)
                        is_retryable = any(term in error_str.lower() for term in
                            ['deadline', 'timeout', '504', '503', '502', 'unavailable', 'overloaded'])

                        if ti.verbose:
                            print(f"Newsletter intro generation failed (attempt {attempt + 1}/{max_retries}): {error_str}")

                        if not is_retryable or attempt == max_retries - 1:
                            # Non-retryable error or last attempt - re-raise
                            raise

                if resp is None:
                    raise last_error or RuntimeError("Newsletter intro generation failed with no response")

                try:
                    resp_json = json_repair.loads(resp)

                    # Ensure resp_json is a dictionary
                    if not isinstance(resp_json, dict):
                        if ti.verbose:
                            print(f"Warning: Newsletter intro expected dict, got {type(resp_json)}")
                            print(f"Raw response: {resp[:200]}...")
                        intro_text = resp
                    else:
                        intro_text = resp_json.get('draft', resp)

                except Exception as json_error:
                    if ti.verbose:
                        print(f"Newsletter intro JSON parsing failed")
                        print(f"Error: {json_error}")
                        print(f"Raw response: {resp[:200]}...")
                    intro_text = resp

                # Final newsletter
                newsletter_content = intro_text + "\n\n" + joined_sections
            await ti._save_checkpoint_async('newsletter_content', newsletter_content)

            # Save to DB
            if ti.db_saving:
                print("Saving newsletter to DB")
                newsletter = Newsletter(
                    content=newsletter_content,
                    start_date=ti.start_date.strftime('%Y-%m-%d'),
                    end_date=ti.end_date.strftime('%Y-%m-%d'),
                    date_sent=TODAY.strftime('%Y-%m-%d')
                )
                NewsletterRepository.insert(newsletter)
    if progress_callback:
        progress_callback("newsletter", 80, "Newsletter content generation complete")

    return newsletter_content, sections_data
