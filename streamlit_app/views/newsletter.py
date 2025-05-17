import streamlit as st
from datetime import datetime, timedelta
from api_utils import make_api_request, APIError
import json
from typing import List, Dict, Any
import pandas as pd

def show_newsletter_page():
    st.title("📰 Newsletter Builder")
    
    # Initialize session state for newsletter content
    if 'newsletter_sections' not in st.session_state:
        st.session_state.newsletter_sections = []
    
    # Newsletter Configuration
    with st.container():
        cols = st.columns([2, 1])
        
        with cols[0]:
            st.subheader("Newsletter Details")
            with st.form("newsletter_config"):
                title = st.text_input("Newsletter Title", placeholder="Enter a catchy title...")
                description = st.text_area("Description", placeholder="Brief description of this newsletter issue...")
                
                cols2 = st.columns(2)
                with cols2[0]:
                    issue_number = st.number_input("Issue Number", min_value=1, value=1)
                with cols2[1]:
                    publication_date = st.date_input("Publication Date")
                
                submitted = st.form_submit_button("Save Configuration", use_container_width=True)
                if submitted:
                    st.success("✅ Newsletter configuration saved!")
        
        with cols[1]:
            st.subheader("Quick Actions")
            if st.button("📝 Preview Newsletter", use_container_width=True):
                st.info("Generating preview...")
            if st.button("📤 Export to HTML", use_container_width=True):
                st.info("Exporting...")
            if st.button("📧 Send Test Email", use_container_width=True):
                st.info("Sending test email...")
    
    # Content Builder
    st.subheader("Content Builder")
    
    # Add new section
    with st.expander("➕ Add New Section", expanded=True):
        with st.form("add_section"):
            section_type = st.selectbox(
                "Section Type",
                ["Featured Papers", "Industry News", "Research Highlights", "Upcoming Events"]
            )
            
            section_title = st.text_input("Section Title")
            section_content = st.text_area("Content", height=150)
            
            cols3 = st.columns([1, 1, 1])
            with cols3[0]:
                importance = st.slider("Importance", 1, 5, 3)
            with cols3[1]:
                word_limit = st.number_input("Word Limit", 50, 500, 200)
            with cols3[2]:
                include_images = st.checkbox("Include Images")
            
            if st.form_submit_button("Add Section", use_container_width=True):
                new_section = {
                    "type": section_type,
                    "title": section_title,
                    "content": section_content,
                    "importance": importance,
                    "word_limit": word_limit,
                    "include_images": include_images
                }
                st.session_state.newsletter_sections.append(new_section)
                st.success("✅ Section added successfully!")
    
    # Display existing sections
    if st.session_state.newsletter_sections:
        st.subheader("Current Sections")
        for i, section in enumerate(st.session_state.newsletter_sections):
            with st.expander(f"{section['type']}: {section['title']}", expanded=False):
                st.write(f"**Content:** {section['content']}")
                st.write(f"**Importance:** {'⭐' * section['importance']}")
                st.write(f"**Word Limit:** {section['word_limit']} words")
                st.write(f"**Images:** {'Yes' if section['include_images'] else 'No'}")
                
                cols4 = st.columns([1, 1])
                with cols4[0]:
                    if st.button("✏️ Edit", key=f"edit_{i}", use_container_width=True):
                        st.session_state.editing_section = i
                with cols4[1]:
                    if st.button("🗑️ Delete", key=f"delete_{i}", use_container_width=True):
                        st.session_state.newsletter_sections.pop(i)
                        st.rerun()
    else:
        st.info("No sections added yet. Use the form above to add your first section!")
