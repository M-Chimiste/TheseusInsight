import streamlit as st
from datetime import datetime, timedelta, date
from streamlit_app import api_client # Assuming api_client is in streamlit_app directory
import json
import asyncio
import websockets # Ensure this is in requirements.txt
from typing import List, Dict, Any
import threading # New import
import time # For controlled reruns if adopted

# Helper to parse emails from text_area
def parse_emails_from_text(text_content: str) -> List[str]:
    recipients = []
    if text_content:
        # Split by newline first, then iterate and split by comma
        lines = text_content.split('\n')
        for line in lines:
            recipients.extend(item.strip() for item in line.split(',') if item.strip())
    # Basic validation: ensure it looks somewhat like an email. More robust validation is on backend.
    return [email for email in recipients if "@" in email and "." in email and email not in [None, ""]]

# Define a container for status messages to prevent them from overlapping
if 'status_messages' not in st.session_state:
    st.session_state.status_messages = []

# Initialize session state keys if they don't exist
def initialize_session_state():
    default_n_days = 7
    keys_defaults = {
        'nl_run_task_id': None,
        'nl_run_start_date': date.today() - timedelta(days=default_n_days - 1),
        'nl_run_end_date': date.today(),
        'nl_run_n_days': default_n_days,
        'nl_run_email_recipients_str': "",
        'nl_run_research_interests': "",
        'nl_run_generate_podcast': False,
        'status_messages': [],
        'active_listener_task_id': None, # Tracks task_id for the active listener thread
        'trigger_rerun_for_status': False
    }
    for key, default_value in keys_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

    # Load defaults only once per session or if explicitly refreshed
    if not st.session_state.get('_nl_recipients_loaded', False):
        try:
            recipients = api_client.get_email_recipients()
            st.session_state.nl_run_email_recipients_str = "\n".join(recipients)
        except api_client.APIClientError as e:
            st.toast(f"Could not load default email recipients: {str(e)}", icon="⚠️")
        st.session_state._nl_recipients_loaded = True

    if not st.session_state.get('_nl_interests_loaded', False):
        try:
            interests = api_client.get_research_interests()
            st.session_state.nl_run_research_interests = interests
        except api_client.APIClientError as e:
            st.toast(f"Could not load default research interests: {str(e)}", icon="⚠️")
        st.session_state._nl_interests_loaded = True

async def listen_to_task_status_async(task_id: str):
    # This function is now intended to be run via _run_websocket_listener_in_thread
    ws_host_url = api_client.API_HOST_URL
    ws_uri_base = "ws://localhost:8000" # Fallback
    if ws_host_url.startswith("http://"):
        ws_uri_base = f"ws://{ws_host_url[len('http://'):]}"
    elif ws_host_url.startswith("https://"):
        ws_uri_base = f"wss://{ws_host_url[len('https://'):]}"
    
    uri = f"{ws_uri_base}/ws/newsletter/{task_id}"
    
    st.session_state.status_messages.append(f"INFO: Attempting WebSocket connection to {uri} for task {task_id}...")

    try:
        async with websockets.connect(uri) as websocket:
            st.session_state.status_messages.append(f"INFO: WebSocket connected for task {task_id}. Waiting for updates...")
            while True:
                message_str = await websocket.recv()
                status_data = json.loads(message_str)
                
                overall_status = status_data.get("overallStatus", "UNKNOWN")
                current_step = status_data.get("currentStep", "N/A")
                progress = status_data.get("progress", 0)
                message = status_data.get("message", "No details.")
                error_detail = status_data.get("error")

                log_message = f"STATUS: {overall_status} | STEP: {current_step} | PROGRESS: {progress*100:.2f}% | MSG: {message}"
                if error_detail:
                    log_message += f" | ERROR: {error_detail}"
                
                st.session_state.status_messages.append(log_message)
                # To make UI update, we need a rerun. Thread can't call st.rerun().
                # Setting a flag can help the main thread decide to rerun.
                # For now, updates will appear on next natural rerun or manual refresh.

                if overall_status in ["COMPLETED", "FAILED"]:
                    final_message = f"Pipeline {overall_status.lower()}"
                    if error_detail:
                        final_message += f": {error_detail}"
                    st.session_state.status_messages.append(f"INFO: {final_message}")
                    st.session_state.nl_run_task_id = None # Task finished
                    st.session_state.active_listener_task_id = None # Listener finished
                    st.session_state.trigger_rerun_for_status = True # Signal main thread
                    break
    except websockets.exceptions.ConnectionClosed as cc_err:
        st.session_state.status_messages.append(f"WARNING: WebSocket connection closed. Task {task_id}. Reason: {cc_err}.")
    except ConnectionRefusedError:
        st.session_state.status_messages.append(f"ERROR: WebSocket connection refused for task {task_id} at {uri}.")
    except Exception as e:
        st.session_state.status_messages.append(f"ERROR: WebSocket listener error for task {task_id}: {type(e).__name__} - {str(e)}")
    finally:
        st.session_state.status_messages.append(f"INFO: WebSocket listener for task {task_id} terminated.")
        if st.session_state.nl_run_task_id == task_id: # If task didn't complete cleanly through status update
            st.session_state.nl_run_task_id = None
            st.session_state.active_listener_task_id = None
        st.session_state.trigger_rerun_for_status = True # Ensure UI refreshes after listener stops

def _run_websocket_listener_in_thread(task_id: str):
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(listen_to_task_status_async(task_id))
    finally:
        loop.close()

