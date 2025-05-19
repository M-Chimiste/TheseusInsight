import streamlit as st
import os
from datetime import datetime
from api_utils import make_api_request, APIError
from typing import Dict, Any, List, Optional
import pandas as pd
import re
from streamlit_app import api_client # Assuming api_client is in streamlit_app directory
from streamlit_app.views.settings import render_model_config_ui # Re-using the helper
import asyncio # For WebSocket listener
import threading # For WebSocket listener
import websockets # For WebSocket listener
import json # For WebSocket messages

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

    # Session state for podcast generation task tracking
    if "pc_task_id" not in st.session_state:
        st.session_state.pc_task_id = None
    if "pc_status_messages" not in st.session_state:
        st.session_state.pc_status_messages = []
    if "pc_pipeline_running" not in st.session_state:
        st.session_state.pc_pipeline_running = False
    if "pc_pipeline_error" not in st.session_state:
        st.session_state.pc_pipeline_error = None
    if "pc_trigger_rerun_for_status" not in st.session_state: # Used by WebSocket listener to tell main thread to rerun
        st.session_state.pc_trigger_rerun_for_status = False
    if "pc_current_stage" not in st.session_state:
        st.session_state.pc_current_stage = ""
    if "pc_current_progress" not in st.session_state:
        st.session_state.pc_current_progress = 0.0
    if "pc_final_artifact_paths" not in st.session_state: # To store paths from completed task
        st.session_state.pc_final_artifact_paths = None

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
    if st.button("🚀 Generate Podcast", use_container_width=True, type="primary", key="pc_generate_button", disabled=st.session_state.pc_pipeline_running):
        # 1. Validate inputs
        input_type = st.session_state.pc_input_type
        urls_list: Optional[List[str]] = None
        uploaded_pdfs = st.session_state.get("pc_uploaded_pdfs", [])

        if input_type == "URLs":
            raw_urls = st.session_state.get("pc_urls_text", "")
            urls_list = [url.strip() for url in re.split(r'[\n,]+', raw_urls) if url.strip()]
            if not urls_list:
                st.error("Please enter at least one URL.")
                st.stop()
        elif input_type == "PDF Upload" and not uploaded_pdfs:
            st.error("Please upload at least one PDF file.")
            st.stop()

        podcast_model_cfg = st.session_state.get("pc_podcast_model_config_temp", {})
        tts_model_cfg = st.session_state.get("pc_tts_model_config_temp", {})
        if not podcast_model_cfg or not podcast_model_cfg.get("model_name") or \
           not tts_model_cfg or not tts_model_cfg.get("tts_provider"):
            st.error("Podcast or TTS model configuration is incomplete. Please check settings.")
            st.stop()

        intro_music = st.session_state.get("pc_intro_music_file", None)
        create_viz = st.session_state.get("pc_create_visualization", False)
        viz_params_collected: Optional[Dict[str, Any]] = None
        if create_viz:
            viz_params_collected = {}
            for key in DEFAULT_VIS_PARAMS.keys(): # Use keys from DEFAULT_VIS_PARAMS as source of truth for viz param names
                viz_params_collected[key] = st.session_state.get(f"pc_vis_{key}")
        
        # 2. Call API client
        try:
            st.session_state.pc_pipeline_running = True
            st.session_state.pc_task_id = None # Reset previous task id
            st.session_state.pc_status_messages = ["Initiating podcast generation..."]
            st.session_state.pc_pipeline_error = None
            st.session_state.pc_current_stage = "Initiating"
            st.session_state.pc_current_progress = 5.0 # Small progress for initiation
            st.session_state.pc_final_artifact_paths = None
            st.rerun() 

            task_id = api_client.start_podcast_generation_pipeline(
                input_type=input_type,
                urls=urls_list,
                pdf_files=uploaded_pdfs if input_type == "PDF Upload" else None,
                podcast_model_config=podcast_model_cfg,
                tts_model_config=tts_model_cfg,
                intro_music_file=intro_music,
                create_visualization=create_viz,
                visualizer_params=viz_params_collected
            )
            st.session_state.pc_task_id = task_id
            # Don't set pipeline_running to False here, WebSocket will do it.
            
            # Start WebSocket listener in a new thread
            # Ensure API_HOST_URL is accessible for WebSocket connection string construction
            ws_url_base = api_client.API_HOST_URL.replace("http", "ws")
            ws_url = f"{ws_url_base}/ws/podcast/{task_id}"
            
            # Ensure an event loop is running in the main thread if not already
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            listener_thread = threading.Thread(
                target=run_async_in_thread,
                args=(listen_to_task_status_async(ws_url, "pc"), loop),
                daemon=True
            )
            listener_thread.start()
            st.success(f"Podcast generation started. Task ID: {task_id}. Waiting for status updates...")
            # UI will update via rerun triggered by WebSocket listener setting pc_trigger_rerun_for_status

        except api_client.APIClientError as e:
            st.session_state.pc_pipeline_error = f"API Error: {str(e)} (Details: {e.details})"
            st.session_state.pc_pipeline_running = False # Error occurred, stop running state
        except Exception as e:
            st.session_state.pc_pipeline_error = f"Failed to start podcast generation: {str(e)}"
            st.session_state.pc_pipeline_running = False # Error occurred, stop running state
        # Removed finally block that sets running to False, as WebSocket should handle it
        # Add a rerun if an error occurred to display it immediately
        if st.session_state.pc_pipeline_error:
            st.rerun()

    # Display status, progress, and errors
    if st.session_state.get("pc_task_id"):
        if st.session_state.pc_pipeline_running:
            st.info(f"Task {st.session_state.pc_task_id} is processing...")
            status_text = st.session_state.get("pc_current_stage", "Processing...")
            if st.session_state.get("pc_status_messages"):
                latest_message = st.session_state.pc_status_messages[-1] if st.session_state.pc_status_messages else status_text
                st.progress(st.session_state.pc_current_progress / 100.0, text=latest_message)
            st.markdown("**Live Log:**")
            st.markdown(f'''<div style="height: 200px; overflow-y: auto; border: 1px solid #ccc; padding: 10px; font-family: monospace; white-space: pre-wrap;'>{"<br>".join(st.session_state.pc_status_messages)}</div>''', unsafe_allow_html=True)
        
        elif st.session_state.pc_pipeline_error:
            st.error(f"Task {st.session_state.pc_task_id} failed: {st.session_state.pc_pipeline_error}")
        
        elif not st.session_state.pc_pipeline_running and st.session_state.pc_final_artifact_paths:
            st.success(f"Task {st.session_state.pc_task_id} completed successfully!")
            # Display download links or results here based on pc_final_artifact_paths
            # For now, just a message. Example: st.markdown(f"Podcast Audio: {st.session_state.pc_final_artifact_paths.get('audio_path')}")

    if st.session_state.get("pc_trigger_rerun_for_status", False):
        st.session_state.pc_trigger_rerun_for_status = False
        st.rerun()

