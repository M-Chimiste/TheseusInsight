import streamlit as st
import os
import requests
from typing import Dict, Any, Optional
import json
import asyncio
import threading
import websockets
from streamlit_app import api_client
from theseus_insight.api.tasks import TaskStatus

# API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

class APIError(Exception):
    pass

def make_api_request(method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None, files: Optional[Dict] = None):
    """Make an API request to the FastAPI backend."""
    url = f"{API_BASE_URL}{endpoint}"
    headers = {}
    
    # Ensure st.session_state is accessed safely, as this util might be imported
    # where st.session_state is not yet fully initialized or in a non-Streamlit context.
    # However, for page imports, it should be fine.
    if hasattr(st, 'session_state') and st.session_state.get('auth_token'):
        headers["Authorization"] = f"Bearer {st.session_state.auth_token}"
    
    try:
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers, params=params)
        elif method.upper() == 'POST':
            if files:
                response = requests.post(url, headers=headers, data=data, files=files)
            else:
                response = requests.post(url, headers=headers, json=data)
        elif method.upper() == 'PUT':
            response = requests.put(url, headers=headers, json=data)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        response.raise_for_status()
        return response.json() if response.content else {}
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_msg = e.response.json().get('detail', str(e))
            except: # Pokemon exception handling is not ideal, but for a quick fix.
                error_msg = e.response.text or str(e)
        raise APIError(f"API request failed: {error_msg}")

# --- WebSocket Utility Functions (Moved from views/newsletter.py) --- #

