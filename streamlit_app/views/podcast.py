import streamlit as st
import os
from datetime import datetime
from api_utils import make_api_request, APIError
from typing import Dict, Any, List
import pandas as pd
import re
from streamlit_app import api_client # Assuming api_client is in streamlit_app directory
from streamlit_app.views.settings import render_model_config_ui # Re-using the helper

# Default values from NeonWaveVisualizer (approximated or common ones)
DEFAULT_VIS_PARAMS = {
    "matrix_count": 8,
    "matrix_head_color": "#00FF00",
    "matrix_tail_color": "#00B000",
    "matrix_char_size": 24,
    "head_step_time": 0.3,
    "random_x_jitter": 3.0,
    "fade_time": 3.0,
    "head_glow_passes": 3,
    "head_glow_alpha_decay": 50,
    "head_spawn_delay_range_min": 2.0,
    "head_spawn_delay_range_max": 5.0,
    "head_saw_period": 1.5,
    "line_width": 3,
    "wave_color": "#00FF80",
    "trail_color_1": "#00C060",
    "trail_color_2": "#008040",
    "trail_color_3": "#004020",
    "glow_passes": 3,
    "glow_alpha_decay": 40,
    "font_path": "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "resolution_width": 1280,
    "resolution_height": 720,
    "fps": 30
}

def initialize_podcast_creator_session_state():
    if "pc_input_type" not in st.session_state:
        st.session_state.pc_input_type = "URLs"
    if "pc_uploaded_pdfs" not in st.session_state:
        st.session_state.pc_uploaded_pdfs = []
    if "pc_urls_text" not in st.session_state:
        st.session_state.pc_urls_text = ""
    if "pc_create_visualization" not in st.session_state:
        st.session_state.pc_create_visualization = False

    if "pc_orchestration_config" not in st.session_state:
        st.session_state.pc_orchestration_config = None
    if "pc_podcast_model_config_temp" not in st.session_state:
        st.session_state.pc_podcast_model_config_temp = {}
    if "pc_tts_model_config_temp" not in st.session_state:
        st.session_state.pc_tts_model_config_temp = {}
    if "pc_available_providers" not in st.session_state:
        st.session_state.pc_available_providers = []

    # Initialize visualization parameters in session state
    for key, value in DEFAULT_VIS_PARAMS.items():
        session_key = f"pc_vis_{key}"
        if session_key not in st.session_state:
            st.session_state[session_key] = value

    if not st.session_state.pc_orchestration_config:
        try:
            st.session_state.pc_orchestration_config = api_client.get_orchestration_config()
            # Initialize temp models from the main orchestration config if not already set
            if not st.session_state.pc_podcast_model_config_temp and st.session_state.pc_orchestration_config.get("podcast_model"):
                st.session_state.pc_podcast_model_config_temp = st.session_state.pc_orchestration_config["podcast_model"].copy()
            if not st.session_state.pc_tts_model_config_temp and st.session_state.pc_orchestration_config.get("tts_model"):
                st.session_state.pc_tts_model_config_temp = st.session_state.pc_orchestration_config["tts_model"].copy()
            
            # Fetch available providers if not already loaded
            if not st.session_state.pc_available_providers:
                providers_data = api_client.get_model_providers()
                st.session_state.pc_available_providers = [p["name"] for p in providers_data]

        except api_client.APIClientError as e:
            st.error(f"Error loading initial model configurations: {str(e)}")
            # Provide default structures if API fails, to prevent crashes
            if not st.session_state.pc_podcast_model_config_temp:
                 st.session_state.pc_podcast_model_config_temp = DEFAULT_VIS_PARAMS.get("podcast_model", {})
            if not st.session_state.pc_tts_model_config_temp:
                 st.session_state.pc_tts_model_config_temp = DEFAULT_VIS_PARAMS.get("tts_model", {})


