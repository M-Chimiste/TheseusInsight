import streamlit as st
import os
import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from contextlib import contextmanager

# Constants for model types
MODEL_TYPES = ["ollama", "gemini", "openai", "anthropic", "llamacpp"]

# Database path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "theseus.db")

# Load arxiv taxonomy
ARXIV_TAXONOMY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "arxiv_taxonomy.json")
with open(ARXIV_TAXONOMY_PATH, 'r') as f:
    ARXIV_TAXONOMY = json.load(f)

# Load orchestration config
ORCHESTRATION_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "orchestration.json")
with open(ORCHESTRATION_CONFIG_PATH, 'r') as f:
    ORCHESTRATION_CONFIG = json.load(f)

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

def show_settings_page():
    st.title("⚙️ Settings")
    
    # Initialize theme settings in session state if not present
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
        value=st.session_state.theme == 'Dark',  # On if theme is Dark
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
        
        # Create tabs for different model settings
        model_tabs = st.tabs(["Embedding Model", "Judge Model", "Content Extraction", "Newsletter Sections", "Newsletter Intro"])
        
        # 1. Embedding Model Tab
        with model_tabs[0]:
            embedding_config = ORCHESTRATION_CONFIG.get('embedding_model', {})
            
            col1, col2 = st.columns(2)
            with col1:
                embedding_model_name = st.text_input(
                    "Model Name",
                    value=embedding_config.get('model_name', 'Alibaba-NLP/gte-modernbert-base'),
                    help="Name of the embedding model",
                    key="embedding_model_name"
                )
            
            with col2:
                trust_remote_code = st.checkbox(
                    "Trust Remote Code",
                    value=embedding_config.get('trust_remote_code', True),
                    help="Whether to trust remote code when loading the model",
                    key="embedding_trust_remote_code"
                )
            
            # Save button for embedding model
            if st.button("Save Embedding Model Settings", key="save_embedding"):
                updated_config = ORCHESTRATION_CONFIG.copy()
                updated_config['embedding_model'] = {
                    "model_name": embedding_model_name,
                    "model_type": embedding_config.get('model_type', 'sentence-transformers'),
                    "trust_remote_code": trust_remote_code
                }
                
                with open(ORCHESTRATION_CONFIG_PATH, 'w') as f:
                    json.dump(updated_config, f, indent=2)
                
                st.success("✅ Embedding model settings saved successfully!")
                st.rerun()
        
        # 2. Judge Model Tab
        with model_tabs[1]:
            judge_config = ORCHESTRATION_CONFIG.get('judge_model', {})
            
            col1, col2 = st.columns(2)
            with col1:
                judge_model_name = st.text_input(
                    "Model Name",
                    value=judge_config.get('model_name', 'phi4-mini:3.8b-q8_0'),
                    help="Name of the judge model",
                    key="judge_model_name"
                )
                
                judge_model_type = st.selectbox(
                    "Model Type",
                    MODEL_TYPES,
                    index=MODEL_TYPES.index(judge_config.get('model_type', 'ollama')) if judge_config.get('model_type') in MODEL_TYPES else 0,
                    help="Type of the judge model",
                    key="judge_model_type"
                )
            
            with col2:
                judge_max_tokens = st.number_input(
                    "Max New Tokens",
                    min_value=100,
                    max_value=8192,
                    value=int(judge_config.get('max_new_tokens', 512)),
                    help="Maximum number of new tokens to generate",
                    key="judge_max_tokens"
                )
                
                judge_temperature = st.number_input(
                    "Temperature",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(judge_config.get('temperature', 0.1)),
                    step=0.01,
                    format="%.2f",
                    help="Temperature for model generation (0.0 to 1.0)",
                    key="judge_temperature"
                )
                
                # Only show num_ctx for ollama and llamacpp models
                if judge_model_type in ["ollama", "llamacpp"]:
                    judge_num_ctx = st.number_input(
                        "Context Window Size",
                        min_value=1024,
                        max_value=131072,
                        value=int(judge_config.get('num_ctx', 4096)),
                        help="Size of the context window",
                        key="judge_num_ctx"
                    )
                else:
                    judge_num_ctx = judge_config.get('num_ctx', 4096)
            
            # Save button for judge model
            if st.button("Save Judge Model Settings", key="save_judge"):
                updated_config = ORCHESTRATION_CONFIG.copy()
                updated_config['judge_model'] = {
                    "model_name": judge_model_name,
                    "model_type": judge_model_type,
                    "max_new_tokens": judge_max_tokens,
                    "temperature": judge_temperature,
                    "num_ctx": judge_num_ctx
                }
                
                with open(ORCHESTRATION_CONFIG_PATH, 'w') as f:
                    json.dump(updated_config, f, indent=2)
                
                st.success("✅ Judge model settings saved successfully!")
                st.rerun()
        
        # 3. Content Extraction Model Tab
        with model_tabs[2]:
            content_config = ORCHESTRATION_CONFIG.get('content_extraction_model', {})
            
            col1, col2 = st.columns(2)
            with col1:
                content_model_name = st.text_input(
                    "Model Name",
                    value=content_config.get('model_name', 'gemma3:27b-it-qat'),
                    help="Name of the content extraction model",
                    key="content_model_name"
                )
                
                content_model_type = st.selectbox(
                    "Model Type",
                    MODEL_TYPES,
                    index=MODEL_TYPES.index(content_config.get('model_type', 'ollama')) if content_config.get('model_type') in MODEL_TYPES else 0,
                    help="Type of the content extraction model",
                    key="content_model_type"
                )
            
            with col2:
                content_max_tokens = st.number_input(
                    "Max New Tokens",
                    min_value=100,
                    max_value=8192,
                    value=int(content_config.get('max_new_tokens', 4096)),
                    help="Maximum number of new tokens to generate",
                    key="content_max_tokens"
                )
                
                content_temperature = st.number_input(
                    "Temperature",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(content_config.get('temperature', 0.1)),
                    step=0.01,
                    format="%.2f",
                    help="Temperature for model generation (0.0 to 1.0)",
                    key="content_temperature"
                )
                
                # Only show num_ctx for ollama and llamacpp models
                if content_model_type in ["ollama", "llamacpp"]:
                    content_num_ctx = st.number_input(
                        "Context Window Size",
                        min_value=1024,
                        max_value=131072,
                        value=int(content_config.get('num_ctx', 131072)),
                        help="Size of the context window",
                        key="content_num_ctx"
                    )
                else:
                    content_num_ctx = content_config.get('num_ctx', 131072)
            
            # Save button for content extraction model
            if st.button("Save Content Extraction Model Settings", key="save_content"):
                updated_config = ORCHESTRATION_CONFIG.copy()
                updated_config['content_extraction_model'] = {
                    "model_name": content_model_name,
                    "model_type": content_model_type,
                    "max_new_tokens": content_max_tokens,
                    "temperature": content_temperature,
                    "num_ctx": content_num_ctx
                }
                
                with open(ORCHESTRATION_CONFIG_PATH, 'w') as f:
                    json.dump(updated_config, f, indent=2)
                
                st.success("✅ Content extraction model settings saved successfully!")
                st.rerun()
        
        # 4. Newsletter Sections Model Tab
        with model_tabs[3]:
            sections_config = ORCHESTRATION_CONFIG.get('newsletter_sections_model', {})
            
            col1, col2 = st.columns(2)
            with col1:
                sections_model_name = st.text_input(
                    "Model Name",
                    value=sections_config.get('model_name', 'gemma3:27b-it-qat'),
                    help="Name of the newsletter sections model",
                    key="sections_model_name"
                )
                
                sections_model_type = st.selectbox(
                    "Model Type",
                    MODEL_TYPES,
                    index=MODEL_TYPES.index(sections_config.get('model_type', 'ollama')) if sections_config.get('model_type') in MODEL_TYPES else 0,
                    help="Type of the newsletter sections model",
                    key="sections_model_type"
                )
            
            with col2:
                sections_max_tokens = st.number_input(
                    "Max New Tokens",
                    min_value=100,
                    max_value=8192,
                    value=int(sections_config.get('max_new_tokens', 4096)),
                    help="Maximum number of new tokens to generate",
                    key="sections_max_tokens"
                )
                
                sections_temperature = st.number_input(
                    "Temperature",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(sections_config.get('temperature', 0.1)),
                    step=0.01,
                    format="%.2f",
                    help="Temperature for model generation (0.0 to 1.0)",
                    key="sections_temperature"
                )
                
                # Only show num_ctx for ollama and llamacpp models
                if sections_model_type in ["ollama", "llamacpp"]:
                    sections_num_ctx = st.number_input(
                        "Context Window Size",
                        min_value=1024,
                        max_value=131072,
                        value=int(sections_config.get('num_ctx', 131072)),
                        help="Size of the context window",
                        key="sections_num_ctx"
                    )
                else:
                    sections_num_ctx = sections_config.get('num_ctx', 131072)
            
            # Save button for newsletter sections model
            if st.button("Save Newsletter Sections Model Settings", key="save_sections"):
                updated_config = ORCHESTRATION_CONFIG.copy()
                updated_config['newsletter_sections_model'] = {
                    "model_name": sections_model_name,
                    "model_type": sections_model_type,
                    "max_new_tokens": sections_max_tokens,
                    "temperature": sections_temperature,
                    "num_ctx": sections_num_ctx
                }
                
                with open(ORCHESTRATION_CONFIG_PATH, 'w') as f:
                    json.dump(updated_config, f, indent=2)
                
                st.success("✅ Newsletter sections model settings saved successfully!")
                st.rerun()
        
        # 5. Newsletter Intro Model Tab
        with model_tabs[4]:
            intro_config = ORCHESTRATION_CONFIG.get('newsletter_intro_model', {})
            
            col1, col2 = st.columns(2)
            with col1:
                intro_model_name = st.text_input(
                    "Model Name",
                    value=intro_config.get('model_name', 'gemini-2.0-flash'),
                    help="Name of the newsletter intro model",
                    key="intro_model_name"
                )
                
                intro_model_type = st.selectbox(
                    "Model Type",
                    MODEL_TYPES,
                    index=MODEL_TYPES.index(intro_config.get('model_type', 'gemini')) if intro_config.get('model_type') in MODEL_TYPES else 0,
                    help="Type of the newsletter intro model",
                    key="intro_model_type"
                )
            
            with col2:
                intro_max_tokens = st.number_input(
                    "Max New Tokens",
                    min_value=100,
                    max_value=8192,
                    value=int(intro_config.get('max_new_tokens', 4096)),
                    help="Maximum number of new tokens to generate",
                    key="intro_max_tokens"
                )
                
                intro_temperature = st.number_input(
                    "Temperature",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(intro_config.get('temperature', 0.1)),
                    step=0.01,
                    format="%.2f",
                    help="Temperature for model generation (0.0 to 1.0)",
                    key="intro_temperature"
                )
                
                # Only show num_ctx for ollama and llamacpp models
                if intro_model_type in ["ollama", "llamacpp"]:
                    intro_num_ctx = st.number_input(
                        "Context Window Size",
                        min_value=1024,
                        max_value=131072,
                        value=int(intro_config.get('num_ctx', 131072)),
                        help="Size of the context window",
                        key="intro_num_ctx"
                    )
                else:
                    intro_num_ctx = intro_config.get('num_ctx', 131072)
            
            # Save button for newsletter intro model
            if st.button("Save Newsletter Intro Model Settings", key="save_intro"):
                updated_config = ORCHESTRATION_CONFIG.copy()
                updated_config['newsletter_intro_model'] = {
                    "model_name": intro_model_name,
                    "model_type": intro_model_type,
                    "max_new_tokens": intro_max_tokens,
                    "temperature": intro_temperature,
                    "num_ctx": intro_num_ctx
                }
                
                with open(ORCHESTRATION_CONFIG_PATH, 'w') as f:
                    json.dump(updated_config, f, indent=2)
                
                st.success("✅ Newsletter intro model settings saved successfully!")
                st.rerun()
    
    # Data Source Settings (Collapsible)
    with st.expander("🔍 Data Source Settings", expanded=True):
        st.markdown("### ArXiv Settings")
        st.markdown("Configure the ArXiv categories to use for paper selection.")
        
        # Get current arxiv settings
        arxiv_config = ORCHESTRATION_CONFIG.get('arxiv_search_categories', {
            "main_category": "cs",
            "filter_categories": ["cs.ai", "cs.cl", "cs.lg", "cs.ir", "cs.ma", "cs.cv"]
        })
        
        # Main category selection
        main_categories = list(ARXIV_TAXONOMY.get('main_categories', {}).keys())
        current_main = arxiv_config.get('main_category', 'cs')
        
        main_category = st.selectbox(
            "Main Category",
            main_categories,
            index=main_categories.index(current_main) if current_main in main_categories else 0,
            format_func=lambda x: f"{x} - {ARXIV_TAXONOMY.get('main_categories', {}).get(x, '')}",
            help="Select the main ArXiv category to search in",
            key="main_category"
        )
        
        # Get subcategories for the selected main category
        if main_category in ARXIV_TAXONOMY:
            subcategories = list(ARXIV_TAXONOMY[main_category].keys())
            subcategory_options = [f"{main_category}.{sub}" for sub in subcategories]
            
            # Format function to display subcategory with description
            def format_subcategory(sub_key):
                # Extract the subcategory code (after the dot)
                if '.' in sub_key:
                    _, sub_code = sub_key.split('.')
                    return f"{sub_key} - {ARXIV_TAXONOMY[main_category].get(sub_code, '')}"
                return sub_key
            
            # Current selected subcategories
            current_filters = arxiv_config.get('filter_categories', [])
            
            # Convert all current filters to lowercase for case-insensitive comparison
            current_filters_lower = [f.lower() for f in current_filters]
            
            # Generate subcategory options with proper casing
            subcategory_options = [f"{main_category}.{sub}" for sub in subcategories]
            subcategory_options_lower = [opt.lower() for opt in subcategory_options]
            
            # Find valid defaults that exist in the options
            valid_defaults = []
            for filter_item in current_filters_lower:
                if filter_item.startswith(main_category.lower() + "."):
                    # Find the matching option with proper casing
                    if filter_item in subcategory_options_lower:
                        index = subcategory_options_lower.index(filter_item)
                        valid_defaults.append(subcategory_options[index])
            
            # Multi-select for subcategories
            selected_subcategories = st.multiselect(
                "Subcategories",
                options=subcategory_options,
                default=valid_defaults,
                format_func=format_subcategory,
                help="Select the subcategories to filter papers by",
                key="subcategories"
            )
            
            # Save button for arxiv settings
            if st.button("Save ArXiv Settings", key="save_arxiv"):
                # Ensure all subcategories are lowercase and properly formatted
                formatted_subcategories = [sub.lower() for sub in selected_subcategories]
                
                updated_config = ORCHESTRATION_CONFIG.copy()
                updated_config['arxiv_search_categories'] = {
                    "main_category": main_category.lower(),
                    "filter_categories": formatted_subcategories
                }
                
                with open(ORCHESTRATION_CONFIG_PATH, 'w') as f:
                    json.dump(updated_config, f, indent=2)
                
                # Also save to database
                set_setting('arxiv_search_categories', json.dumps({
                    "main_category": main_category.lower(),
                    "filter_categories": formatted_subcategories
                }))
                
                st.success("✅ ArXiv settings saved successfully!")
                st.rerun()
        else:
            st.warning(f"No subcategories found for {main_category}. Please select a different main category.")
            
        # Display current settings
        st.markdown("### Current ArXiv Settings")
        st.json(arxiv_config)
    
    # Apply theme on initial load if not already applied
    apply_theme(st.session_state.theme)
