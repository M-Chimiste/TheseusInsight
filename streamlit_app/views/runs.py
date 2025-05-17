import streamlit as st
import pandas as pd
from typing import Dict, Any, List
from datetime import datetime, timedelta
from api_utils import make_api_request, APIError

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
    st.title("📊 Run Log")
    
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
            div[data-testid="stMetricValue"] {
                font-size: 2rem;
                font-weight: bold;
                color: #2563eb;
            }
            div[data-testid="stDataFrame"] > div {
                border-radius: 10px;
                box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'runs' not in st.session_state:
        st.session_state.runs = []
    
    # Dashboard
    st.subheader("Dashboard")
    
    # Key metrics
    metrics = st.columns(4)
    with metrics[0]:
        st.metric("Total Runs", len(st.session_state.runs))
    with metrics[1]:
        successful_runs = len([r for r in st.session_state.runs if r.get('status') == 'Completed'])
        st.metric("Successful Runs", successful_runs)
    with metrics[2]:
        avg_duration = "N/A"
        if st.session_state.runs:
            durations = [r.get('duration', 0) for r in st.session_state.runs]
            avg_duration = f"{sum(durations)/len(durations):.1f}s"
        st.metric("Avg Duration", avg_duration)
    with metrics[3]:
        recent_runs = len([r for r in st.session_state.runs 
                         if datetime.strptime(r.get('start_time', ''), "%Y-%m-%d %H:%M:%S")
                         > datetime.now() - timedelta(days=1)])
        st.metric("Recent Runs (24h)", recent_runs)
    
    # Run Management
    with st.container():
        cols = st.columns([2, 1])
        
        with cols[0]:
            st.subheader("Log New Run")
            with st.form("run_form"):
                run_name = st.text_input("Run Name", placeholder="Enter a descriptive name...")
                
                cols2 = st.columns(2)
                with cols2[0]:
                    model = st.selectbox(
                        "Model",
                        ["GPT-4", "GPT-3.5-Turbo", "Claude-2", "Claude-3"]
                    )
                with cols2[1]:
                    status = st.selectbox(
                        "Status",
                        ["Running", "Completed", "Failed", "Cancelled"]
                    )
                
                cols3 = st.columns(3)
                with cols3[0]:
                    duration = st.number_input("Duration (s)", min_value=0, value=60)
                with cols3[1]:
                    tokens = st.number_input("Tokens Used", min_value=0, value=1000)
                with cols3[2]:
                    cost = st.number_input("Cost ($)", min_value=0.0, value=0.01, format="%.3f")
                
                notes = st.text_area("Notes", height=100)
                
                submitted = st.form_submit_button("Log Run", use_container_width=True)
                if submitted:
                    new_run = {
                        "name": run_name,
                        "model": model,
                        "status": status,
                        "duration": duration,
                        "tokens": tokens,
                        "cost": cost,
                        "notes": notes,
                        "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    st.session_state.runs.append(new_run)
                    st.success("✅ Run logged successfully!")
        
        with cols[1]:
            st.subheader("Quick Actions")
            if st.button("📥 Import Logs", use_container_width=True):
                st.info("Opening import dialog...")
            if st.button("📤 Export Logs", use_container_width=True):
                st.info("Preparing export...")
            if st.button("🔄 Sync Runs", use_container_width=True):
                st.info("Syncing run data...")
    
    # Run History
    st.subheader("Run History")
    
    # Filters
    with st.expander("🔍 Filters", expanded=True):
        cols4 = st.columns(4)
        with cols4[0]:
            filter_model = st.multiselect(
                "Model",
                ["GPT-4", "GPT-3.5-Turbo", "Claude-2", "Claude-3"]
            )
        with cols4[1]:
            filter_status = st.multiselect(
                "Status",
                ["Running", "Completed", "Failed", "Cancelled"]
            )
        with cols4[2]:
            date_range = st.selectbox(
                "Time Range",
                ["Last 24 hours", "Last 7 days", "Last 30 days", "All time"]
            )
        with cols4[3]:
            sort_by = st.selectbox(
                "Sort By",
                ["Start Time", "Duration", "Cost"]
            )
    
    # Display runs
    if st.session_state.runs:
        df = pd.DataFrame(st.session_state.runs)
        
        # Apply filters
        if filter_model:
            df = df[df['model'].isin(filter_model)]
        if filter_status:
            df = df[df['status'].isin(filter_status)]
            
        # Apply date filter
        df['start_time'] = pd.to_datetime(df['start_time'])
        if date_range == "Last 24 hours":
            df = df[df['start_time'] > datetime.now() - timedelta(days=1)]
        elif date_range == "Last 7 days":
            df = df[df['start_time'] > datetime.now() - timedelta(days=7)]
        elif date_range == "Last 30 days":
            df = df[df['start_time'] > datetime.now() - timedelta(days=30)]
        
        # Sort
        if sort_by == "Start Time":
            df = df.sort_values('start_time', ascending=False)
        elif sort_by == "Duration":
            df = df.sort_values('duration', ascending=False)
        else:  # Cost
            df = df.sort_values('cost', ascending=False)
        
        # Display as cards
        for _, run in df.iterrows():
            with st.expander(f"{run['name']} ({run['status']})", expanded=False):
                cols5 = st.columns([3, 1])
                with cols5[0]:
                    st.write(f"**Model:** {run['model']}")
                    st.write(f"**Duration:** {run['duration']}s")
                    st.write(f"**Tokens:** {run['tokens']}")
                    st.write(f"**Notes:** {run['notes']}")
                with cols5[1]:
                    st.write(f"**Cost:** ${run['cost']:.3f}")
                    st.write(f"**Started:** {run['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    cols6 = st.columns(2)
                    with cols6[0]:
                        if st.button("📊 Details", key=f"details_{run['start_time']}", use_container_width=True):
                            st.session_state.viewing_run = run['start_time']
                    with cols6[1]:
                        if st.button("🗑️ Delete", key=f"delete_{run['start_time']}", use_container_width=True):
                            st.session_state.runs = [r for r in st.session_state.runs if r['start_time'] != run['start_time']]
                            st.rerun()
    else:
        st.info("No runs logged yet. Use the form above to log your first run!")
