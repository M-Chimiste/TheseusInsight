import streamlit as st
import os
from dotenv import load_dotenv
from pathlib import Path
import json
from datetime import datetime, timedelta
import requests
import asyncio
import websockets
import json
from typing import Dict, Any, Optional, List

# Load environment variables
load_dotenv()

# Configure the page
st.set_page_config(
    page_title="Theseus Insight",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
WS_BASE_URL = os.getenv("WS_BASE_URL", "ws://localhost:8000")

# Custom CSS for better styling
st.markdown("""
    <style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .sidebar .sidebar-content {
        width: 280px;
    }
    .stProgress > div > div > div > div {
        background-color: #4CAF50;
    }
    .stButton>button {
        width: 100%;
    }
    .stSelectbox, .stTextInput, .stTextArea, .stDateInput, .stTimeInput {
        margin-bottom: 1rem;
    }
    """, unsafe_allow_html=True)

# State management
if 'auth_token' not in st.session_state:
    st.session_state.auth_token = None

class APIError(Exception):
    pass

def make_api_request(method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None, files: Optional[Dict] = None):
    """Make an API request to the FastAPI backend."""
    url = f"{API_BASE_URL}{endpoint}"
    headers = {}
    
    if st.session_state.auth_token:
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
            except:
                error_msg = e.response.text or str(e)
        raise APIError(f"API request failed: {error_msg}")

# Sidebar navigation
def render_sidebar():
    st.sidebar.title("Theseus Insight")
    
    # Navigation menu
    menu = {
        "🎛️ Settings": "settings",
        "📰 Newsletter Builder": "newsletter",
        "🎙️ Podcast Builder": "podcast",
        "📄 Paper Ratings": "papers",
        "📊 Run Log": "runs"
    }
    
    # Render navigation
    st.sidebar.title("Navigation")
    selection = st.sidebar.radio("", list(menu.keys()))
    
    # Add some space and app info
    st.sidebar.markdown("---")
    st.sidebar.info(
        "Theseus Insight v0.3\n\n"
        "Research paper analysis and newsletter generation tool"
    )
    
    return menu[selection]

# Main app
def main():
    # Render sidebar and get current page
    page = render_sidebar()
    
    # Display the selected page
    if page == "settings":
        from pages.settings import show_settings_page
        show_settings_page()
    elif page == "newsletter":
        from pages.newsletter import show_newsletter_page
        show_newsletter_page()
    elif page == "podcast":
        from pages.podcast import show_podcast_page
        show_podcast_page()
    elif page == "papers":
        from pages.papers import show_papers_page
        show_papers_page()
    elif page == "runs":
        from pages.runs import show_runs_page
        show_runs_page()

if __name__ == "__main__":
    main()
