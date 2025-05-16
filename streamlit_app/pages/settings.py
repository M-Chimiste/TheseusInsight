import streamlit as st
from app import make_api_request, APIError

def show_settings_page():
    st.title("⚙️ Settings")
    
    # Create tabs for different settings sections
    tab1, tab2, tab3, tab4 = st.tabs(["Research Interests", "Models", "Email", "Misc"])
    
    with tab1:
        st.header("Research Interests")
        
        try:
            # Get current research interests
            interests = make_api_request("GET", "/settings/research-interests")
            current_interests = "\n".join(interests.get("interests", []))
            
            # Text area for editing interests
            new_interests = st.text_area(
                "Enter your research interests (one per line)",
                value=current_interests,
                height=200,
                help="Enter one research interest per line. These will be used to filter papers."
            )
            
            # Save button
            if st.button("Save Research Interests"):
                interests_list = [i.strip() for i in new_interests.split("\n") if i.strip()]
                make_api_request("PUT", "/settings/research-interests", {"interests": interests_list})
                st.success("Research interests saved successfully!")
                
        except APIError as e:
            st.error(f"Error: {e}")
    
    with tab2:
        st.header("Model Configuration")
        
        try:
            # Get available models
            models = make_api_request("GET", "/models")
            
            # Display current models
            st.subheader("Current Models")
            if models:
                for model in models:
                    with st.expander(f"{model['name']} ({model['model_type']})"):
                        st.code(f"Path: {model.get('path', 'N/A')}\n"
                               f"Description: {model.get('description', 'No description')}")
                        
                        # Delete button
                        if st.button(f"Delete {model['name']}", key=f"del_{model['id']}"):
                            make_api_request("DELETE", f"/models/{model['id']}")
                            st.experimental_rerun()
            else:
                st.info("No models configured.")
            
            # Add new model form
            st.subheader("Add New Model")
            with st.form("add_model"):
                name = st.text_input("Model Name")
                model_type = st.selectbox("Model Type", ["llm", "embedding", "tts"])
                path = st.text_input("Model Path")
                description = st.text_area("Description")
                
                if st.form_submit_button("Add Model"):
                    if not name or not path:
                        st.error("Name and Path are required fields")
                    else:
                        make_api_request("POST", "/models", {
                            "name": name,
                            "model_type": model_type,
                            "path": path,
                            "description": description
                        })
                        st.experimental_rerun()
                        
        except APIError as e:
            st.error(f"Error: {e}")
    
    with tab3:
        st.header("Email Settings")
        
        try:
            # Get current email settings
            email_settings = make_api_request("GET", "/settings/email")
            
            # Email settings form
            with st.form("email_settings"):
                smtp_server = st.text_input("SMTP Server", 
                                          value=email_settings.get("smtp_server", ""))
                smtp_port = st.number_input("SMTP Port", 
                                          value=email_settings.get("smtp_port", 587), 
                                          min_value=1, 
                                          max_value=65535)
                smtp_username = st.text_input("SMTP Username", 
                                            value=email_settings.get("smtp_username", ""))
                smtp_password = st.text_input("SMTP Password", 
                                            value="", 
                                            type="password",
                                            help="Leave empty to keep current password")
                from_email = st.text_input("From Email", 
                                         value=email_settings.get("from_email", ""))
                
                if st.form_submit_button("Save Email Settings"):
                    settings = {
                        "smtp_server": smtp_server,
                        "smtp_port": smtp_port,
                        "smtp_username": smtp_username,
                        "from_email": from_email
                    }
                    # Only update password if provided
                    if smtp_password:
                        settings["smtp_password"] = smtp_password
                    
                    make_api_request("PUT", "/settings/email", settings)
                    st.success("Email settings saved successfully!")
                    
                # Test email
                if st.form_submit_button("Send Test Email"):
                    try:
                        make_api_request("POST", "/settings/email/test")
                        st.success("Test email sent successfully!")
                    except APIError as e:
                        st.error(f"Failed to send test email: {e}")
                        
        except APIError as e:
            st.error(f"Error: {e}")
    
    with tab4:
        st.header("Miscellaneous Settings")
        
        try:
            # Get current misc settings
            misc_settings = make_api_request("GET", "/settings/misc")
            
            # Misc settings form
            with st.form("misc_settings"):
                results_per_page = st.number_input(
                    "Results Per Page", 
                    min_value=5, 
                    max_value=100, 
                    value=misc_settings.get("results_per_page", 25)
                )
                
                theme = st.selectbox(
                    "Theme", 
                    ["light", "dark", "system"],
                    index=["light", "dark", "system"].index(misc_settings.get("theme", "light"))
                )
                
                if st.form_submit_button("Save Settings"):
                    make_api_request("PUT", "/settings/misc", {
                        "results_per_page": results_per_page,
                        "theme": theme
                    })
                    st.success("Miscellaneous settings saved successfully!")
                    
        except APIError as e:
            st.error(f"Error: {e}")
