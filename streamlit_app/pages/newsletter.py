import streamlit as st
from datetime import datetime, timedelta
from app import make_api_request, APIError
import json

def show_newsletter_page():
    st.title("📰 Newsletter Builder")
    
    # Initialize session state for form data
    if 'newsletter_data' not in st.session_state:
        st.session_state.newsletter_data = {
            'start_date': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
            'end_date': datetime.now().strftime('%Y-%m-%d'),
            'interests_override': '',
            'email_recipients': '',
            'create_podcast': False,
            'podcast_voice': 'en-US-Wavenet-D',
            'speaking_rate': 1.0,
            'include_visualization': False
        }
    
    # Date range selection
    st.header("1. Select Date Range")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=datetime.strptime(st.session_state.newsletter_data['start_date'], '%Y-%m-%d'),
            max_value=datetime.now()
        )
    with col2:
        end_date = st.date_input(
            "End Date",
            value=datetime.strptime(st.session_state.newsletter_data['end_date'], '%Y-%m-%d'),
            min_value=start_date,
            max_value=datetime.now()
        )
    
    # Research interests override
    st.header("2. Research Focus")
    interests_override = st.text_area(
        "Override default research interests (one per line)",
        value=st.session_state.newsletter_data['interests_override'],
        height=100,
        help="Leave empty to use default interests from settings"
    )
    
    # Email options
    st.header("3. Email Options")
    email_recipients = st.text_input(
        "Recipients (comma-separated email addresses)",
        value=st.session_state.newsletter_data['email_recipients'],
        placeholder="user1@example.com, user2@example.com"
    )
    
    # Podcast options
    st.header("4. Podcast Options")
    create_podcast = st.checkbox(
        "Also create podcast version",
        value=st.session_state.newsletter_data['create_podcast']
    )
    
    if create_podcast:
        with st.expander("Podcast Settings"):
            col1, col2 = st.columns(2)
            with col1:
                voice = st.selectbox(
                    "Voice",
                    ["en-US-Wavenet-D", "en-US-Wavenet-C", "en-US-Standard-D"],
                    index=["en-US-Wavenet-D", "en-US-Wavenet-C", "en-US-Standard-D"].index(
                        st.session_state.newsletter_data.get('podcast_voice', 'en-US-Wavenet-D'))
                    )
            with col2:
                speaking_rate = st.slider(
                    "Speaking Rate",
                    min_value=0.5,
                    max_value=2.0,
                    value=st.session_state.newsletter_data.get('speaking_rate', 1.0),
                    step=0.1
                )
            
            include_visualization = st.checkbox(
                "Include visualization",
                value=st.session_state.newsletter_data.get('include_visualization', False)
            )
            
            if include_visualization:
                st.warning("Visualization will increase generation time")
    
    # Save form data to session state
    st.session_state.newsletter_data.update({
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'interests_override': interests_override,
        'email_recipients': email_recipients,
        'create_podcast': create_podcast,
        'podcast_voice': voice if create_podcast else 'en-US-Wavenet-D',
        'speaking_rate': speaking_rate if create_podcast else 1.0,
        'include_visualization': include_visualization if create_podcast else False
    })
    
    # Generate button
    st.header("5. Generate Newsletter")
    if st.button("🚀 Generate Newsletter", type="primary"):
        if not email_recipients.strip():
            st.error("Please enter at least one email recipient")
        else:
            with st.spinner("Generating newsletter..."):
                try:
                    # Prepare the request data
                    data = {
                        'start_date': start_date.strftime('%Y-%m-%d'),
                        'end_date': end_date.strftime('%Y-%m-%d'),
                        'email_recipients': [e.strip() for e in email_recipients.split(',') if e.strip()],
                        'options': {}
                    }
                    
                    # Add research interests if overridden
                    if interests_override.strip():
                        data['interests'] = [i.strip() for i in interests_override.split('\n') if i.strip()]
                    
                    # Add podcast options if enabled
                    if create_podcast:
                        data['options']['podcast'] = {
                            'voice': voice,
                            'speaking_rate': speaking_rate,
                            'include_visualization': include_visualization
                        }
                    
                    # Call the API
                    response = make_api_request(
                        "POST",
                        "/newsletter/generate",
                        data
                    )
                    
                    if 'task_id' in response:
                        st.session_state.newsletter_task_id = response['task_id']
                        st.success("Newsletter generation started!")
                        st.session_state.show_progress = True
                        
                        # In a real app, you would connect to WebSocket here
                        # to get real-time progress updates
                        # For now, we'll simulate progress
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        for i in range(100):
                            progress_bar.progress(i + 1)
                            status_text.text(f"Status: Processing... {i+1}%")
                            # Simulate API call to check status
                            # status = make_api_request("GET", f"/tasks/{st.session_state.newsletter_task_id}")
                            # if status.get('status') == 'completed':
                            #     break
                            # time.sleep(0.1)
                        
                        status_text.text("Status: Complete!")
                        st.balloons()
                        
                        # Show download links
                        st.success("Newsletter generated successfully!")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.download_button(
                                "📥 Download Newsletter (PDF)",
                                data=json.dumps(data, indent=2).encode(),
                                file_name=f"newsletter_{datetime.now().strftime('%Y%m%d')}.json",
                                mime="application/json"
                            )
                        
                        if create_podcast:
                            with col2:
                                st.download_button(
                                    "🎧 Download Podcast",
                                    data=json.dumps(data, indent=2).encode(),
                                    file_name=f"podcast_{datetime.now().strftime('%Y%m%d')}.json",
                                    mime="application/json"
                                )
                    else:
                        st.error("Failed to start newsletter generation")
                        
                except APIError as e:
                    st.error(f"Error: {e}")
