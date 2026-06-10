"""Stage 7: Podcast generation/visualization/publish (extracted from run_async, B9)."""
import json
import os
from typing import Callable, Optional

from ...communication import upload_video
from ...data_access import PodcastRepository
from ...data_model.papers import Podcast
from ...utils import TODAY


async def run(
    ti,
    top_n_df,
    sections_data,
    progress_callback: Optional[Callable],
) -> None:
    """Generate podcast audio (+ optional visualization), persist, publish."""
    if progress_callback:
        progress_callback("podcast", 90, "Starting podcast generation")
    if ti.generate_podcast:
        # Part A: Generate Podcast Script + Audio
        podcast_content = await ti._load_checkpoint_async('podcast_script')
        if podcast_content is None:
            # If we haven't built any script yet, let's do it
            if ti.verbose:
                print("Generating podcast script & audio...")

            if top_n_df is None:
                top_n_df = await ti._load_checkpoint_async('papers_ranked')
                if top_n_df is None:
                    raise ValueError("Cannot generate podcast: no ranked papers found.")
            if sections_data is None:
                sections_data = await ti._load_checkpoint_async('newsletter_sections')
                if sections_data is None:
                    raise ValueError("Cannot generate podcast: no newsletter sections found.")

            podcast_content = ti.podcast_generator.generate_podcast(
                pdf_paths=list(top_n_df['pdf_url']),
                output_format=ti.output_format,
                output_dir=ti.output_dir,
                prefix=ti.prefix,
                final_filename=ti.final_filename,
                verbose=ti.verbose,
                visualizer=False  # We'll do visualization in next step
            )
            await ti._save_checkpoint_async('podcast_script', podcast_content)

        # Part B: Visualization (if visualizer=True)
        visualized_podcast = await ti._load_checkpoint_async('podcast_visualized')
        if ti.visualizer and visualized_podcast is None:
            if ti.verbose:
                print("Generating podcast visualization...")

            # We re-run generate_podcast with visualizer=True
            # so it merges the final audio with the animation
            podcast_content = ti.podcast_generator.generate_podcast(
                pdf_paths=list(top_n_df['pdf_url']),
                output_format=ti.output_format,
                output_dir=ti.output_dir,
                prefix=ti.prefix,
                final_filename=ti.final_filename,
                verbose=ti.verbose,
                visualizer=True,
                resolution=ti.resolution,
                fps=ti.fps,
                matrix_count=ti.matrix_count,
                matrix_head_color=ti.matrix_head_color,
                matrix_tail_color=ti.matrix_tail_color,
                matrix_char_size=ti.matrix_char_size,
                head_step_time=ti.head_step_time,
                random_x_jitter=ti.random_x_jitter,
                fade_time=ti.fade_time,
                head_glow_passes=ti.head_glow_passes,
                head_glow_alpha_decay=ti.head_glow_alpha_decay,
                head_spawn_delay_range=ti.head_spawn_delay_range,
                head_saw_period=ti.head_saw_period,
                wave_color=ti.wave_color,
                trail_colors=ti.trail_colors,
                glow_passes=ti.glow_passes,
                glow_alpha_decay=ti.glow_alpha_decay,
                line_width=ti.line_width,
                font_path=ti.font_path
            )
            await ti._save_checkpoint_async('podcast_visualized', podcast_content)

        # Save the final script / transcript in DB and optional JSON
        if podcast_content:
            if ti.save_dialogue:
                if ti.verbose:
                    print("Saving podcast dialogue to JSON...")
                dialogue_path = os.path.join(ti.output_dir, f"{ti.prefix}_dialogue.json")
                with open(dialogue_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "dialogue": podcast_content['dict_transcript'],
                        "description": podcast_content['description']
                    }, f, ensure_ascii=False, indent=2)

            # Insert a record in the DB for the final podcast
            if ti.db_saving:
                podcast = Podcast(
                    title=ti.final_filename,
                    date=TODAY.strftime('%Y-%m-%d'),
                    script=json.dumps(podcast_content['dict_transcript']),
                    description=podcast_content['description']
                )
                PodcastRepository.insert(podcast)

            # Part C: Publish to YouTube if requested
            if ti.publish_podcast:
                video_path = (podcast_content['visualizer_path']
                              if ti.visualizer else
                              podcast_content['final_podcast_path'])
                if ti.verbose:
                    print("Publishing to YouTube, this may take a while...")
                try:
                    upload_video(
                        video_path,
                        title=ti.final_filename,
                        description=podcast_content['description']
                    )
                except Exception as up_e:
                    ti._log_error(500, up_e)
                    raise
    if progress_callback:
        progress_callback("podcast", 100, "Podcast generation complete")