async def listen_to_task_status_async(task_id: str, session_prefix: str, ws_endpoint_path: str):
    ws_host_url = api_client.API_HOST_URL
    # Ensure ws_uri_base is derived correctly, handling potential trailing slashes in API_HOST_URL or ws_endpoint_path
    cleaned_host = ws_host_url.replace("http://", "", 1).replace("https://", "", 1).rstrip("/")
    protocol = "wss" if ws_host_url.startswith("https://") else "ws"
    cleaned_endpoint_path = ws_endpoint_path.lstrip("/")
    uri = f"{protocol}://{cleaned_host}/{cleaned_endpoint_path}/{task_id}"

    status_messages_key = f"{session_prefix}_status_messages"
    trigger_rerun_key = f"{session_prefix}_trigger_rerun_for_status"
    pipeline_running_key = f"{session_prefix}_pipeline_running"
    active_listener_task_id_key = f"{session_prefix}_active_listener_task_id"
    current_stage_key = f"{session_prefix}_current_stage"
    current_progress_key = f"{session_prefix}_current_progress"
    pipeline_error_key = f"{session_prefix}_pipeline_error"
    final_artifact_paths_key = f"{session_prefix}_final_artifact_paths"
    
    # Robustly initialize session state keys
    if not isinstance(st.session_state.get(status_messages_key), list):
        st.session_state[status_messages_key] = []
    if trigger_rerun_key not in st.session_state: st.session_state[trigger_rerun_key] = False
    if pipeline_running_key not in st.session_state: st.session_state[pipeline_running_key] = False
    if active_listener_task_id_key not in st.session_state: st.session_state[active_listener_task_id_key] = None
    if current_stage_key not in st.session_state: st.session_state[current_stage_key] = ""
    if current_progress_key not in st.session_state: st.session_state[current_progress_key] = 0.0
    if pipeline_error_key not in st.session_state: st.session_state[pipeline_error_key] = None
    if final_artifact_paths_key not in st.session_state: st.session_state[final_artifact_paths_key] = None
    
    st.session_state[status_messages_key].append(f"DEBUG: Listener initiated for task {task_id} at {uri}.")
    st.session_state[trigger_rerun_key] = True 

    try:
        st.session_state[status_messages_key].append(f"DEBUG: Attempting WebSocket connection to {uri}...")
        st.session_state[trigger_rerun_key] = True
        
        async with websockets.connect(uri, open_timeout=10) as websocket:
            st.session_state[status_messages_key].append(f"DEBUG: WebSocket connected successfully to {uri}.")
            st.session_state[pipeline_running_key] = True 
            st.session_state[active_listener_task_id_key] = task_id
            st.session_state[trigger_rerun_key] = True

            while True:
                message_processed_in_loop = False
                try:
                    # DEBUG: Log before attempting to receive
                    # st.session_state[status_messages_key].append(f"DEBUG: Waiting to receive message from WebSocket...")
                    # st.session_state[trigger_rerun_key] = True # Potentially too frequent

                    message_str = await asyncio.wait_for(websocket.recv(), timeout=60)
                    st.session_state[status_messages_key].append(f"DEBUG: Received raw message: {message_str[:300]}...")
                    status_data = json.loads(message_str)
                    message_processed_in_loop = True # Flag that we got and processed a message
                    
                    overall_status = status_data.get("overallStatus", "UNKNOWN_STATUS")
                    current_step = status_data.get("currentStep", "N/A_STEP")
                    progress = float(status_data.get("progress", 0.0)) * 100
                    message = status_data.get("message", "No details provided.")
                    error_detail = status_data.get("error")
                    result = status_data.get("result")

                    log_message = f"LIVE_UPDATE: Status={overall_status}, Step='{current_step}', Progress={progress:.1f}%, Msg='{message}'"
                    if error_detail:
                        log_message += f" | Error='{error_detail}'"
                    
                    st.session_state[status_messages_key].append(log_message)
                    st.session_state[current_stage_key] = current_step
                    st.session_state[current_progress_key] = progress
                    st.session_state[pipeline_error_key] = error_detail

                    if overall_status == TaskStatus.COMPLETED.value:
                        st.session_state[pipeline_running_key] = False
                        st.session_state[final_artifact_paths_key] = result
                        st.session_state[status_messages_key].append(f"INFO: Pipeline COMPLETED for task {task_id}.")
                        break 
                    elif overall_status == TaskStatus.FAILED.value:
                        st.session_state[pipeline_running_key] = False
                        error_msg_to_show = error_detail or st.session_state.get(f'{session_prefix}_pipeline_error') or "Unknown failure"
                        st.session_state[pipeline_error_key] = error_msg_to_show
                        st.session_state[status_messages_key].append(f"INFO: Pipeline FAILED for task {task_id}. Reason: {error_msg_to_show}")
                        break
                except asyncio.TimeoutError:
                    st.session_state[status_messages_key].append("DEBUG: WebSocket receive timeout (60s). Will try recv() again...")
                    # No explicit break, just continue the while loop to try recv() again.
                    # trigger_rerun_key will be set in finally
                except websockets.exceptions.ConnectionClosed as cc_err:
                    st.session_state[status_messages_key].append(f"ERROR: WebSocket connection closed for task {task_id}. Code: {cc_err.code}, Reason: {cc_err.reason}")
                    if st.session_state.get(pipeline_running_key, False):
                        st.session_state[pipeline_error_key] = f"WebSocket connection lost (Code: {cc_err.code})"
                        st.session_state[pipeline_running_key] = False
                    break 
                except json.JSONDecodeError as json_err:
                    st.session_state[status_messages_key].append(f"ERROR: Failed to decode JSON from WebSocket: {json_err}. Message: {message_str[:300]}...")
                    message_processed_in_loop = True # Still count as message processing attempt
                except Exception as e_inner:
                    st.session_state[status_messages_key].append(f"ERROR: WebSocket listener (inner loop) unexpected error for task {task_id}: {type(e_inner).__name__} - {str(e_inner)}")
                    st.session_state[pipeline_error_key] = f"Error processing status: {str(e_inner)}"
                    st.session_state[pipeline_running_key] = False
                    break 
                finally:
                    # Trigger rerun only if a message was processed or an error occurred in this iteration
                    # (excluding timeout, which just retries)
                    if message_processed_in_loop or isinstance(e_inner, (websockets.exceptions.ConnectionClosed, json.JSONDecodeError, Exception)):
                         st.session_state[trigger_rerun_key] = True
    
    except websockets.exceptions.InvalidURI as iu_err:
        st.session_state[status_messages_key].append(f"FATAL_WS_SETUP: Invalid WebSocket URI: '{uri}'. Error: {iu_err}")
        st.session_state[pipeline_error_key] = f"Invalid WebSocket URI: {uri}"
        st.session_state[trigger_rerun_key] = True 
    except websockets.exceptions.WebSocketException as ws_conn_err: 
        st.session_state[status_messages_key].append(f"FATAL_WS_SETUP: WebSocket connection to {uri} failed. Error: {type(ws_conn_err).__name__} - {ws_conn_err}")
        st.session_state[pipeline_error_key] = f"Connection to {uri} failed: {ws_conn_err}"
        st.session_state[trigger_rerun_key] = True 
    except ConnectionRefusedError: 
        st.session_state[status_messages_key].append(f"FATAL_WS_SETUP: WebSocket connection REFUSED for task {task_id} at {uri}.")
        st.session_state[pipeline_error_key] = "Connection refused by WebSocket server."
        st.session_state[trigger_rerun_key] = True 
    except Exception as e_outer:
        st.session_state[status_messages_key].append(f"FATAL_WS_SETUP: Unhandled exception during WebSocket setup for task {task_id}: {type(e_outer).__name__} - {str(e_outer)}")
        st.session_state[pipeline_error_key] = f"WebSocket setup failed: {str(e_outer)}"
        st.session_state[trigger_rerun_key] = True 
    finally:
        st.session_state[status_messages_key].append(f"INFO: WebSocket listener for task {task_id} is terminating.")
        if st.session_state.get(active_listener_task_id_key) == task_id: 
            if st.session_state.get(pipeline_running_key, False):
                st.session_state[pipeline_running_key] = False
                if not st.session_state.get(pipeline_error_key):
                     st.session_state[pipeline_error_key] = "Listener terminated without explicit task completion or failure signal."
            st.session_state[active_listener_task_id_key] = None 
        st.session_state[trigger_rerun_key] = True # Always trigger a final rerun when listener terminates

def run_async_in_thread(async_function_with_args):
    """Runs an async function in a separate thread, creating and managing its own event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(async_function_with_args)
    finally:
        loop.close() 