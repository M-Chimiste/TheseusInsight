import streamlit as st
import os
from datetime import datetime
from app import make_api_request, APIError

def show_podcast_page():
    st.title("🎙️ Podcast Builder")
    
    # Initialize session state for form data
    if 'podcast_data' not in st.session_state:
        st.session_state.podcast_data = {
            'input_type': 'pdf',
            'podcast_title': f"Podcast_{datetime.now().strftime('%Y%m%d')}",
            'podcast_description': '',
            'voice': 'en-US-Wavenet-D',
            'speaking_rate': 1.0,
            'include_visualization': False,
            'visualization_style': 'scientific',
            'background_music': 'none',
            'uploaded_files': []
        }
    
    # Input type selection
    st.header("1. Input Source")
    input_type = st.radio(
        "Select input type",
        ["Upload PDFs", "Enter ArXiv URLs", "Enter Text"],
        index=0,
        key='podcast_input_type'
    )
    
    # Handle different input types
    if input_type == "Upload PDFs":
        uploaded_files = st.file_uploader(
            "Upload PDF files",
            type=["pdf"],
            accept_multiple_files=True,
            key="podcast_pdf_uploader"
        )
        st.session_state.podcast_data['uploaded_files'] = uploaded_files
        
        if uploaded_files:
            st.success(f"{len(uploaded_files)} files uploaded")
            
    elif input_type == "Enter ArXiv URLs":
        arxiv_urls = st.text_area(
            "Enter ArXiv URLs (one per line)",
            height=100,
            help="Example: https://arxiv.org/abs/2103.00001",
            key="podcast_arxiv_urls"
        )
        st.session_state.podcast_data['arxiv_urls'] = arxiv_urls.split('\n') if arxiv_urls else []
        
    else:  # Enter Text
        podcast_text = st.text_area(
            "Enter your script",
            height=200,
            help="Enter the text you want to convert to speech",
            key="podcast_text"
        )
        st.session_state.podcast_data['text'] = podcast_text
    
    # Podcast metadata
    st.header("2. Podcast Details")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.podcast_data['podcast_title'] = st.text_input(
            "Podcast Title",
            value=st.session_state.podcast_data['podcast_title']
        )
    with col2:
        st.session_state.podcast_data['podcast_author'] = st.text_input(
            "Author",
            value=st.session_state.podcast_data.get('podcast_author', '')
        )
    
    st.session_state.podcast_data['podcast_description'] = st.text_area(
        "Description",
        value=st.session_state.podcast_data['podcast_description'],
        height=80
    )
    
    # Voice settings
    st.header("3. Voice Settings")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.podcast_data['voice'] = st.selectbox(
            "Voice",
            ["en-US-Wavenet-D", "en-US-Wavenet-C", "en-US-Standard-D", "en-US-Standard-C"],
            index=["en-US-Wavenet-D", "en-US-Wavenet-C", "en-US-Standard-D", "en-US-Standard-C"].index(
                st.session_state.podcast_data['voice']
            )
        )
    with col2:
        st.session_state.podcast_data['speaking_rate'] = st.slider(
            "Speaking Rate",
            min_value=0.5,
            max_value=2.0,
            value=st.session_state.podcast_data['speaking_rate'],
            step=0.1,
            help="1.0 is normal speed, 0.5 is half speed, 2.0 is double speed"
        )
    
    # Visualization options
    st.header("4. Visualization Options")
    st.session_state.podcast_data['include_visualization'] = st.checkbox(
        "Include video visualization",
        value=st.session_state.podcast_data['include_visualization'],
        help="Create a video with animated text and images"
    )
    
    if st.session_state.podcast_data['include_visualization']:
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.podcast_data['visualization_style'] = st.selectbox(
                "Visualization Style",
                ["scientific", "minimal", "dynamic", "academic"],
                index=["scientific", "minimal", "dynamic", "academic"].index(
                    st.session_state.podcast_data.get('visualization_style', 'scientific')
                )
            )
        with col2:
            st.session_state.podcast_data['background_music'] = st.selectbox(
                "Background Music",
                ["none", "ambient", "upbeat", "calm"],
                index=["none", "ambient", "upbeat", "calm"].index(
                    st.session_state.podcast_data.get('background_music', 'none')
                )
            )
        
        if st.session_state.podcast_data['background_music'] != 'none':
            st.session_state.podcast_data['music_volume'] = st.slider(
                "Music Volume",
                min_value=0.1,
                max_value=1.0,
                value=st.session_state.podcast_data.get('music_volume', 0.3),
                step=0.1,
                help="Volume of background music relative to speech"
            )
    
    # Generate button
    st.header("5. Generate Podcast")
    
    if st.button("🎙️ Generate Podcast", type="primary"):
        # Validate input
        if input_type == "Upload PDFs" and not st.session_state.podcast_data.get('uploaded_files'):
            st.error("Please upload at least one PDF file")
        elif input_type == "Enter ArXiv URLs" and not st.session_state.podcast_data.get('arxiv_urls'):
            st.error("Please enter at least one ArXiv URL")
        elif input_type == "Enter Text" and not st.session_state.podcast_data.get('text', '').strip():
            st.error("Please enter some text")
        else:
            with st.spinner("Generating podcast..."):
                try:
                    # Prepare the request data
                    data = {
                        'title': st.session_state.podcast_data['podcast_title'],
                        'description': st.session_state.podcast_data['podcast_description'],
                        'voice': st.session_state.podcast_data['voice'],
                        'speaking_rate': st.session_state.podcast_data['speaking_rate'],
                        'include_visualization': st.session_state.podcast_data['include_visualization'],
                        'options': {}
                    }
                    
                    if 'podcast_author' in st.session_state.podcast_data:
                        data['author'] = st.session_state.podcast_data['podcast_author']
                    
                    if st.session_state.podcast_data['include_visualization']:
                        data['options']['visualization'] = {
                            'style': st.session_state.podcast_data['visualization_style'],
                            'background_music': st.session_state.podcast_data['background_music']
                        }
                        if 'music_volume' in st.session_state.podcast_data:
                            data['options']['visualization']['music_volume'] = st.session_state.podcast_data['music_volume']
                    
                    # Handle different input types
                    if input_type == "Upload PDFs":
                        # In a real app, you would upload the files to the server
                        # For now, we'll just include the filenames
                        data['input_type'] = 'pdf'
                        data['files'] = [f.name for f in st.session_state.podcast_data['uploaded_files']]
                    elif input_type == "Enter ArXiv URLs":
                        data['input_type'] = 'arxiv'
                        data['urls'] = [url.strip() for url in st.session_state.podcast_data['arxiv_urls'] if url.strip()]
                    else:  # Enter Text
                        data['input_type'] = 'text'
                        data['text'] = st.session_state.podcast_data['text']
                    
                    # Call the API
                    response = make_api_request(
                        "POST",
                        "/podcast/generate",
                        data
                    )
                    
                    if 'task_id' in response:
                        st.session_state.podcast_task_id = response['task_id']
                        st.success("Podcast generation started!")
                        
                        # In a real app, you would connect to WebSocket here
                        # to get real-time progress updates
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        for i in range(100):
                            progress_bar.progress(i + 1)
                            status_text.text(f"Status: Processing... {i+1}%")
                            # Simulate API call to check status
                            # status = make_api_request("GET", f"/tasks/{st.session_state.podcast_task_id}")
                            # if status.get('status') == 'completed':
                            #     break
                            # time.sleep(0.1)
                        
                        status_text.text("Status: Complete!")
                        st.balloons()
                        
                        # Show download links
                        st.success("Podcast generated successfully!")
                        
                        # In a real app, you would get the download URL from the API
                        # For now, we'll just show a placeholder
                        col1, col2 = st.columns(2)
                        with col1:
                            st.download_button(
                                "🎧 Download Audio (MP3)",
                                data=b"",  # Empty data for demo
                                file_name=f"{st.session_state.podcast_data['podcast_title']}.mp3",
                                mime="audio/mp3"
                            )
                        
                        if st.session_state.podcast_data['include_visualization']:
                            with col2:
                                st.download_button(
                                    "🎥 Download Video (MP4)",
                                    data=b"",  # Empty data for demo
                                    file_name=f"{st.session_state.podcast_data['podcast_title']}.mp4",
                                    mime="video/mp4"
                                )
                    else:
                        st.error("Failed to start podcast generation")
                        
                except APIError as e:
                    st.error(f"Error: {e}")
