import requests
import streamlit as st # For error display and potential config
import json
from typing import Dict, Any, List, Optional
import os

# Determine API base URL from environment variable or default to host and port only.
# The /api prefix will be added in the function calls.
API_HOST_URL = os.getenv("API_HOST_URL", "http://localhost:8000")

class APIClientError(Exception):
    """Custom exception for API client errors."""
    def __init__(self, message, status_code=None, details=None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details

def _handle_response(response: requests.Response) -> Dict[str, Any]:
    """Helper function to handle API responses."""
    if 200 <= response.status_code < 300:
        try:
            return response.json()
        except json.JSONDecodeError:
            raise APIClientError(f"Failed to decode JSON response from {response.url}. Content: {response.text[:200]}", response.status_code)
    else:
        try:
            error_details = response.json().get("detail", response.text)
        except json.JSONDecodeError:
            error_details = response.text
        raise APIClientError(
            f"API request to {response.url} failed with status {response.status_code}.",
            status_code=response.status_code,
            details=error_details
        )

# --- Orchestration Config --- #
def get_orchestration_config() -> Dict[str, Any]:
    """Fetches the full orchestration configuration from the API, including podcast_model and tts_model."""
    url = f"{API_HOST_URL}/api/settings/orchestration"
    try:
        response = requests.get(url)
        return _handle_response(response)
    except requests.exceptions.RequestException as e:
        raise APIClientError(f"Network error fetching orchestration config: {e}")

def update_orchestration_config(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Updates the orchestration configuration via the API, including podcast_model and tts_model."""
    url = f"{API_HOST_URL}/api/settings/orchestration"
    try:
        response = requests.put(url, json=config_data)
        return _handle_response(response)
    except requests.exceptions.RequestException as e:
        raise APIClientError(f"Network error updating orchestration config: {e}")

# --- ArXiv Categories --- #
def get_arxiv_categories() -> Dict[str, Any]:
    """Fetches ArXiv search categories from the API."""
    url = f"{API_HOST_URL}/api/settings/arxiv-categories"
    try:
        response = requests.get(url)
        return _handle_response(response)
    except requests.exceptions.RequestException as e:
        raise APIClientError(f"Network error fetching ArXiv categories: {e}")

def update_arxiv_categories(categories_data: Dict[str, Any]) -> Dict[str, Any]:
    """Updates ArXiv search categories via the API."""
    url = f"{API_HOST_URL}/api/settings/arxiv-categories"
    try:
        response = requests.put(url, json=categories_data)
        return _handle_response(response)
    except requests.exceptions.RequestException as e:
        raise APIClientError(f"Network error updating ArXiv categories: {e}")

# --- Model Providers --- #
def get_model_providers() -> List[Dict[str, Any]]:
    """Fetches the list of model providers from the API."""
    url = f"{API_HOST_URL}/api/model-providers"
    try:
        response = requests.get(url)
        return _handle_response(response)
    except requests.exceptions.RequestException as e:
        raise APIClientError(f"Network error fetching model providers: {e}")

# --- Email Recipients --- # 
def get_email_recipients() -> List[str]:
    """Fetches email recipients from the API."""
    url = f"{API_HOST_URL}/api/settings/email-recipients"
    try:
        response_data = _handle_response(requests.get(url))
        return response_data.get("recipients", [])
    except requests.exceptions.RequestException as e:
        raise APIClientError(f"Network error fetching email recipients: {e}")

def update_email_recipients(recipients: List[str]) -> Dict[str, Any]:
    """Updates email recipients via the API."""
    url = f"{API_HOST_URL}/api/settings/email-recipients"
    try:
        response = requests.put(url, json={"recipients": recipients})
        return _handle_response(response)
    except requests.exceptions.RequestException as e:
        raise APIClientError(f"Network error updating email recipients: {e}")

# --- Research Interests --- #
def get_research_interests() -> str:
    """Fetches research interests from the API."""
    url = f"{API_HOST_URL}/api/settings/research-interests"
    try:
        response_data = _handle_response(requests.get(url))
        return response_data.get("interests", "") # Default to empty string if not found
    except requests.exceptions.RequestException as e:
        raise APIClientError(f"Network error fetching research interests: {e}")

def update_research_interests(interests: str) -> Dict[str, Any]:
    """Updates research interests via the API."""
    url = f"{API_HOST_URL}/api/settings/research-interests"
    try:
        response = requests.put(url, json={"interests": interests})
        return _handle_response(response)
    except requests.exceptions.RequestException as e:
        raise APIClientError(f"Network error updating research interests: {e}")

# --- Theseus Insight Newsletter Actions --- # 
def start_theseus_newsletter_run(
    start_date: str,
    end_date: str,
    email_recipients: List[str],
    research_interests: str,
    generate_podcast: bool = False
) -> str: # Returns task_id
    """Starts the Theseus Insight newsletter generation pipeline via the API."""
    url = f"{API_HOST_URL}/api/actions/run-newsletter-pipeline"
    payload = {
        "start_date": start_date,
        "end_date": end_date,
        "email_recipients": email_recipients,
        "research_interests": research_interests,
        "generate_podcast_run": generate_podcast
    }
    try:
        response = requests.post(url, json=payload)
        response_data = _handle_response(response)
        task_id = response_data.get("task_id")
        if not task_id:
            details = response_data.get("message", str(response_data))
            raise APIClientError(f"Failed to get task_id from pipeline start response. Details: {details}", details=details)
        return task_id
    except requests.exceptions.RequestException as e:
        raise APIClientError(f"Network error starting newsletter pipeline: {e}")
    except APIClientError: 
        raise
    except Exception as e: 
        raise APIClientError(f"Unexpected error when starting newsletter pipeline: {str(e)}")

# --- Podcast Generation --- #
def start_podcast_generation_pipeline(
    input_type: str,
    podcast_model_config: Dict[str, Any],
    tts_model_config: Dict[str, Any],
    create_visualization: bool,
    urls: Optional[List[str]] = None,
    pdf_files: Optional[List[Any]] = None, # Streamlit UploadedFile objects
    intro_music_file: Optional[Any] = None, # Streamlit UploadedFile object
    visualizer_params: Optional[Dict[str, Any]] = None,
) -> str: # Returns task_id
    """Starts the podcast generation pipeline via the API."""
    url = f"{API_HOST_URL}/api/podcast/generate"
    
    # Prepare the main parameters payload as a JSON string
    params_payload_dict = {
        "input_type": input_type,
        "urls": urls,
        "podcast_model_config": podcast_model_config,
        "tts_model_config": tts_model_config,
        "create_visualization": create_visualization,
        "visualizer_params": visualizer_params if create_visualization else None,
    }
    params_json_str = json.dumps(params_payload_dict)
    
    # Prepare form data part for the JSON string
    data_payload = {'params_json': params_json_str}
    
    # Prepare files for multipart upload
    files_to_upload = {}
    if intro_music_file:
        files_to_upload['intro_music_file'] = (intro_music_file.name, intro_music_file, intro_music_file.type)
        
    if input_type == "pdfs" and pdf_files:
        # For multiple files under the same field name, pass a list of (filename, file_obj, content_type) tuples
        pdf_file_tuples = []
        for pdf_file in pdf_files:
            pdf_file_tuples.append((pdf_file.name, pdf_file, pdf_file.type))
        if pdf_file_tuples:
            files_to_upload['pdf_files'] = pdf_file_tuples

    try:
        if not files_to_upload: # No files being sent
            response = requests.post(url, data=data_payload)
        else: # Files are present
            response = requests.post(url, data=data_payload, files=files_to_upload)
            
        response_data = _handle_response(response)
        task_id = response_data.get("task_id")
        if not task_id:
            details = response_data.get("message", str(response_data))
            raise APIClientError(f"Failed to get task_id from podcast generation response. Details: {details}", details=details)
        return task_id
    except requests.exceptions.RequestException as e:
        raise APIClientError(f"Network error starting podcast generation pipeline: {e}")
    except APIClientError: # Re-raise APIClientError if it was raised by _handle_response
        raise
    except Exception as e:
        # Catch any other unexpected errors during request preparation or sending
        import traceback
        print(f"RAW EXCEPTION in start_podcast_generation_pipeline: {traceback.format_exc()}")
        raise APIClientError(f"Unexpected error: {str(e)}")

# Example usage (for testing, not part of the client usually)
if __name__ == "__main__":
    print(f"Using API Host URL: {API_HOST_URL}")
    try:
        print("\n--- Testing Orchestration Config ---")
        orch_conf = get_orchestration_config()
        print("Fetched Orchestration Config:", json.dumps(orch_conf, indent=2))
        # Example update (be cautious with actual updates)
        # orch_conf["judge_model"]["temperature"] = 0.77
        # updated_orch_conf_res = update_orchestration_config(orch_conf)
        # print("Update Response:", updated_orch_conf_res)

        print("\n--- Testing ArXiv Categories ---")
        arxiv_cat = get_arxiv_categories()
        print("Fetched ArXiv Categories:", json.dumps(arxiv_cat, indent=2))
        # Example update
        # arxiv_cat["filter_categories"].append("cs.NE")
        # updated_arxiv_res = update_arxiv_categories(arxiv_cat)
        # print("Update Response:", updated_arxiv_res)

        print("\n--- Testing Model Providers ---")
        providers = get_model_providers()
        print("Fetched Model Providers:", json.dumps(providers, indent=2))

        print("\n--- Testing Email Recipients ---")
        emails = get_email_recipients()
        print("Fetched Email Recipients:", emails)
        # updated_emails_res = update_email_recipients(["test1@example.com", "test2@example.com"])
        # print("Update Response:", updated_emails_res)

        print("\n--- Testing Research Interests ---")
        research_interests_text = get_research_interests()
        print("Fetched Research Interests:", research_interests_text)
        # Example update
        # updated_interests_res = update_research_interests("New research interests focused on AI safety.")
        # print("Update Response:", updated_interests_res)

    except APIClientError as e:
        print(f"API Client Error: {str(e)} (Status: {e.status_code})")
        if e.details:
            print(f"Details: {e.details}")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}") 