def show_podcast_creator_page():
    st.title("🎙️ Podcast Creator")
    initialize_podcast_creator_session_state()

    st.subheader("1. Content Sources")
    st.session_state.pc_input_type = st.radio(
        "Choose input type:",
        ("URLs", "PDF Upload"),
        key="pc_input_type_radio"
    )

    if st.session_state.pc_input_type == "PDF Upload":
        st.session_state.pc_uploaded_pdfs = st.file_uploader(
            "Upload PDF files", type="pdf", accept_multiple_files=True, key="pc_pdf_uploader"
        )
        if st.session_state.pc_uploaded_pdfs:
            st.write(f"{len(st.session_state.pc_uploaded_pdfs)} PDF(s) selected.")
    else:
        st.session_state.pc_urls_text = st.text_area(
            "Enter URLs (one per line or comma-separated)", height=150, key="pc_url_input"
        )
        if st.session_state.pc_urls_text:
            urls = re.split(r'[\n,]+', st.session_state.pc_urls_text)
            st.write(f"{len([url for url in urls if url.strip()])} URL(s) detected.")

    st.subheader("2. Model Configuration")
    if st.session_state.pc_orchestration_config:
        with st.expander("Podcast & TTS Model Settings", expanded=False):
            # Podcast Model
            st.markdown("**Podcast Generation Model**")
            if st.session_state.pc_podcast_model_config_temp:
                 new_podcast_config = render_model_config_ui(
                    model_key="podcast_generation_model", 
                    config_data=st.session_state.pc_podcast_model_config_temp, 
                    available_providers=st.session_state.get("pc_available_providers", ["ollama", "gemini", "openai", "anthropic"]),
                    form_key_prefix="pc_podcast_model"
                )
                 if new_podcast_config != st.session_state.pc_podcast_model_config_temp:
                    st.session_state.pc_podcast_model_config_temp = new_podcast_config
            else:
                st.warning("Podcast model configuration not loaded.")
            
            # TTS Model
            st.markdown("**Text-to-Speech (TTS) Model**")
            tts_config = st.session_state.pc_tts_model_config_temp
            if tts_config:
                tts_config["tts_provider"] = st.selectbox("TTS Provider", ["openai", "google", "elevenlabs", "kokoro"], index=["openai", "google", "elevenlabs", "kokoro"].index(tts_config.get("tts_provider", "openai")), key="pc_tts_provider")
                tts_config["tts_model_name"] = st.text_input("TTS Model Name", value=tts_config.get("tts_model_name", "tts-1"), key="pc_tts_model_name")
                # For simplicity, assuming 2 speakers for now as per current TheseusInsight class
                tts_config["speaker_1_voice"] = st.text_input("Speaker 1 Voice ID/Name", value=tts_config.get("speaker_1_voice", "sage"), key="pc_tts_s1_voice")
                tts_config["speaker_1_speed"] = st.number_input("Speaker 1 Speed", min_value=0.5, max_value=3.5, value=float(tts_config.get("speaker_1_speed", 1.0)), step=0.1, key="pc_tts_s1_speed")
                tts_config["speaker_2_voice"] = st.text_input("Speaker 2 Voice ID/Name", value=tts_config.get("speaker_2_voice", "ash"), key="pc_tts_s2_voice")
                tts_config["speaker_2_speed"] = st.number_input("Speaker 2 Speed", min_value=0.5, max_value=3.5, value=float(tts_config.get("speaker_2_speed", 1.0)), step=0.1, key="pc_tts_s2_speed")
            else:
                st.warning("TTS model configuration not loaded.")

            if st.button("Save Model Changes to Main Settings", key="pc_save_model_changes"):
                try:
                    updated_orchestration_config = st.session_state.pc_orchestration_config.copy()
                    updated_orchestration_config["podcast_model"] = st.session_state.pc_podcast_model_config_temp
                    updated_orchestration_config["tts_model"] = st.session_state.pc_tts_model_config_temp
                    api_client.update_orchestration_config(updated_orchestration_config)
                    st.session_state.pc_orchestration_config = updated_orchestration_config # Update local session state
                    st.success("Model configurations saved successfully to main settings!")
                except api_client.APIClientError as e:
                    st.error(f"Failed to save model configurations: {str(e)}")
    else:
        st.warning("Orchestration configuration could not be loaded. Model settings are unavailable.")


    st.subheader("3. Intro Music (Optional)")
    st.file_uploader("Upload Intro Music (MP3)", type="mp3", key="pc_intro_music_file")

    st.subheader("4. Visualization (Optional)")
    st.session_state.pc_create_visualization = st.checkbox("Create Video Visualization?", key="pc_viz_checkbox")

    if st.session_state.pc_create_visualization:
        with st.expander("Visualization Settings", expanded=True):
            st.info("Adjust parameters for the video visualization. Colors can be hex codes (e.g., #FF0000).")
            c1, c2 = st.columns(2)
            with c1:
                st.color_picker("Matrix Head Color", value=st.session_state.pc_vis_matrix_head_color, key="pc_vis_mat_head_color")
                st.number_input("Matrix Char Size", min_value=10, max_value=50, value=st.session_state.pc_vis_matrix_char_size, step=1, key="pc_vis_mat_char_size")
                st.number_input("Head Step Time (s)", min_value=0.05, max_value=1.0, value=st.session_state.pc_vis_head_step_time, step=0.01, key="pc_vis_head_step")
                st.number_input("Fade Time (s)", min_value=0.5, max_value=10.0, value=st.session_state.pc_vis_fade_time, step=0.1, key="pc_vis_fade_time")
                st.number_input("Head Glow Alpha Decay", min_value=0, max_value=255, value=st.session_state.pc_vis_head_glow_alpha_decay, step=5, key="pc_vis_head_glow_decay")
                st.number_input("Head Saw Period (s)", min_value=0.1, max_value=5.0, value=st.session_state.pc_vis_head_saw_period, step=0.1, key="pc_vis_head_saw")
                st.color_picker("Wave Color", value=st.session_state.pc_vis_wave_color, key="pc_vis_wave_color")
                st.number_input("Glow Alpha Decay", min_value=0, max_value=255, value=st.session_state.pc_vis_glow_alpha_decay, step=5, key="pc_vis_glow_decay")
                st.number_input("FPS", min_value=10, max_value=60, value=st.session_state.pc_vis_fps, step=1, key="pc_vis_fps")
                st.number_input("Resolution Width (px)", min_value=640, max_value=3840, value=st.session_state.pc_vis_resolution_width, step=10, key="pc_vis_res_w")

            with c2:
                st.color_picker("Matrix Tail Color", value=st.session_state.pc_vis_matrix_tail_color, key="pc_vis_mat_tail_color")
                st.number_input("Matrix Count", min_value=1, max_value=50, value=st.session_state.pc_vis_matrix_count, step=1, key="pc_vis_mat_count")
                st.number_input("Random X Jitter (px)", min_value=0.0, max_value=10.0, value=st.session_state.pc_vis_random_x_jitter, step=0.1, key="pc_vis_x_jitter")
                st.number_input("Head Glow Passes", min_value=1, max_value=10, value=st.session_state.pc_vis_head_glow_passes, step=1, key="pc_vis_head_glow_passes")
                st.markdown("Head Spawn Delay Range (min, max seconds)")
                hr1, hr2 = st.columns(2)
                hr1.number_input("Min", min_value=0.1, max_value=10.0, value=st.session_state.pc_vis_head_spawn_delay_range_min, step=0.1, key="pc_vis_h_spawn_min")
                hr2.number_input("Max", min_value=0.1, max_value=10.0, value=st.session_state.pc_vis_head_spawn_delay_range_max, step=0.1, key="pc_vis_h_spawn_max")
                st.number_input("Line Width (px)", min_value=1, max_value=10, value=st.session_state.pc_vis_line_width, step=1, key="pc_vis_line_width")
                st.markdown("**Trail Colors**")
                st.color_picker("Trail Color 1", value=st.session_state.pc_vis_trail_color_1, key="pc_vis_trail_color_1")
                st.color_picker("Trail Color 2", value=st.session_state.pc_vis_trail_color_2, key="pc_vis_trail_color_2")
                st.color_picker("Trail Color 3", value=st.session_state.pc_vis_trail_color_3, key="pc_vis_trail_color_3")
                st.number_input("Glow Passes", min_value=1, max_value=10, value=st.session_state.pc_vis_glow_passes, step=1, key="pc_vis_glow_passes")
                st.text_input("Font Path", value=st.session_state.pc_vis_font_path, key="pc_vis_font_path")
                st.number_input("Resolution Height (px)", min_value=360, max_value=2160, value=st.session_state.pc_vis_resolution_height, step=10, key="pc_vis_res_h")

    st.markdown("---    ")
    if st.button("🚀 Generate Podcast", use_container_width=True, type="primary", key="pc_generate_button"):
        st.info("Podcast generation started... (This will be implemented fully later)")
        # Placeholder for actual generation logic
        # 1. Collect all data from st.session_state
        # 2. Validate inputs (e.g., at least one URL or PDF)
        # 3. Prepare payload for API
        # 4. Call api_client.start_podcast_generation_pipeline(...)
        # 5. Handle task_id and status updates similar to newsletter page

# Remove or comment out the old podcast page if it's being replaced
# def show_podcast_page():
#    st.title("🎙️ Podcast Builder")
# ... (old code)
