import streamlit as st
import os
from typing import Dict, Any
from api_utils import make_api_request, APIError

def show_settings_page():
    st.title("⚙️ Settings")
    
    # Create a modern card-like container for settings
    with st.container():
        with st.form("settings_form"):
            st.subheader("API Configuration")
            
            # API Key input with modern styling
            api_key = st.text_input(
                "API Key",
                type="password",
                value=os.getenv("API_KEY", ""),
                help="Enter your API key for authentication"
            )
            
            # Environment selection
            environment = st.selectbox(
                "Environment",
                ["Development", "Staging", "Production"],
                index=0,
                help="Select the environment for API endpoints"
            )
            
            # Model settings
            st.subheader("Model Settings")
            
            model = st.selectbox(
                "Default Language Model",
                ["GPT-4", "GPT-3.5-Turbo", "Claude-2", "Claude-3"],
                index=0,
                help="Select the default language model for text generation"
            )
            
            temperature = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=1.0,
                value=0.7,
                step=0.1,
                help="Control the randomness of the model's output"
            )
            
            # Display settings
            st.subheader("Display Settings")
            
            theme = st.radio(
                "Theme",
                ["Light", "Dark", "System"],
                horizontal=True,
                help="Choose the application theme"
            )
            
            # Advanced settings in an expander
            with st.expander("Advanced Settings"):
                max_tokens = st.number_input(
                    "Max Tokens",
                    min_value=100,
                    max_value=4000,
                    value=2000,
                    step=100,
                    help="Maximum number of tokens for model responses"
                )
                
                batch_size = st.number_input(
                    "Batch Size",
                    min_value=1,
                    max_value=100,
                    value=10,
                    step=1,
                    help="Number of items to process in each batch"
                )
            
            # Save button with modern styling
            submitted = st.form_submit_button("Save Settings", use_container_width=True)
            
            if submitted:
                # Here you would typically save the settings to a configuration file or database
                st.success("✅ Settings saved successfully!")
                
                # You can store the settings in session state for use across the app
                settings: Dict[str, Any] = {
                    "api_key": api_key,
                    "environment": environment,
                    "model": model,
                    "temperature": temperature,
                    "theme": theme,
                    "max_tokens": max_tokens,
                    "batch_size": batch_size
                }
                st.session_state.settings = settings
