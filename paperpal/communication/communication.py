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


def construct_email_body(content,
                         start_date,
                         end_date,
                         urls_and_titles):
    if start_date == end_date:
        date_range = start_date
    else:
        date_range = f"{start_date} - {end_date}"
    body = f"""## PaperPal Newsletter for {date_range}:

{content}

##References:
{urls_and_titles}
"""
    return body


class GmailCommunication:

    def __init__(self, sender_address=None, receiver_address=None, app_password=None):
        self.sender_address = sender_address
        self.app_password = app_password
        self.receiver_address = receiver_address
        self.email_message = None
        
        if not self.app_password:
            self.app_password = os.getenv('GMAIL_APP_PASSWORD', None)
            if not self.app_password:
                raise Exception("No application password found. Please set the GMAIL_APP_PASSWORD environment variable.")
                
        if not self.sender_address:
            self.sender_address = os.getenv('GMAIL_SENDER_ADDRESS', None)
            if not self.sender_address:
                raise Exception("No sender address found. Please set the GMAIL_SENDER_ADDRESS environment variable.")


    def compose_message(self, content, start_date, end_date):
        """Method to compose a MIMEMultipart Message

        Args:
            content (str): markdown formatted string content for generating an email
        """
        sender_address = self.sender_address
        receiver_address = self.receiver_address

        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
            start_date = start_date.strftime("%B %d, %Y")
        
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d")
            end_date = end_date.strftime("%B %d, %Y")

        # Keep receiver_address as a list if it is one
        if not receiver_address:  # we send the email to ourselves if we aren't sending it to someone else.
            receiver_address = [sender_address]
        elif isinstance(receiver_address, str):
            receiver_address = [addr.strip() for addr in receiver_address.split(',')]
        
        # Remove sender's address from BCC list if it's there
        receiver_address = [addr for addr in receiver_address if addr != sender_address]
        
        if start_date == end_date:
            date_range = start_date
        else:
            date_range = f"{start_date} to {end_date}"
        
        message = MIMEMultipart('alternative')
        message["From"] = sender_address
        message["To"] = sender_address  # Set To as the sender address
        if receiver_address:  # Only add BCC if there are other recipients
            message["Bcc"] = ', '.join(receiver_address)
        message['Subject'] = f"PaperPal Paper Newsletter for {date_range}"
        
        # Create both plain text and HTML versions
        text_part = MIMEText(content, 'plain')
        html_content = markdown2.markdown(content)
        html_part = MIMEText(html_content, 'html')
        
        # Attach both versions - the email client will use the last attached version it can handle
        message.attach(text_part)
        message.attach(html_part)
        
        self.email_message = message
        # Store the receiver list separately
        self.receiver_list = receiver_address


    def send_email(self):
        sender_address = self.sender_address
        app_password = self.app_password
        message = self.email_message
        
        try:
            print(f"Attempting to send email from: {sender_address}")
            print(f"Recipients list: {self.receiver_list}")
            print(f"Message headers: {dict(message.items())}")  # Log message headers
            
            session = smtplib.SMTP('smtp.gmail.com', 587)
            print("Connected to SMTP server")
            
            session.starttls()
            print("Started TLS")
            
            session.login(sender_address, app_password)
            print("Logged in successfully")
            
            message_text = message.as_string()
            
            # Use the stored receiver list
            for recipient in self.receiver_list:
                try:
                    print(f"Attempting to send to: {recipient}")
                    session.sendmail(sender_address, recipient, message_text)
                    print(f"Successfully sent email to: {recipient}")
                except Exception as e:
                    print(f"Failed to send to {recipient}: {str(e)}")
                    raise
                
            session.quit()
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
            message['Subject'] = "PaperPal Error Notification"
            
            error_content = f"""## PaperPal Error Report

An error occurred during the PaperPal execution:

{error_msg}
"""
            
            text_part = MIMEText(error_content, 'plain')
            html_content = markdown2.markdown(error_content)
            html_part = MIMEText(html_content, 'html')
            
            message.attach(text_part)
            message.attach(html_part)
            
            session = smtplib.SMTP('smtp.gmail.com', 587)
            print("Connected to SMTP server for error notification")
            
            session.starttls()
            print("Started TLS for error notification")
            
            session.login(self.sender_address, self.app_password)
            print("Logged in successfully for error notification")
            
            message_text = message.as_string()
            session.sendmail(self.sender_address, self.sender_address, message_text)
            print("Error notification sent successfully")
            
            session.quit()
            print("Error notification SMTP session closed")
            
        except Exception as e:
            print(f"Failed to send error notification: {str(e)}")