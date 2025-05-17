import streamlit as st
import os
import requests
from typing import Dict, Any, Optional

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