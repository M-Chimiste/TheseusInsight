import streamlit as st
import os
import json
from typing import Dict, Any, List

# Import API client
from streamlit_app import api_client

# Constants for model types
MODEL_TYPES = ["ollama", "gemini", "openai", "anthropic", "llamacpp", "sentence-transformers"]

# Load arxiv taxonomy (still needed for UI display of category names)
# This path should be relative to the project root if possible, or adjusted.
# For now, assuming it works as is when Streamlit is run from project root.
ARXIV_TAXONOMY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "arxiv_taxonomy.json")
if os.path.exists(ARXIV_TAXONOMY_PATH):
    with open(ARXIV_TAXONOMY_PATH, 'r') as f:
        ARXIV_TAXONOMY = json.load(f)
else:
    ARXIV_TAXONOMY = {} # Fallback if not found
    st.error(f"Could not load ArXiv Taxonomy from {ARXIV_TAXONOMY_PATH}")

# Load orchestration config
ORCHESTRATION_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "orchestration.json")
if os.path.exists(ORCHESTRATION_CONFIG_PATH):
    with open(ORCHESTRATION_CONFIG_PATH, 'r') as f:
        ORCHESTRATION_CONFIG = json.load(f)
else:
    ORCHESTRATION_CONFIG = {}

def get_theme_setting():
    """Get theme setting from session state or default to System."""
    if 'theme' in st.session_state:
        return st.session_state.theme
    return 'System'

