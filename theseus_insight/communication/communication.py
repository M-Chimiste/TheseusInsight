# Copyright 2023 M Chimiste

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import markdown2
from theseus_insight.data_model.data_handling import PaperDatabase


def construct_email_body(content,
                         start_date,
                         end_date,
                         urls_and_titles):
    """
    Construct the body of an email.

    Args:
        content (str): The content of the email
        start_date (str): The start date of the newsletter
        end_date (str): The end date of the newsletter
        urls_and_titles (str): The URLs and titles of the references
    Returns:
        str: The body of the email
    """
    if start_date == end_date:
        date_range = start_date
    else:
        date_range = f"{start_date} - {end_date}"
    body = f"""## Theseus Insight Newsletter for {date_range}:

{content}

## References:
{urls_and_titles}
"""
    return body


class GmailCommunication:
    """
    Class for sending emails via Gmail.
    """
    def __init__(self,
                sender_address=None, 
                receiver_address=None, 
                app_password=None, 
                verbose=False,
                db_path=None):
        self.sender_address = sender_address
        self.app_password = app_password
        self.receiver_address = receiver_address
        self.email_message = None
        self.verbose = verbose
        if not db_path:
            db_path = os.getenv('DATABASE_URL', 'postgresql://theseus:theseus@localhost:5432/theseusdb')
        self.db_path = db_path
        self.db = PaperDatabase(self.db_path)
        if not self.app_password:
            self.app_password = os.getenv('GMAIL_APP_PASSWORD', None)
            if not self.app_password:
                raise Exception("No application password found. Please set the GMAIL_APP_PASSWORD environment variable.")
        if not self.sender_address:
            self.sender_address = os.getenv('GMAIL_SENDER_ADDRESS', None)
            if not self.sender_address:
                raise Exception("No sender address found. Please set the GMAIL_SENDER_ADDRESS environment variable.")


    def compose_message(self, content, start_date, end_date):
        """
        Compose an email message.
        
        Args:
            content (str): The content of the email
            start_date (str): The start date of the newsletter
            end_date (str): The end date of the newsletter
        """
        sender_address = self.sender_address
        receiver_address = self.receiver_address
        # If receiver_address is not provided, fetch from DB
        if not receiver_address:
            recipients = self.db.get_email_recipients()
            if recipients:
                receiver_address = recipients
            else:
                receiver_address = [sender_address]
        elif isinstance(receiver_address, str):
            receiver_address = [addr.strip() for addr in receiver_address.split(',')]
        # Remove sender's address from BCC list if it's there
        receiver_address = [addr for addr in receiver_address if addr != sender_address]
        
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
            start_date = start_date.strftime("%B %d, %Y")
        
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d")
            end_date = end_date.strftime("%B %d, %Y")

        if start_date == end_date:
            date_range = start_date
        else:
            date_range = f"{start_date} to {end_date}"
        
        message = MIMEMultipart('alternative')
        message["From"] = sender_address
        message["To"] = sender_address  # Set To as the sender address
        # Remove the BCC header - it will be handled during sendmail
        if "Bcc" in message:
            del message["Bcc"]
        message['Subject'] = f"Theseus Insight Paper Newsletter for {date_range}"
        
        # Create both plain text and HTML versions
        text_part = MIMEText(content, 'plain')
        
        # Enhanced HTML generation with proper CSS styling
        html_content = self._create_enhanced_html(content)
        html_part = MIMEText(html_content, 'html')
        
        # Attach both versions - the email client will use the last attached version it can handle
        message.attach(text_part)
        message.attach(html_part)
        
        self.email_message = message
        # Store the receiver list separately
        self.receiver_list = receiver_address

    def _create_enhanced_html(self, content):
        """
        Create enhanced HTML content with proper CSS styling to prevent title formatting issues.
        
        Args:
            content (str): The markdown content
            
        Returns:
            str: Enhanced HTML content
        """
        # Pre-process content to clean up any problematic title formatting
        import re
        
        # Clean up titles in the markdown content first
        def clean_title_line(match):
            title_text = match.group(1)
            # Remove any newlines or extra whitespace within the title
            cleaned_title = re.sub(r'\s+', ' ', title_text).strip()
            return f"## {cleaned_title}"
        
        # Pattern to match ## title lines and clean them
        title_pattern = r'^## (.+?)$'
        cleaned_content = re.sub(title_pattern, clean_title_line, content, flags=re.MULTILINE)
        
        # Convert markdown to HTML
        base_html = markdown2.markdown(cleaned_content)
        
        # Enhanced CSS specifically for email clients like Gmail
        email_css = """
        <style type="text/css">
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                line-height: 1.6;
                color: #333333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }
            h1, h2, h3, h4, h5, h6 {
                color: #2c3e50;
                margin-top: 30px;
                margin-bottom: 15px;
                font-weight: bold !important;
                line-height: 1.3 !important;
                /* Prevent title breaking across lines from losing formatting */
                display: block !important;
                word-wrap: break-word !important;
                /* Force consistent bold formatting across line breaks */
                font-weight: 700 !important;
                /* Prevent unwanted line breaks within titles */
                white-space: nowrap !important;
                overflow: hidden !important;
                text-overflow: ellipsis !important;
            }
            h2 {
                font-size: 1.5em !important;
                border-bottom: 2px solid #3498db;
                padding-bottom: 10px;
                /* Allow line breaks but maintain formatting */
                white-space: normal !important;
                overflow: visible !important;
                text-overflow: clip !important;
                /* Ensure the entire title block maintains formatting */
                overflow-wrap: break-word !important;
            }
            /* Force Gmail to respect our styling */
            .title-block {
                font-weight: bold !important;
                font-size: 1.5em !important;
                color: #2c3e50 !important;
                border-bottom: 2px solid #3498db !important;
                padding-bottom: 10px !important;
                margin-top: 30px !important;
                margin-bottom: 15px !important;
                display: block !important;
                line-height: 1.3 !important;
                /* Better handling of long titles */
                word-wrap: break-word !important;
                overflow-wrap: break-word !important;
                hyphens: auto !important;
                /* Ensure consistent formatting across all parts of the title */
                font-family: inherit !important;
            }
            /* Additional span styling for title components */
            .title-block span {
                font-weight: bold !important;
                font-size: inherit !important;
                color: inherit !important;
                font-family: inherit !important;
            }
            p {
                margin-bottom: 15px;
                line-height: 1.6;
            }
            ul, ol {
                margin-bottom: 15px;
                padding-left: 30px;
            }
            li {
                margin-bottom: 5px;
            }
            a {
                color: #3498db;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
            /* Specific styles for mobile Gmail apps */
            @media only screen and (max-width: 600px) {
                body {
                    padding: 10px;
                }
                h2, .title-block {
                    font-size: 1.3em !important;
                }
            }
        </style>
        """
        
        # Post-process the HTML to add better title formatting
        # Replace h2 tags with enhanced div blocks to ensure consistent formatting
        def replace_h2_with_enhanced(match):
            title_text = match.group(1)
            # Additional cleaning of the title text
            clean_title = re.sub(r'\s+', ' ', title_text).strip()
            # Wrap in spans to ensure formatting consistency
            return f'<div class="title-block"><span>{clean_title}</span></div>'
        
        # Pattern to match h2 tags and their content
        h2_pattern = r'<h2>(.*?)</h2>'
        enhanced_html = re.sub(h2_pattern, replace_h2_with_enhanced, base_html, flags=re.DOTALL)
        
        # Wrap in proper HTML structure
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Theseus Insight Newsletter</title>
            {email_css}
        </head>
        <body>
            {enhanced_html}
        </body>
        </html>
        """
        
        return full_html


    def send_email(self):
        """
        Send an email.
        """
        sender_address = self.sender_address
        app_password = self.app_password
        message = self.email_message

        try:
            if self.verbose:
                print(f"Attempting to send email from: {sender_address}")
                print(f"Recipients list: {self.receiver_list}")
                print(f"Message headers: {dict(message.items())}")

            session = smtplib.SMTP('smtp.gmail.com', 587)
            if self.verbose:
                print("Connected to SMTP server")

            session.starttls()
            if self.verbose:
                print("Started TLS")

            session.login(sender_address, app_password)
            if self.verbose:
                print("Logged in successfully")

            message_text = message.as_string()

            # Send the email ONCE with all recipients in BCC
            if self.receiver_list:
                # Use the sender's address for 'To' and the receiver list for 'Bcc'
                session.sendmail(sender_address, [sender_address] + self.receiver_list, message_text)
                if self.verbose:
                    print(f"Successfully sent email to all BCC recipients")
            else:
                session.sendmail(sender_address, sender_address, message_text)
                if self.verbose:
                    print(f"Successfully sent email to sender")


            session.quit()
            if self.verbose:
                print("SMTP session closed")

        except Exception as e:
            error_msg = f"Unable to send email with exception {str(e)}"
            print(f"Error details: {error_msg}")
            # Try to send error notification without raising
            try:
                self.send_error_notification(error_msg)
            except:
                pass
            raise Exception(error_msg)
                

    def send_error_notification(self, error_msg: str):
        """
        Send an error notification email to the sender.
        
        Args:
            error_msg (str): The error message to send
        """
        try:
            print(f"Attempting to send error notification to {self.sender_address}")
            
            message = MIMEMultipart('alternative')
            message["From"] = self.sender_address
            message["To"] = self.sender_address
            message['Subject'] = "Theseus Insight Error Notification"
            
            error_content = f"""## Theseus Insight Error Report

An error occurred during the Theseus Insight execution:

{error_msg}
"""
            
            text_part = MIMEText(error_content, 'plain')
            html_content = markdown2.markdown(error_content)
            html_part = MIMEText(html_content, 'html')
            
            message.attach(text_part)
            message.attach(html_part)
            
            session = smtplib.SMTP('smtp.gmail.com', 587)
            if self.verbose:
                print("Connected to SMTP server for error notification")
            
            session.starttls()
            if self.verbose:
                print("Started TLS for error notification")
            
            session.login(self.sender_address, self.app_password)
            if self.verbose:
                print("Logged in successfully for error notification")
            
            message_text = message.as_string()
            session.sendmail(self.sender_address, self.sender_address, message_text)
            if self.verbose:
                print("Error notification sent successfully")
            
            session.quit()
            if self.verbose:
                print("Error notification SMTP session closed")
            
        except Exception as e:
            if self.verbose:
                print(f"Failed to send error notification: {str(e)}")
