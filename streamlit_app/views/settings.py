import streamlit as st
import os
from typing import Dict, Any
from api_utils import make_api_request, APIError

def apply_theme(theme):
    """Apply the selected theme."""
    if theme == 'Dark':
        st.markdown("""
            <style>
                :root {
                    --text-primary: #f3f4f6 !important;
                    --text-secondary: #9ca3af !important;
                    --bg-primary: #111827 !important;
                    --bg-secondary: #1f2937 !important;
                    --card-bg: #1f2937 !important;
                    --border-color: #374151 !important;
                }
                .stApp, .main .block-container {
                    background-color: var(--bg-primary) !important;
                    color: var(--text-primary) !important;
                }
                .stTextInput > div > div > input, 
                .stTextArea > div > div > textarea,
                .stSelectbox > div > div,
                .stNumberInput > div > input,
                .stSlider > div > div > div > div {
                    background-color: var(--bg-secondary) !important;
                    color: var(--text-primary) !important;
                    border-color: var(--border-color) !important;
                }
                .stRadio > div {
                    background-color: var(--bg-secondary) !important;
                    padding: 10px;
                    border-radius: 0.5rem;
                }
            </style>
        """, unsafe_allow_html=True)
    elif theme == 'Light':
        st.markdown("""
            <style>
                :root {
                    --text-primary: #111827 !important;
                    --text-secondary: #4b5563 !important;
                    --bg-primary: #ffffff !important;
                    --bg-secondary: #f3f4f6 !important;
                    --card-bg: #ffffff !important;
                    --border-color: #e5e7eb !important;
                }
                .stApp, .main .block-container {
                    background-color: var(--bg-primary) !important;
                    color: var(--text-primary) !important;
                }
            </style>
        """, unsafe_allow_html=True)
    # For 'System', we'll let the OS preference take over via the media query

def save_settings(settings):
    """Save settings to session state and apply theme."""
    st.session_state.settings = settings
    apply_theme(settings.get('theme', 'System'))

def show_settings_page():
    st.title("⚙️ Settings")
    
    # Initialize settings in session state if not present
    if 'settings' not in st.session_state:
        st.session_state.settings = {
            'theme': 'System',
            'api_key': os.getenv("API_KEY", ""),
            'environment': 'Development',
            'model': 'GPT-4',
            'temperature': 0.7,
            'max_tokens': 2000,
            'batch_size': 10
        }
    
    # Create a modern card-like container for settings
    with st.container():
        with st.form("settings_form"):
            st.subheader("Display Settings")
            
            # Theme toggle with improved styling
            theme = st.radio(
                "Theme",
                ["Light", "Dark", "System"],
                index=["Light", "Dark", "System"].index(st.session_state.settings.get('theme', 'System')),
                horizontal=True,
                help="Choose the application theme",
                key="theme_selector"
            )
            
            # Update theme immediately when changed
            if theme != st.session_state.settings.get('theme'):
                st.session_state.settings['theme'] = theme
                apply_theme(theme)
            
            st.markdown("---")
            st.subheader("API Configuration")
            
            # API Key input with modern styling
            api_key = st.text_input(
                "API Key",
                type="password",
                value=st.session_state.settings.get('api_key', ''),
                help="Enter your API key for authentication"
            )
            
            # Environment selection
            environment = st.selectbox(
                "Environment",
                ["Development", "Staging", "Production"],
                index=["Development", "Staging", "Production"].index(st.session_state.settings.get('environment', 'Development')),
                help="Select the environment for API endpoints"
            )
            
            # Model settings
            st.subheader("Model Settings")
            
            model = st.selectbox(
                "Default Language Model",
                ["GPT-4", "GPT-3.5-Turbo", "Claude-2", "Claude-3"],
                index=["GPT-4", "GPT-3.5-Turbo", "Claude-2", "Claude-3"].index(st.session_state.settings.get('model', 'GPT-4')),
                help="Select the default language model for text generation"
            )
            
            temperature = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=1.0,
                value=float(st.session_state.settings.get('temperature', 0.7)),
                step=0.1,
                help="Control the randomness of the model's output (lower = more deterministic, higher = more creative)"
            )
            
            # Advanced settings in an expander
            with st.expander("Advanced Settings"):
                max_tokens = st.number_input(
                    "Max Tokens",
                    min_value=100,
                    max_value=4000,
                    value=int(st.session_state.settings.get('max_tokens', 2000)),
                    step=100,
                    help="Maximum number of tokens for model responses"
                )
                
                batch_size = st.number_input(
                    "Batch Size",
                    min_value=1,
                    max_value=100,
                    value=int(st.session_state.settings.get('batch_size', 10)),
                    step=1,
                    help="Number of items to process in each batch"
                )
            
            # Save button with modern styling
            col1, col2 = st.columns([1, 2])
            with col1:
                submitted = st.form_submit_button("💾 Save Settings", use_container_width=True)
            
            if submitted:
                settings = {
                    "api_key": api_key,
                    "environment": environment,
                    "model": model,
                    "temperature": temperature,
                    "theme": theme,
                    "max_tokens": max_tokens,
                    "batch_size": batch_size
                }
                
                # Save settings and apply theme
                save_settings(settings)
                st.success("✅ Settings saved successfully!")
                
                # Rerun to apply theme changes immediately
                st.rerun()
    
    # Apply theme on initial load if not already applied
    if 'settings' in st.session_state and st.session_state.settings.get('theme'):
        apply_theme(st.session_state.settings['theme'])
