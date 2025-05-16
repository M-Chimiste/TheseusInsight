import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from app import make_api_request, APIError

def show_papers_page():
    st.title("📄 Paper Ratings")
    
    # Initialize session state for filters and pagination
    if 'papers_page' not in st.session_state:
        st.session_state.papers_page = 1
    if 'papers_filters' not in st.session_state:
        st.session_state.papers_filters = {
            'search': '',
            'min_score': 0.0,
            'max_score': 10.0,
            'start_date': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            'end_date': datetime.now().strftime('%Y-%m-%d'),
            'sort_by': 'date',
            'sort_order': 'desc',
            'page_size': 20
        }
    
    # Sidebar filters
    with st.sidebar:
        st.header("🔍 Filters")
        
        # Search
        search_query = st.text_input(
            "Search papers",
            value=st.session_state.papers_filters['search'],
            placeholder="Title, abstract, or author"
        )
        
        # Score range
        st.subheader("Score Range")
        min_score, max_score = st.slider(
            "Select score range",
            min_value=0.0,
            max_value=10.0,
            value=(
                st.session_state.papers_filters['min_score'],
                st.session_state.papers_filters['max_score']
            ),
            step=0.1,
            format="%.1f"
        )
        
        # Date range
        st.subheader("Date Range")
        date_range = st.selectbox(
            "Select date range",
            ["Last 7 days", "Last 30 days", "Last 90 days", "Last year", "Custom"],
            index=1
        )
        
        if date_range == "Custom":
            start_date = st.date_input(
                "From",
                value=datetime.strptime(st.session_state.papers_filters['start_date'], '%Y-%m-%d')
            )
            end_date = st.date_input(
                "To",
                value=datetime.strptime(st.session_state.papers_filters['end_date'], '%Y-%m-%d')
            )
        else:
            days = {
                "Last 7 days": 7,
                "Last 30 days": 30,
                "Last 90 days": 90,
                "Last year": 365
            }[date_range]
            start_date = datetime.now() - timedelta(days=days)
            end_date = datetime.now()
        
        # Sorting
        st.subheader("Sorting")
        sort_by = st.selectbox(
            "Sort by",
            ["Date", "Score", "Title"],
            index=["date", "score", "title"].index(st.session_state.papers_filters['sort_by'])
        )
        sort_order = st.selectbox(
            "Sort order",
            ["Descending", "Ascending"],
            index=0 if st.session_state.papers_filters['sort_order'] == 'desc' else 1
        )
        
        # Page size
        page_size = st.selectbox(
            "Items per page",
            [10, 20, 50, 100],
            index=[10, 20, 50, 100].index(st.session_state.papers_filters['page_size'])
        )
        
        # Apply filters button
        if st.button("Apply Filters"):
            st.session_state.papers_filters.update({
                'search': search_query,
                'min_score': min_score,
                'max_score': max_score,
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'sort_by': sort_by.lower(),
                'sort_order': 'desc' if sort_order == 'Descending' else 'asc',
                'page_size': page_size
            })
            st.session_state.papers_page = 1
    
    # Display papers
    try:
        # Prepare query parameters
        params = {
            'page': st.session_state.papers_page,
            'page_size': st.session_state.papers_filters['page_size'],
            'search': st.session_state.papers_filters['search'],
            'min_score': st.session_state.papers_filters['min_score'],
            'max_score': st.session_state.papers_filters['max_score'],
            'start_date': st.session_state.papers_filters['start_date'],
            'end_date': st.session_state.papers_filters['end_date'],
            'sort_by': st.session_state.papers_filters['sort_by'],
            'sort_order': st.session_state.papers_filters['sort_order']
        }
        
        # Fetch papers from API
        response = make_api_request("GET", "/papers", params=params)
        
        if not response or 'items' not in response:
            st.warning("No papers found matching your criteria.")
            return
        
        papers = response['items']
        total_pages = response.get('total_pages', 1)
        
        # Display papers count
        st.write(f"Found {response.get('total', 0)} papers")
        
        # Display each paper
        for paper in papers:
            with st.expander(f"{paper.get('title', 'Untitled')} ({paper.get('score', 0):.1f}★)"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    # Display paper details
                    authors = ", ".join(paper.get('authors', []))
                    st.write(f"**Authors:** {authors}")
                    
                    # Display abstract with a max height and scroll
                    st.write("**Abstract:**")
                    st.write(
                        f"<div style='max-height: 150px; overflow-y: auto; padding: 5px; border: 1px solid #e0e0e0; border-radius: 5px;'>"
                        f"{paper.get('abstract', 'No abstract available.')}"
                        "</div>",
                        unsafe_allow_html=True
                    )
                    
                    # Display metadata
                    col_meta1, col_meta2, col_meta3 = st.columns(3)
                    with col_meta1:
                        st.caption(f"**Published:** {paper.get('published_date', 'N/A')}")
                    with col_meta2:
                        st.caption(f"**Updated:** {paper.get('updated_date', 'N/A')}")
                    with col_meta3:
                        st.caption(f"**Categories:** {', '.join(paper.get('categories', []))}")
                    
                    # Display links
                    if 'url' in paper or 'pdf_url' in paper:
                        st.write("**Links:**")
                        link_cols = st.columns(3)
                        if 'url' in paper:
                            link_cols[0].markdown(f"[📄 Paper]({paper['url']})")
                        if 'pdf_url' in paper:
                            link_cols[1].markdown(f"[📥 PDF]({paper['pdf_url']})")
                
                with col2:
                    # Display score and actions
                    st.metric("Score", f"{paper.get('score', 0):.1f}")
                    
                    # Action buttons
                    if st.button("📰 Add to Newsletter", key=f"add_{paper.get('id')}"):
                        # In a real app, this would add the paper to a newsletter
                        st.session_state.newsletter_papers = st.session_state.get('newsletter_papers', set())
                        st.session_state.newsletter_papers.add(paper['id'])
                        st.success(f"Added to newsletter selection")
                    
                    if st.button("🎙️ Create Podcast", key=f"podcast_{paper.get('id')}"):
                        # This would pre-fill the podcast creation form
                        st.session_state.podcast_source = f"paper:{paper['id']}"
                        st.experimental_rerun()
        
        # Pagination controls
        if total_pages > 1:
            st.write("---")
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col1:
                if st.session_state.papers_page > 1:
                    if st.button("← Previous"):
                        st.session_state.papers_page -= 1
                        st.experimental_rerun()
            
            with col2:
                st.write(f"Page {st.session_state.papers_page} of {total_pages}")
            
            with col3:
                if st.session_state.papers_page < total_pages:
                    if st.button("Next →"):
                        st.session_state.papers_page += 1
                        st.experimental_rerun()
    
    except APIError as e:
        st.error(f"Error loading papers: {e}")
    
    # Debug info (can be removed in production)
    if st.sidebar.checkbox("Show debug info"):
        st.sidebar.json(st.session_state.papers_filters)