def show_newsletter_page():
    initialize_session_state() # Ensure all session state variables are set up
    st.title("📰 New Theseus Insight Newsletter Run")

    # Handle rerun trigger from listener thread
    if st.session_state.get('trigger_rerun_for_status', False):
        st.session_state.trigger_rerun_for_status = False # Reset flag
        # Check if this rerun is for a completed/failed task
        # Display final toast message here if desired, as session state has been updated by thread
        last_message = st.session_state.status_messages[-1] if st.session_state.status_messages else ""
        if "Pipeline completed" in last_message.lower():
            st.toast("Newsletter pipeline completed!", icon="✅")
        elif "Pipeline failed" in last_message.lower() or "error" in last_message.lower():
            st.toast("Newsletter pipeline encountered an error.", icon="❌")
        st.rerun()

    st.subheader("🗓️ Date Range for Paper Discovery")
    col1, col2, col3 = st.columns([1,2,2])
    with col1:
        n_days_ui = st.number_input("Days", value=st.session_state.nl_run_n_days, min_value=1, key="_nl_n_days", help="Number of past days (relative to End Date).")
    with col2:
        start_date_ui = st.date_input("Start Date", value=st.session_state.nl_run_start_date, key="_nl_start_date", max_value=date.today())
    with col3:
        end_date_ui = st.date_input("End Date", value=st.session_state.nl_run_end_date, key="_nl_end_date", max_value=date.today())

    if n_days_ui != st.session_state.nl_run_n_days:
        st.session_state.nl_run_n_days = n_days_ui
        st.session_state.nl_run_start_date = end_date_ui - timedelta(days=n_days_ui - 1)
        st.rerun()
    if start_date_ui != st.session_state.nl_run_start_date:
        st.session_state.nl_run_start_date = start_date_ui
        if start_date_ui > end_date_ui: st.session_state.nl_run_end_date = start_date_ui
        st.session_state.nl_run_n_days = (st.session_state.nl_run_end_date - st.session_state.nl_run_start_date).days + 1
        st.rerun()
    if end_date_ui != st.session_state.nl_run_end_date:
        st.session_state.nl_run_end_date = end_date_ui
        if start_date_ui > end_date_ui: st.session_state.nl_run_start_date = end_date_ui
        st.session_state.nl_run_n_days = (st.session_state.nl_run_end_date - st.session_state.nl_run_start_date).days + 1
        st.rerun()

    st.markdown("---")
    st.subheader("🎯 Targeting and Content Focus")
    email_recipients_input = st.text_area("Email Recipients (for this run)", value=st.session_state.nl_run_email_recipients_str, height=100, key="_nl_email_recipients_ta", help="Emails, separated by newlines or commas.")
    research_interests_input = st.text_area("Research Interests (for this run)", value=st.session_state.nl_run_research_interests, height=150, key="_nl_research_interests_ta", help="Define research focus.")
    generate_podcast_input = st.checkbox("🎙️ Also generate Podcast?", value=st.session_state.nl_run_generate_podcast, key="_nl_gen_podcast_cb")

    st.session_state.nl_run_email_recipients_str = email_recipients_input
    st.session_state.nl_run_research_interests = research_interests_input
    st.session_state.nl_run_generate_podcast = generate_podcast_input

    st.markdown("---")
    # Disable button if a task is currently being processed (nl_run_task_id is not None)
    # or if a listener is active for a different task_id (active_listener_task_id is not None and different)
    run_button_disabled = st.session_state.nl_run_task_id is not None
    
    if st.button("🚀 Generate Newsletter", use_container_width=True, type="primary", key="_nl_run_btn", disabled=run_button_disabled):
        if not st.session_state.nl_run_research_interests.strip():
            st.error("Research Interests cannot be empty.")
        else:
            final_recipients_list = parse_emails_from_text(st.session_state.nl_run_email_recipients_str)
            if not final_recipients_list and st.session_state.nl_run_email_recipients_str.strip():
                 st.warning("No valid email recipients found.")
            
            st.session_state.status_messages = ["INFO: Initiating newsletter generation..."]
            try:
                task_id = api_client.start_theseus_newsletter_run(
                    start_date=st.session_state.nl_run_start_date.strftime("%Y-%m-%d"),
                    end_date=st.session_state.nl_run_end_date.strftime("%Y-%m-%d"),
                    email_recipients=final_recipients_list,
                    research_interests=st.session_state.nl_run_research_interests,
                    generate_podcast=st.session_state.nl_run_generate_podcast
                )
                st.session_state.nl_run_task_id = task_id
                st.session_state.active_listener_task_id = task_id # Mark that a listener is starting for this task
                st.session_state.trigger_rerun_for_status = False # Reset flag before starting thread
                
                # Start the WebSocket listener in a new thread
                listener_thread = threading.Thread(
                    target=_run_websocket_listener_in_thread, 
                    args=(task_id,), 
                    daemon=True
                )
                listener_thread.start()
                
                st.success(f"Pipeline initiated! Task ID: {task_id}. Updates will appear below.")
                st.rerun() # Rerun to reflect button disable and initial status message
            except api_client.APIClientError as e:
                st.error(f"API Error: {str(e)} (Details: {e.details})")
                st.session_state.nl_run_task_id = None
                st.session_state.active_listener_task_id = None
            except Exception as e:
                st.error(f"Unexpected error: {str(e)}")
                st.session_state.nl_run_task_id = None
                st.session_state.active_listener_task_id = None

    # Display Status Area
    st.subheader("Pipeline Status")
    if st.session_state.status_messages:
        # Use a markdown block for better scrollability and formatting if messages get long
        status_text = "\n".join(st.session_state.status_messages[-20:]) # Show last 20 messages
        st.markdown(f"```\n{status_text}\n```", help="Latest status updates from the pipeline.")
    elif st.session_state.nl_run_task_id:
        st.info("Task is running. Waiting for first status update...")
    else:
        st.info("No active newsletter generation task. Configure and click 'Generate Newsletter' to start.") 