# Helper to run asyncio functions in a separate thread
def run_async_in_thread(coro, loop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(coro)

async def listen_to_task_status_async(ws_url: str, session_prefix: str):
    """Listen to task status via WebSocket and update Streamlit session state."""
    try:
        async with websockets.connect(ws_url) as websocket:
            st.session_state[f"{session_prefix}_status_messages"].append(f"Connected to WebSocket: {ws_url}")
            st.session_state[f"{session_prefix}_trigger_rerun_for_status"] = True

            while True:
                try:
                    message_json = await asyncio.wait_for(websocket.recv(), timeout=60) # Timeout for recv
                    status_data = json.loads(message_json)
                    
                    st.session_state[f"{session_prefix}_status_messages"].append(status_data.get("message", "No message"))
                    st.session_state[f"{session_prefix}_current_stage"] = status_data.get("currentStep", "Processing")
                    st.session_state[f"{session_prefix}_current_progress"] = float(status_data.get("progress", 0.0)) * 100 # Assuming progress is 0.0-1.0

                    overall_status = status_data.get("overallStatus")
                    if overall_status == "COMPLETED":
                        st.session_state[f"{session_prefix}_pipeline_running"] = False
                        st.session_state[f"{session_prefix}_final_artifact_paths"] = status_data.get("result", {}) # Store results
                        st.session_state[f"{session_prefix}_status_messages"].append("Pipeline COMPLETED.")
                        st.session_state[f"{session_prefix}_trigger_rerun_for_status"] = True
                        break 
                    elif overall_status == "FAILED":
                        st.session_state[f"{session_prefix}_pipeline_running"] = False
                        st.session_state[f"{session_prefix}_pipeline_error"] = status_data.get("error", "Unknown error from pipeline")
                        st.session_state[f"{session_prefix}_status_messages"].append(f"Pipeline FAILED: {st.session_state[f'{session_prefix}_pipeline_error']}")
                        st.session_state[f"{session_prefix}_trigger_rerun_for_status"] = True
                        break
                    
                    st.session_state[f"{session_prefix}_trigger_rerun_for_status"] = True # Trigger UI update

                except asyncio.TimeoutError:
                    st.session_state[f"{session_prefix}_status_messages"].append("WebSocket receive timeout, will keep listening...")
                    st.session_state[f"{session_prefix}_trigger_rerun_for_status"] = True
                    # Check if task is still considered running on server if possible, or just continue listening
                except websockets.exceptions.ConnectionClosed:
                    st.session_state[f"{session_prefix}_status_messages"].append("WebSocket connection closed.")
                    if st.session_state[f"{session_prefix}_pipeline_running"]:
                        st.session_state[f"{session_prefix}_pipeline_error"] = "WebSocket connection lost unexpectedly."
                        st.session_state[f"{session_prefix}_pipeline_running"] = False
                    st.session_state[f"{session_prefix}_trigger_rerun_for_status"] = True
                    break
                except Exception as e:
                    st.session_state[f"{session_prefix}_status_messages"].append(f"WebSocket listener error: {str(e)}")
                    st.session_state[f"{session_prefix}_pipeline_error"] = f"Error processing status: {str(e)}"
                    st.session_state[f"{session_prefix}_pipeline_running"] = False # Assume failure
                    st.session_state[f"{session_prefix}_trigger_rerun_for_status"] = True
                    break
    except Exception as e:
        st.session_state[f"{session_prefix}_status_messages"].append(f"Failed to connect to WebSocket ({ws_url}): {str(e)}")
        st.session_state[f"{session_prefix}_pipeline_error"] = f"WebSocket connection failed: {str(e)}"
        st.session_state[f"{session_prefix}_pipeline_running"] = False
        st.session_state[f"{session_prefix}_trigger_rerun_for_status"] = True

