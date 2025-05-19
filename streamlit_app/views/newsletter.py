import streamlit as st
from datetime import datetime, timedelta, date
from streamlit_app import api_client # Assuming api_client is in streamlit_app directory
import json
import asyncio
# import websockets # No longer directly used here
from typing import List, Dict, Any
import threading
# import time # For controlled reruns if adopted

from streamlit_app.api_utils import listen_to_task_status_async, run_async_in_thread

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

# Initialize session state keys if they don't exist
def initialize_newsletter_session_state(): # Renamed for clarity and consistency
    default_n_days = 7
    # Keys specific to the newsletter run form and status
    keys_defaults = {
        'nl_run_task_id': None,
        'nl_run_start_date': date.today() - timedelta(days=default_n_days - 1),
        'nl_run_end_date': date.today(),
        'nl_run_n_days': default_n_days,
        'nl_run_email_recipients_str': "",
        'nl_run_research_interests': "",
        'nl_run_generate_podcast': False,
        
        # Status tracking for newsletter, prefixed with 'nl_'
        'nl_status_messages': [],
        'nl_pipeline_running': False,
        'nl_pipeline_error': None,
        'nl_current_stage': "",
        'nl_current_progress': 0.0,
        'nl_final_artifact_paths': None,
        'nl_trigger_rerun_for_status': False,
        'nl_active_listener_task_id': None # Tracks task_id for the active listener thread
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

def show_newsletter_page():
    initialize_newsletter_session_state() # Ensure all session state variables are set up
    st.title("📰 New Theseus Insight Newsletter Run")

    # Handle rerun trigger from listener thread
    if st.session_state.get('nl_trigger_rerun_for_status', False):
        st.session_state.nl_trigger_rerun_for_status = False # Reset flag
        # Check if this rerun is for a completed/failed task
        # Display final toast message here if desired, as session state has been updated by thread
        last_message = st.session_state.nl_status_messages[-1] if st.session_state.nl_status_messages else ""
        if "Pipeline completed" in last_message.lower():
            st.toast("Newsletter pipeline completed!", icon="✅")
        elif "Pipeline failed" in last_message.lower() or "error" in last_message.lower():
            st.toast("Newsletter pipeline encountered an error.", icon="❌")
        st.rerun()

    st.subheader("🗓️ Date Range for Paper Discovery")
    col1, col2, col3 = st.columns([1,2,2])
    with col1:
        n_days_ui = st.number_input("Days", value=st.session_state.nl_run_n_days, min_value=1, key="_nl_n_days_input", help="Number of past days (relative to End Date).")
    with col2:
        start_date_ui = st.date_input("Start Date", value=st.session_state.nl_run_start_date, key="_nl_start_date_input", max_value=date.today())
    with col3:
        end_date_ui = st.date_input("End Date", value=st.session_state.nl_run_end_date, key="_nl_end_date_input", max_value=date.today())

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
    email_recipients_input = st.text_area("Email Recipients (for this run)", value=st.session_state.nl_run_email_recipients_str, height=100, key="_nl_email_recipients_ta_input", help="Emails, separated by newlines or commas.")
    research_interests_input = st.text_area("Research Interests (for this run)", value=st.session_state.nl_run_research_interests, height=150, key="_nl_research_interests_ta_input", help="Define research focus.")
    generate_podcast_input = st.checkbox("🎙️ Also generate Podcast?", value=st.session_state.nl_run_generate_podcast, key="_nl_gen_podcast_cb_input")

    st.session_state.nl_run_email_recipients_str = email_recipients_input
    st.session_state.nl_run_research_interests = research_interests_input
    st.session_state.nl_run_generate_podcast = generate_podcast_input

    st.markdown("---")
    # Disable button if a task is currently being processed (nl_run_task_id is not None)
    # or if a listener is active for a different task_id (active_listener_task_id is not None and different)
    run_button_disabled = st.session_state.nl_pipeline_running or (st.session_state.nl_active_listener_task_id is not None and st.session_state.nl_active_listener_task_id != st.session_state.nl_run_task_id)
    
    if st.button("🚀 Generate Newsletter", use_container_width=True, type="primary", key="_nl_run_btn_input", disabled=run_button_disabled):
        if not st.session_state.nl_run_research_interests.strip():
            st.error("Research Interests cannot be empty.")
        else:
            final_recipients_list = parse_emails_from_text(st.session_state.nl_run_email_recipients_str)
            if not final_recipients_list and st.session_state.nl_run_email_recipients_str.strip():
                 st.warning("No valid email recipients found from the input. Proceeding without recipients for this run if you continue.")
            
            # Set initial status for UI update *before* long running operations
            st.session_state.nl_status_messages = ["INFO: Initiating newsletter generation..."]
            st.session_state.nl_pipeline_running = True
            st.session_state.nl_pipeline_error = None
            st.session_state.nl_current_stage = "Initiating"
            st.session_state.nl_current_progress = 5.0 
            st.session_state.nl_final_artifact_paths = None
            st.session_state.nl_trigger_rerun_for_status = False 
            # No st.rerun() here yet

            try:
                # Perform the API call and thread start first
                task_id = api_client.start_theseus_newsletter_run(
                    start_date=st.session_state.nl_run_start_date.strftime("%Y-%m-%d"),
                    end_date=st.session_state.nl_run_end_date.strftime("%Y-%m-%d"),
                    email_recipients=final_recipients_list,
                    research_interests=st.session_state.nl_run_research_interests,
                    generate_podcast=st.session_state.nl_run_generate_podcast
                )
                st.session_state.nl_run_task_id = task_id
                st.session_state.nl_active_listener_task_id = task_id 
                
                # No longer need to manage loop here
                # try:
                #     loop = asyncio.get_event_loop()
                #     if loop.is_closed():
                #         loop = asyncio.new_event_loop()
                #         asyncio.set_event_loop(loop)
                # except RuntimeError: 
                #     loop = asyncio.new_event_loop()
                #     asyncio.set_event_loop(loop)

                # Start listener thread
                ws_endpoint_path = "/ws/newsletter" # Specific endpoint for newsletter
                listener_thread = threading.Thread(
                    target=run_async_in_thread,
                    args=(listen_to_task_status_async(task_id, "nl", ws_endpoint_path),), # Note the trailing comma for single arg tuple
                    daemon=True
                )
                listener_thread.start()
                
                st.success(f"Pipeline initiated! Task ID: {task_id}. Updates will appear below.")
                # Now that task is initiated, rerun to update button state etc.
                st.rerun() 

            except api_client.APIClientError as e:
                st.session_state.nl_pipeline_error = f"API Error: {str(e)} (Details: {e.details})"
                st.session_state.nl_pipeline_running = False # Task failed to start
                st.session_state.nl_active_listener_task_id = None
                st.rerun() 
            except Exception as e_main:
                st.session_state.nl_pipeline_error = f"Unexpected error: {str(e_main)}"
                st.session_state.nl_pipeline_running = False # Task failed to start
                st.session_state.nl_active_listener_task_id = None
                st.rerun() 

    # Display Status Area
    st.subheader("Pipeline Status")
    if st.session_state.get("nl_run_task_id") or st.session_state.get("nl_active_listener_task_id"):
        if st.session_state.nl_pipeline_running:
            st.info(f"Task {st.session_state.nl_run_task_id or st.session_state.nl_active_listener_task_id} is processing...")
        
        # Display progress bar
        latest_message_for_progress = st.session_state.nl_current_stage
        if st.session_state.nl_status_messages:
            # Try to find a message that includes progress info if current_stage is too generic
            for msg in reversed(st.session_state.nl_status_messages):
                if "PROGRESS:" in msg:
                    latest_message_for_progress = msg.split("MSG: ",1)[-1].split(" | ERROR:",1)[0]
                    break
        st.progress(st.session_state.nl_current_progress / 100.0, text=latest_message_for_progress)

        # Display log messages
        log_display = "\n".join(st.session_state.nl_status_messages[-20:]) 
        st.markdown("""**Live Log:**
<div style="height: 200px; overflow-y: auto; border: 1px solid #ccc; padding: 10px; font-family: monospace; white-space: pre-wrap;">{}</div>""".format(log_display.replace("\n", "<br>")), unsafe_allow_html=True)
        
        if not st.session_state.nl_pipeline_running and st.session_state.nl_pipeline_error:
            st.error(f"Task failed: {st.session_state.nl_pipeline_error}")
        elif not st.session_state.nl_pipeline_running and st.session_state.nl_final_artifact_paths is not None:
            st.success("Task completed successfully!")
            # Potentially show download links using nl_final_artifact_paths here
    else:
        st.info("No active newsletter generation task. Configure and click 'Generate Newsletter' to start.") 