def set_theme_setting(theme: str):
    """Set theme setting in session state."""
    st.session_state.theme = theme

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
                .stExpander {
                    background-color: var(--card-bg) !important;
                    border-color: var(--border-color) !important;
                }
                /* Toggle label color */
                p, span, label, .stMarkdown, div[data-testid="stVerticalBlock"] div {
                    color: var(--text-primary) !important;
                }
                /* Toggle switch color */
                .stToggle > div > div {
                    background-color: var(--bg-secondary) !important;
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
                /* Toggle label color */
                p, span, label, .stMarkdown, div[data-testid="stVerticalBlock"] div {
                    color: var(--text-primary) !important;
                }
                /* Toggle switch color */
                .stToggle > div > div {
                    background-color: var(--bg-secondary) !important;
                }
            </style>
        """, unsafe_allow_html=True)
    # For 'System', we'll let the OS preference take over via the media query

# Helper function to populate model config UI and collect data
def render_model_config_ui(model_key: str, config_data: Dict[str, Any], available_providers: List[str], form_key_prefix: str) -> Dict[str, Any]:
    """Renders UI for a single model config and returns its current state from UI.
    Args:
        model_key: Identifier for the model role (e.g., 'embedding_model', 'judge_model').
        config_data: The current configuration dictionary for this model.
        available_providers: List of provider names (e.g., ['ollama', 'openai']).
        form_key_prefix: Unique prefix for Streamlit widget keys.
    Returns:
        A dictionary representing the model's configuration as set in the UI.
    """
    ui_state = {}

    col1, col2 = st.columns(2)
    with col1:
        ui_state['model_name'] = st.text_input(
            "Model Name",
            value=config_data.get('model_name', ''),
            help=f"Name of the {model_key.replace('_', ' ')}",
            key=f"{form_key_prefix}_model_name"
        )
        
        current_type = config_data.get('model_type', available_providers[0] if available_providers else '')
        type_index = 0
        if current_type in available_providers:
            type_index = available_providers.index(current_type)
        
        ui_state['model_type'] = st.selectbox(
            "Model Type (Provider)",
            available_providers,
            index=type_index,
            help=f"Type of the {model_key.replace('_', ' ')}",
            key=f"{form_key_prefix}_model_type"
        )

    with col2:
        # Common parameters for most generative models
        if model_key != "embedding_model": # Embedding models might not have these
            ui_state['max_new_tokens'] = st.number_input(
                "Max New Tokens",
                min_value=100,
                max_value=131072, # Increased upper bound
                value=int(config_data.get('max_new_tokens', 2048)),
                help="Maximum number of new tokens to generate",
                key=f"{form_key_prefix}_max_tokens"
            )
            
            ui_state['temperature'] = st.number_input(
                "Temperature",
                min_value=0.0,
                max_value=2.0, # Increased upper bound
                value=float(config_data.get('temperature', 0.7)),
                step=0.01,
                format="%.2f",
                help="Temperature for model generation (0.0 to 2.0)",
                key=f"{form_key_prefix}_temperature"
            )
            
            # Only show num_ctx for ollama and llamacpp models (as per previous logic)
            # This can be adjusted if other providers also use it.
            if ui_state['model_type'] in ["ollama", "llamacpp"]:
                ui_state['num_ctx'] = st.number_input(
                    "Context Window Size (num_ctx)",
                    min_value=1024,
                    max_value=131072, # Increased upper bound
                    value=int(config_data.get('num_ctx', 4096)),
                    help="Size of the context window",
                    key=f"{form_key_prefix}_num_ctx"
                )
            else:
                # If not applicable, ensure it's not sent or set to None if API expects it
                ui_state['num_ctx'] = config_data.get('num_ctx') # retain if present but not editable
        
        # Specific to embedding models
        if model_key == "embedding_model":
            ui_state['trust_remote_code'] = st.checkbox(
                "Trust Remote Code",
                value=config_data.get('trust_remote_code', False),
                help="Whether to trust remote code when loading the embedding model",
                key=f"{form_key_prefix}_trust_remote_code"
            )
        else:
            ui_state['trust_remote_code'] = config_data.get('trust_remote_code') # retain if present

    # Ensure all expected fields from ModelConfig Pydantic model are present, even if None
    for field in ['max_new_tokens', 'temperature', 'num_ctx', 'trust_remote_code']:
        if field not in ui_state:
            ui_state[field] = config_data.get(field) # retain original if not in UI for this model type
            
    return ui_state

def show_settings_page():
    st.title("⚙️ Settings")

    # --- Initialize state for holding API data --- #
    if 'settings_orchestration_config' not in st.session_state:
        st.session_state.settings_orchestration_config = None
    if 'settings_arxiv_categories' not in st.session_state:
        st.session_state.settings_arxiv_categories = None
    if 'settings_model_providers' not in st.session_state:
        st.session_state.settings_model_providers = []

    # --- Load data from API --- #
    # Only load once or if forced by a refresh button (not implemented here)
    if st.session_state.settings_orchestration_config is None: # Check if already loaded
        try:
            st.session_state.settings_orchestration_config = api_client.get_orchestration_config()
            st.session_state.settings_arxiv_categories = api_client.get_arxiv_categories()
            providers_data = api_client.get_model_providers()
            st.session_state.settings_model_providers = [p['name'] for p in providers_data] if providers_data else []
        except api_client.APIClientError as e:
            st.error(f"Failed to load settings from API: {str(e)} (Details: {e.details})")
            # Prevent further rendering of settings UI if critical data is missing
            return 
    
    # Retrieve loaded data from session state
    orchestration_config = st.session_state.settings_orchestration_config
    arxiv_categories_config = st.session_state.settings_arxiv_categories
    model_provider_names = st.session_state.settings_model_providers

    if not orchestration_config or not arxiv_categories_config: # Check if loading failed
        st.warning("Configurations could not be loaded. Please try again later.")
        return

    # Initialize theme settings in session state if not present (UI specific, keep as is)
    if 'theme' not in st.session_state:
        st.session_state.theme = 'System'
    
    # Theme selection at the top
    st.subheader("Display Settings")
    
    # Initialize theme state if not present
    if 'theme' not in st.session_state:
        st.session_state.theme = 'System'
    
    # Simple dark mode toggle
    dark_mode = st.toggle(
        "Dark Mode",
        value=st.session_state.theme,
        help="Toggle dark mode on/off"
    )
    
    # Set theme based on toggle
    theme = 'Dark' if dark_mode else 'Light'
    
    # Update theme immediately when changed
    if theme != st.session_state.theme:
        set_theme_setting(theme)
        apply_theme(theme)
    
    st.markdown("---")
    
    # Newsletter Settings (Collapsible)
    with st.expander("📰 Newsletter Model Settings", expanded=True):
        st.markdown("### Model Configuration")
        st.markdown("Configure the models used for different aspects of newsletter generation.")
        
        model_keys_titles = {
            "embedding_model": "Embedding Model",
            "judge_model": "Judge Model",
            "content_extraction_model": "Content Extraction Model",
            "newsletter_sections_model": "Newsletter Sections Model",
            "newsletter_intro_model": "Newsletter Intro Model"
        }
        model_tabs = st.tabs([title for title in model_keys_titles.values()])
        
        current_orchestration_data_ui = {} # To store UI state for all models

        for i, (model_key, tab_title) in enumerate(model_keys_titles.items()):
            with model_tabs[i]:
                st.subheader(f"{tab_title} Configuration")
                # Get the specific model's config from the larger orchestration_config
                current_model_cfg_data = orchestration_config.get(model_key, {})
                
                # Render UI and get back the state from the UI
                ui_model_state = render_model_config_ui(
                    model_key,
                    current_model_cfg_data,
                    model_provider_names,
                    form_key_prefix=f"settings_{model_key}"
                )
                current_orchestration_data_ui[model_key] = ui_model_state

        if st.button("Save All Model Settings", key="save_all_models"):
            # Construct the full orchestration config payload from UI states
            payload = orchestration_config.copy() # Start with original to preserve other fields
            for model_key, ui_data in current_orchestration_data_ui.items():
                payload[model_key] = ui_data
            
            try:
                response = api_client.update_orchestration_config(payload)
                st.success("✅ Model settings saved successfully via API!")
                # Update session state with the new config (API might return the saved object)
                st.session_state.settings_orchestration_config = api_client.get_orchestration_config() # Re-fetch to be sure
                st.rerun()
            except api_client.APIClientError as e:
                st.error(f"Failed to save model settings: {str(e)} (Details: {e.details})")

    # Data Source Settings (Collapsible)
    with st.expander("🔍 Data Source Settings", expanded=True):
        st.markdown("### ArXiv Settings")
        st.markdown("Configure the ArXiv categories to use for paper selection.")
        
        # Use arxiv_categories_config fetched from API
        current_main_arxiv_cat = arxiv_categories_config.get('main_category', 'cs')
        current_filter_arxiv_cats = arxiv_categories_config.get('filter_categories', [])

        main_categories_from_taxonomy = list(ARXIV_TAXONOMY.get('main_categories', {}).keys())
        
        main_category_ui = st.selectbox(
            "Main Category",
            main_categories_from_taxonomy,
            index=main_categories_from_taxonomy.index(current_main_arxiv_cat) if current_main_arxiv_cat in main_categories_from_taxonomy else 0,
            format_func=lambda x: f"{x} - {ARXIV_TAXONOMY.get('main_categories', {}).get(x, '')}",
            help="Select the main ArXiv category to search in",
            key="main_category_arxiv_ui"
        )
        
        selected_subcategories_ui = []
        if main_category_ui in ARXIV_TAXONOMY:
            subcategories = list(ARXIV_TAXONOMY[main_category_ui].keys())
            subcategory_options = [f"{main_category_ui}.{sub}" for sub in subcategories]
            
            def format_subcategory(sub_key):
                if '.' in sub_key:
                    main_c, sub_c = sub_key.split('.', 1) # Split only on the first dot
                    if main_c in ARXIV_TAXONOMY and sub_c in ARXIV_TAXONOMY[main_c]:
                         return f"{sub_key} - {ARXIV_TAXONOMY[main_c].get(sub_c, '')}"
                return sub_key
            
            # Determine valid defaults for multiselect based on current main_category_ui and fetched filters
            valid_defaults_for_multiselect = []
            if main_category_ui.lower() == current_main_arxiv_cat.lower(): # Only use defaults if main cat matches fetched
                for filt_cat in current_filter_arxiv_cats:
                    if filt_cat.startswith(main_category_ui + ".") and filt_cat in subcategory_options:
                        valid_defaults_for_multiselect.append(filt_cat)
            
            selected_subcategories_ui = st.multiselect(
                "Subcategories",
                options=subcategory_options,
                default=valid_defaults_for_multiselect,
                format_func=format_subcategory,
                help="Select the subcategories to filter papers by",
                key="subcategories_arxiv_ui"
            )
        else:
            st.warning(f"No subcategories found in taxonomy for {main_category_ui}.")
            
        if st.button("Save ArXiv Settings", key="save_arxiv_api"):
            arxiv_payload = {
                "main_category": main_category_ui.lower(),
                "filter_categories": [sub.lower() for sub in selected_subcategories_ui]
            }
            try:
                response = api_client.update_arxiv_categories(arxiv_payload)
                st.success("✅ ArXiv settings saved successfully via API!")
                st.session_state.settings_arxiv_categories = api_client.get_arxiv_categories() # Re-fetch
                st.rerun()
            except api_client.APIClientError as e:
                st.error(f"Failed to save ArXiv settings: {str(e)} (Details: {e.details})")
            
        st.markdown("### Current ArXiv Settings (from API)")
        st.json(arxiv_categories_config) # Display the fetched config
    
    # Apply theme on initial load if not already applied
    apply_theme(st.session_state.theme) # Theme logic remains UI-side
