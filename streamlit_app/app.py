import streamlit as st
import sys
import os
from dotenv import load_dotenv
from styles.css import apply_all_styles

# Ensure the root directory is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir) # This assumes app.py is in streamlit_app, which is in project_root
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

# Configure the page
st.set_page_config(
    page_title="Theseus Insight",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Create a placeholder for theme styles
theme_style_placeholder = st.empty()

# Apply all custom CSS
st.markdown(apply_all_styles(), unsafe_allow_html=True)

# Apply theme from settings if set
if 'settings' in st.session_state and st.session_state.settings.get('theme'):
    from views.settings import apply_theme
    apply_theme(theme_style_placeholder, st.session_state.settings['theme'])

# Initialize session state
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Settings"

# Initialize settings if not present
if 'settings' not in st.session_state:
    st.session_state.settings = {
        'theme': 'Dark',  # Changed default theme from 'System' to 'Dark'
        'api_key': os.getenv("API_KEY", ""),
        'environment': 'Development',
        'model': 'GPT-4',
        'temperature': 0.7,
        'max_tokens': 2000,
        'batch_size': 10
    }

def render_navigation():
    with st.sidebar:
        st.markdown("""
            <div style='text-align: center; padding: 1rem;'>
                <h2 style='color: #000;'>🔬 Theseus Insight</h2>
            </div>
        """, unsafe_allow_html=True)

        nav_pages = {
            "⚙️ Settings": "Settings",
            "📰 Newsletter Builder": "Newsletter Builder",
            "🎙️ Podcast Creator": "Podcast Creator",
        }

        for label, page in nav_pages.items():
            if st.button(label, key=f"nav_{page}"):
                st.session_state.current_page = page
                st.rerun()

# Render navigation
render_navigation()

# Load the appropriate page
if st.session_state.current_page == "Settings":
    from views.settings import show_settings_page
    show_settings_page()
elif st.session_state.current_page == "Newsletter Builder":
    from views.newsletter import show_newsletter_page
    show_newsletter_page()
elif st.session_state.current_page == "Podcast Creator":
    from views.podcast import show_podcast_creator_page
    show_podcast_creator_page()