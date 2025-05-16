import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from app import make_api_request, APIError

def format_duration(seconds):
    """Format duration in seconds to human-readable format."""
    if not seconds:
        return "N/A"
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def get_status_badge(status):
    """Get a styled badge for the run status."""
    status_colors = {
        "completed": "green",
        "failed": "red",
        "running": "blue",
        "pending": "orange",
        "cancelled": "gray"
    }
    color = status_colors.get(status.lower(), "gray")
    return f"<span style='color: white; background-color: {color}; padding: 0.2em 0.5em; border-radius: 0.5em; font-size: 0.8em;'>{status.upper()}</span>"

def show_runs_page():
    st.title("📊 Run History")
    
    # Initialize session state for filters and pagination
    if 'runs_page' not in st.session_state:
        st.runs_page = 1
    if 'runs_filters' not in st.session_state:
        st.session_state.runs_filters = {
            'pipeline_type': 'all',
            'status': 'all',
            'start_date': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            'end_date': datetime.now().strftime('%Y-%m-%d'),
            'search': '',
            'page_size': 20
        }
    
    # Sidebar filters
    with st.sidebar:
        st.header("🔍 Filters")
        
        # Pipeline type filter
        pipeline_type = st.selectbox(
            "Pipeline Type",
            ["All", "Newsletter", "Podcast", "Other"],
            index=["all", "newsletter", "podcast", "other"].index(
                st.session_state.runs_filters['pipeline_type']
            )
        )
        
        # Status filter
        status = st.selectbox(
            "Status",
            ["All", "Completed", "Failed", "Running", "Pending", "Cancelled"],
            index=["all", "completed", "failed", "running", "pending", "cancelled"].index(
                st.session_state.runs_filters['status']
            )
        )
        
        # Date range filter
        st.subheader("Date Range")
        date_range = st.selectbox(
            "Select date range",
            ["Last 7 days", "Last 30 days", "Last 90 days", "Custom"],
            index=1
        )
        
        if date_range == "Custom":
            start_date = st.date_input(
                "From",
                value=datetime.strptime(st.session_state.runs_filters['start_date'], '%Y-%m-%d')
            )
            end_date = st.date_input(
                "To",
                value=datetime.strptime(st.session_state.runs_filters['end_date'], '%Y-%m-%d')
            )
        else:
            days = {
                "Last 7 days": 7,
                "Last 30 days": 30,
                "Last 90 days": 90
            }[date_range]
            start_date = datetime.now() - timedelta(days=days)
            end_date = datetime.now()
        
        # Search
        search_query = st.text_input(
            "Search runs",
            value=st.session_state.runs_filters.get('search', ''),
            placeholder="Search by name or ID"
        )
        
        # Page size
        page_size = st.selectbox(
            "Items per page",
            [10, 20, 50, 100],
            index=[10, 20, 50, 100].index(st.session_state.runs_filters.get('page_size', 20))
        )
        
        # Apply filters button
        if st.button("Apply Filters"):
            st.session_state.runs_filters.update({
                'pipeline_type': pipeline_type.lower(),
                'status': status.lower(),
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'search': search_query,
                'page_size': page_size
            })
            st.session_state.runs_page = 1
    
    # Display runs
    try:
        # Prepare query parameters
        params = {
            'page': st.session_state.get('runs_page', 1),
            'page_size': st.session_state.runs_filters['page_size'],
            'pipeline_type': st.session_state.runs_filters['pipeline_type'] if st.session_state.runs_filters['pipeline_type'] != 'all' else None,
            'status': st.session_state.runs_filters['status'] if st.session_state.runs_filters['status'] != 'all' else None,
            'start_date': st.session_state.runs_filters['start_date'],
            'end_date': st.session_state.runs_filters['end_date'],
            'search': st.session_state.runs_filters['search'] or None
        }
        
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        
        # Fetch runs from API
        response = make_api_request("GET", "/runs", params=params)
        
        if not response or 'items' not in response:
            st.warning("No runs found matching your criteria.")
            return
        
        runs = response['items']
        total_pages = response.get('total_pages', 1)
        
        # Display runs count
        st.write(f"Found {response.get('total', 0)} runs")
        
        # Display runs in a table
        for run in runs:
            with st.expander(f"{run.get('name', 'Unnamed Run')} - {run.get('pipeline_type', 'N/A').capitalize()}"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    # Display run details
                    st.write(f"**ID:** {run.get('id')}")
                    st.write(f"**Status:** {get_status_badge(run.get('status', 'unknown'))}", unsafe_allow_html=True)
                    
                    # Display timestamps
                    col_ts1, col_ts2, col_ts3 = st.columns(3)
                    with col_ts1:
                        st.caption(f"**Created:**\n{run.get('created_at', 'N/A')}")
                    with col_ts2:
                        if 'started_at' in run:
                            st.caption(f"**Started:**\n{run['started_at']}")
                    with col_ts3:
                        if 'completed_at' in run:
                            st.caption(f"**Completed:**\n{run['completed_at']}")
                    
                    # Display duration
                    if 'duration' in run:
                        st.caption(f"**Duration:** {format_duration(run['duration'])}")
                    
                    # Display error if failed
                    if run.get('status') == 'failed' and 'error' in run:
                        st.error(f"Error: {run['error']}")
                
                with col2:
                    # Action buttons
                    if run.get('status') == 'completed':
                        if 'output_files' in run and run['output_files']:
                            for i, file in enumerate(run['output_files']):
                                if st.button(f"⬇️ {file.get('name', 'Download')}", key=f"dl_{run['id']}_{i}"):
                                    # In a real app, this would download the file
                                    st.success(f"Would download {file.get('name')}")
                    
                    # View logs button
                    if st.button("📋 View Logs", key=f"logs_{run['id']}"):
                        # In a real app, this would show the logs
                        st.info("Logs would be displayed here in a real implementation.")
                    
                    # Retry button for failed runs
                    if run.get('status') == 'failed':
                        if st.button("🔄 Retry", key=f"retry_{run['id']}"):
                            # In a real app, this would retry the run
                            st.info(f"Would retry run {run['id']}")
                    
                    # Cancel button for running/pending runs
                    if run.get('status') in ['running', 'pending']:
                        if st.button("❌ Cancel", key=f"cancel_{run['id']}"):
                            # In a real app, this would cancel the run
                            st.info(f"Would cancel run {run['id']}")
        
        # Pagination controls
        if total_pages > 1:
            st.write("---")
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col1:
                if st.session_state.runs_page > 1:
                    if st.button("← Previous", key="prev_page"):
                        st.session_state.runs_page -= 1
                        st.experimental_rerun()
            
            with col2:
                st.write(f"Page {st.session_state.runs_page} of {total_pages}")
            
            with col3:
                if st.session_state.runs_page < total_pages:
                    if st.button("Next →", key="next_page"):
                        st.session_state.runs_page += 1
                        st.experimental_rerun()
    
    except APIError as e:
        st.error(f"Error loading runs: {e}")
    
    # Debug info (can be removed in production)
    if st.sidebar.checkbox("Show debug info"):
        st.sidebar.json(st.session_state.runs_filters)
        st.sidebar.json(params if 'params' in locals() else {})
