import streamlit as st
from dotenv import load_dotenv
from styles.css import apply_all_styles
import os

# Load environment variables
load_dotenv()

# Configure the page
st.set_page_config(
    page_title="Theseus Insight",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply all custom CSS
st.markdown(apply_all_styles(), unsafe_allow_html=True)

# Apply theme from settings if set
if 'settings' in st.session_state and st.session_state.settings.get('theme'):
    from views.settings import apply_theme
    apply_theme(st.session_state.settings['theme'])

# Initialize session state
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Settings"

# Initialize settings if not present
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
            "🎙️ Podcast Builder": "Podcast Builder",
            "📄 Paper Ratings": "Paper Ratings",
            "📊 Run Log": "Run Log"
        }

        for label, page in nav_pages.items():
            if st.button(label, key=f"nav_{page}"):
                st.session_state.current_page = page
                st.rerun()

        # Stats section with consistent styling
        st.markdown("---")
        st.markdown("""
            <div class='custom-container'>
                <h4 style='color: #000; margin: 0;'>📈 Quick Stats</h4>
                <div class='stats-grid'>
                    <div class='stat-card'>
                        <div class='stat-value'>25</div>
                        <div class='stat-label'>📄 Papers</div>
                    </div>
                    <div class='stat-card'>
                        <div class='stat-value'>8</div>
                        <div class='stat-label'>✅ Tasks</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Version info with consistent styling
        st.markdown("---")
        st.markdown("""
            <div class='custom-container'>
                <h4 style='color: #000; margin: 0;'>ℹ️ About</h4>
                <p style='color: rgba(0, 0, 0, 0.8); margin-top: 0.5rem;'>
                    Theseus Insight v0.3<br>
                    Research paper analysis and newsletter generation tool
                </p>
            </div>
        """, unsafe_allow_html=True)

# Render navigation
render_navigation()

# Load the appropriate page
if st.session_state.current_page == "Settings":
    from views.settings import show_settings_page
    show_settings_page()
elif st.session_state.current_page == "Newsletter Builder":
    from views.newsletter import show_newsletter_page
    show_newsletter_page()
elif st.session_state.current_page == "Podcast Builder":
    from views.podcast import show_podcast_page
    show_podcast_page()
elif st.session_state.current_page == "Paper Ratings":
    from views.papers import show_papers_page
    show_papers_page()
elif st.session_state.current_page == "Run Log":
    from views.runs import show_runs_page
    show_runs_page()
