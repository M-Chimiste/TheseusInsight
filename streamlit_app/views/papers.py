import streamlit as st
import pandas as pd
from typing import Dict, Any, List

def show_papers_page():
    st.title("📄 Paper Ratings")
    
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
            .element-container iframe {
                border-radius: 10px;
            }
            div[data-testid="stDataFrame"] > div {
                border-radius: 10px;
                box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'papers' not in st.session_state:
        st.session_state.papers = []
    
    # Paper Management
    with st.container():
        cols = st.columns([2, 1])
        
        with cols[0]:
            st.subheader("Add New Paper")
            with st.form("paper_form"):
                title = st.text_input("Paper Title", placeholder="Enter the paper title...")
                authors = st.text_input("Authors", placeholder="Enter authors (comma-separated)...")
                
                cols2 = st.columns(2)
                with cols2[0]:
                    arxiv_id = st.text_input("ArXiv ID", placeholder="e.g., 2103.00001")
                with cols2[1]:
                    publication_date = st.date_input("Publication Date")
                
                abstract = st.text_area("Abstract", height=100)
                
                cols3 = st.columns(3)
                with cols3[0]:
                    rating = st.slider("Rating", 1, 5, 3)
                with cols3[1]:
                    category = st.selectbox(
                        "Category",
                        ["Machine Learning", "Natural Language Processing", "Computer Vision", "Robotics", "Other"]
                    )
                with cols3[2]:
                    read_status = st.selectbox("Status", ["Unread", "Reading", "Completed", "Archived"])
                
                submitted = st.form_submit_button("Add Paper", use_container_width=True)
                if submitted:
                    new_paper = {
                        "title": title,
                        "authors": [a.strip() for a in authors.split(",")],
                        "arxiv_id": arxiv_id,
                        "publication_date": publication_date.strftime("%Y-%m-%d"),
                        "abstract": abstract,
                        "rating": rating,
                        "category": category,
                        "status": read_status
                    }
                    st.session_state.papers.append(new_paper)
                    st.success("✅ Paper added successfully!")
        
        with cols[1]:
            st.subheader("Quick Actions")
            if st.button("📥 Import Papers", use_container_width=True):
                st.info("Opening import dialog...")
            if st.button("📤 Export Library", use_container_width=True):
                st.info("Preparing export...")
            if st.button("🔄 Sync with Zotero", use_container_width=True):
                st.info("Syncing with Zotero...")
    
    # Paper Library
    st.subheader("Paper Library")
    
    # Filters
    with st.expander("🔍 Filters", expanded=True):
        cols4 = st.columns(4)
        with cols4[0]:
            filter_category = st.multiselect(
                "Category",
                ["Machine Learning", "Natural Language Processing", "Computer Vision", "Robotics", "Other"]
            )
        with cols4[1]:
            filter_status = st.multiselect(
                "Status",
                ["Unread", "Reading", "Completed", "Archived"]
            )
        with cols4[2]:
            min_rating = st.number_input("Min Rating", 1, 5, 1)
        with cols4[3]:
            sort_by = st.selectbox(
                "Sort By",
                ["Date", "Rating", "Title"]
            )
    
    # Display papers
    if st.session_state.papers:
        df = pd.DataFrame(st.session_state.papers)
        
        # Apply filters
        if filter_category:
            df = df[df['category'].isin(filter_category)]
        if filter_status:
            df = df[df['status'].isin(filter_status)]
        df = df[df['rating'] >= min_rating]
        
        # Sort
        if sort_by == "Date":
            df = df.sort_values('publication_date', ascending=False)
        elif sort_by == "Rating":
            df = df.sort_values('rating', ascending=False)
        else:  # Title
            df = df.sort_values('title')
        
        # Display as cards
        for _, paper in df.iterrows():
            with st.expander(f"{paper['title']} ({'⭐' * paper['rating']})", expanded=False):
                cols5 = st.columns([3, 1])
                with cols5[0]:
                    st.write(f"**Authors:** {', '.join(paper['authors'])}")
                    st.write(f"**Abstract:** {paper['abstract']}")
                    st.write(f"**Category:** {paper['category']}")
                    st.write(f"**Status:** {paper['status']}")
                with cols5[1]:
                    st.write(f"**ArXiv:** [{paper['arxiv_id']}](https://arxiv.org/abs/{paper['arxiv_id']})")
                    st.write(f"**Published:** {paper['publication_date']}")
                    
                    cols6 = st.columns(2)
                    with cols6[0]:
                        if st.button("✏️ Edit", key=f"edit_{paper['arxiv_id']}", use_container_width=True):
                            st.session_state.editing_paper = paper['arxiv_id']
                    with cols6[1]:
                        if st.button("🗑️ Delete", key=f"delete_{paper['arxiv_id']}", use_container_width=True):
                            st.session_state.papers = [p for p in st.session_state.papers if p['arxiv_id'] != paper['arxiv_id']]
                            st.rerun()
    else:
        st.info("No papers in your library yet. Add your first paper using the form above!")
