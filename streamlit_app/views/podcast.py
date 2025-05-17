import streamlit as st
import os
from datetime import datetime
from api_utils import make_api_request, APIError
from typing import Dict, Any, List
import pandas as pd

def show_podcast_page():
    st.title("🎙️ Podcast Builder")
    
    # Add modern card styling
    st.markdown("""
        <style>
            div[data-testid="stForm"] {
                background: white;
                padding: 2rem;
                border-radius: 10px;
                box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
                margin-bottom: 1rem;
            }
            div[data-testid="stExpander"] {
                background: white;
                border-radius: 10px;
                box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
                margin-bottom: 1rem;
            }
            .stAudio {
                margin: 1rem 0;
            }
            .stProgress {
                margin: 1rem 0;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'podcast_episodes' not in st.session_state:
        st.session_state.podcast_episodes = []
    
    # Podcast Configuration
    with st.container():
        cols = st.columns([2, 1])
        
        with cols[0]:
            st.subheader("Episode Details")
            with st.form("podcast_config"):
                title = st.text_input("Episode Title", placeholder="Enter an engaging title...")
                description = st.text_area("Episode Description", placeholder="Brief description of this episode...")
                
                cols2 = st.columns(2)
                with cols2[0]:
                    episode_number = st.number_input("Episode Number", min_value=1, value=1)
                with cols2[1]:
                    duration = st.slider("Target Duration (minutes)", 5, 60, 15)
                
                cols3 = st.columns(2)
                with cols3[0]:
                    voice = st.selectbox(
                        "Voice",
                        ["en-US-Wavenet-D", "en-US-Wavenet-C", "en-US-Standard-D"],
                        index=0
                    )
                with cols3[1]:
                    speaking_rate = st.slider(
                        "Speaking Rate",
                        min_value=0.5,
                        max_value=2.0,
                        value=1.0,
                        step=0.1
                    )
                
                submitted = st.form_submit_button("Save Configuration", use_container_width=True)
                if submitted:
                    st.success("✅ Episode configuration saved!")
        
        with cols[1]:
            st.subheader("Quick Actions")
            if st.button("🎧 Preview Audio", use_container_width=True):
                st.info("Generating audio preview...")
            if st.button("📤 Export Episode", use_container_width=True):
                st.info("Exporting episode...")
            if st.button("🎵 Add Background Music", use_container_width=True):
                st.info("Opening music library...")
    
    # Content Builder
    st.subheader("Content Builder")
    
    # Add new segment
    with st.expander("➕ Add New Segment", expanded=True):
        with st.form("add_segment"):
            segment_type = st.selectbox(
                "Segment Type",
                ["Paper Review", "News Update", "Interview", "Research Highlight"]
            )
            
            segment_title = st.text_input("Segment Title")
            segment_script = st.text_area("Script", height=150)
            
            cols4 = st.columns([1, 1, 1])
            with cols4[0]:
                priority = st.slider("Priority", 1, 5, 3)
            with cols4[1]:
                time_limit = st.number_input("Time Limit (seconds)", 30, 600, 120)
            with cols4[2]:
                add_jingle = st.checkbox("Add Transition Jingle")
            
            if st.form_submit_button("Add Segment", use_container_width=True):
                new_segment = {
                    "type": segment_type,
                    "title": segment_title,
                    "script": segment_script,
                    "priority": priority,
                    "time_limit": time_limit,
                    "add_jingle": add_jingle
                }
                st.session_state.podcast_episodes.append(new_segment)
                st.success("✅ Segment added successfully!")
    
    # Display existing segments
    if st.session_state.podcast_episodes:
        st.subheader("Episode Segments")
        for i, segment in enumerate(st.session_state.podcast_episodes):
            with st.expander(f"{segment['type']}: {segment['title']}", expanded=False):
                st.write(f"**Script:** {segment['script']}")
                st.write(f"**Priority:** {'🎯' * segment['priority']}")
                st.write(f"**Time Limit:** {segment['time_limit']} seconds")
                st.write(f"**Transition Jingle:** {'Yes' if segment['add_jingle'] else 'No'}")
                
                # Audio preview placeholder
                st.audio("https://www.example.com/sample.mp3", format='audio/mp3')
                
                cols5 = st.columns([1, 1, 1])
                with cols5[0]:
                    if st.button("✏️ Edit", key=f"edit_{i}", use_container_width=True):
                        st.session_state.editing_segment = i
                with cols5[1]:
                    if st.button("🎵 Add Music", key=f"music_{i}", use_container_width=True):
                        st.info("Opening music selector...")
                with cols5[2]:
                    if st.button("🗑️ Delete", key=f"delete_{i}", use_container_width=True):
                        st.session_state.podcast_episodes.pop(i)
                        st.rerun()
    else:
        st.info("No segments added yet. Use the form above to add your first segment!")
