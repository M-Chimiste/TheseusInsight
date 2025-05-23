import unittest
from unittest.mock import patch, MagicMock
import smtplib
import os
from datetime import date

from theseus_insight.communication.communication import GmailCommunication, construct_email_body
from theseus_insight.constants import GMAIL_APP_PASSWORD_ENV_VAR, GMAIL_SENDER_ADDRESS_ENV_VAR


class TestGmailCommunication(unittest.TestCase):

    def setUp(self):
        self.sender_address = "sender@example.com"
        self.app_password = "testpassword"
        self.receiver_address = "receiver@example.com"
        self.subject = "Test Subject"
        self.content = "This is the test content."

        # Set environment variables for the tests
        os.environ[GMAIL_SENDER_ADDRESS_ENV_VAR] = self.sender_address
        os.environ[GMAIL_APP_PASSWORD_ENV_VAR] = self.app_password

    def tearDown(self):
        # Clean up environment variables
        del os.environ[GMAIL_SENDER_ADDRESS_ENV_VAR]
        del os.environ[GMAIL_APP_PASSWORD_ENV_VAR]

    def test_init_with_receiver(self):
        comm = GmailCommunication(sender_address=self.sender_address,
                                  app_password=self.app_password,
                                  receiver_address=self.receiver_address)
        self.assertEqual(comm.sender_address, self.sender_address)
        self.assertEqual(comm.app_password, self.app_password)
        self.assertEqual(comm.receiver_address, self.receiver_address)
        self.assertIsNone(comm.message)

    def test_init_without_receiver(self):
        comm = GmailCommunication(sender_address=self.sender_address,
                                  app_password=self.app_password)
        self.assertEqual(comm.sender_address, self.sender_address)
        self.assertEqual(comm.app_password, self.app_password)
        self.assertIsNone(comm.receiver_address)
        self.assertIsNone(comm.message)

    def test_init_uses_env_vars(self):
        # Test that it picks up from env if not provided
        comm_env = GmailCommunication(receiver_address=self.receiver_address)
        self.assertEqual(comm_env.sender_address, self.sender_address)
        self.assertEqual(comm_env.app_password, self.app_password)
        self.assertEqual(comm_env.receiver_address, self.receiver_address)

        # Test that providing args overrides env vars
        override_sender = "override_sender@example.com"
        override_password = "override_password"
        comm_override = GmailCommunication(sender_address=override_sender,
                                           app_password=override_password,
                                           receiver_address=self.receiver_address)
        self.assertEqual(comm_override.sender_address, override_sender)
        self.assertEqual(comm_override.app_password, override_password)


    def test_compose_message(self):
        comm = GmailCommunication(sender_address=self.sender_address,
                                  app_password=self.app_password,
                                  receiver_address=self.receiver_address)
        
        start_date = date(2023, 1, 1)
        end_date = date(2023, 1, 7)
        
        comm.compose_message(content=self.content, start_date=start_date, end_date=end_date, subject_prefix="Newsletter")

        self.assertIsNotNone(comm.message)
        self.assertIn(f"Subject: Newsletter: Research Papers Summary ({start_date} - {end_date})", comm.message)
        self.assertIn(f"From: {self.sender_address}", comm.message)
        self.assertIn(f"To: {self.receiver_address}", comm.message)
        # Check if the content constructed by construct_email_body is present
        expected_body_part = "Summary of research papers from 2023-01-01 to 2023-01-07." # from construct_email_body
        self.assertIn(expected_body_part, comm.message)
        self.assertIn(self.content, comm.message)


    @patch('smtplib.SMTP_SSL')
    def test_send_email_with_receiver(self, mock_smtp_ssl):
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        comm = GmailCommunication(sender_address=self.sender_address,
                                  app_password=self.app_password,
                                  receiver_address=self.receiver_address)
        comm.compose_message(content=self.content, start_date=date.today(), end_date=date.today(), subject_prefix="Test")
        
        comm.send_email()

        mock_smtp_ssl.assert_called_once_with("smtp.gmail.com", 465)
        mock_server.login.assert_called_once_with(self.sender_address, self.app_password)
        mock_server.sendmail.assert_called_once_with(self.sender_address, self.receiver_address, comm.message.encode('utf-8'))
        # server.quit() is implicitly called by context manager exit in actual code if we mock __exit__
        # If not, we might need to check if quit() was called on mock_server if __exit__ isn't mocked for it.

    @patch('smtplib.SMTP_SSL')
    @patch('logging.warning')
    def test_send_email_without_receiver(self, mock_logging_warning, mock_smtp_ssl):
        comm = GmailCommunication(sender_address=self.sender_address,
                                  app_password=self.app_password) # No receiver_address
        comm.compose_message(content=self.content, start_date=date.today(), end_date=date.today(), subject_prefix="Test")
        
        comm.send_email()

        mock_smtp_ssl.assert_not_called()
        mock_logging_warning.assert_called_once_with("Receiver address is not set. Email will not be sent.")

    @patch('smtplib.SMTP_SSL')
    def test_send_error_notification(self, mock_smtp_ssl):
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server
        
        error_subject = "Pipeline Error"
        error_message = "Something went wrong."
        receiver_override = "admin@example.com"

        comm = GmailCommunication(sender_address=self.sender_address,
                                  app_password=self.app_password,
                                  receiver_address=self.receiver_address) # Original receiver
        
        comm.send_error_notification(error_subject, error_message, receiver_address_override=receiver_override)

        mock_smtp_ssl.assert_called_once_with("smtp.gmail.com", 465)
        mock_server.login.assert_called_once_with(self.sender_address, self.app_password)
        
        # Check that the message was constructed correctly for the error
        args, _ = mock_server.sendmail.call_args
        sent_from, sent_to, actual_message_str = args
        self.assertEqual(sent_from, self.sender_address)
        self.assertEqual(sent_to, receiver_override) # Error sent to override address
        self.assertIn(f"Subject: {error_subject}", actual_message_str)
        self.assertIn(f"From: {self.sender_address}", actual_message_str)
        self.assertIn(f"To: {receiver_override}", actual_message_str)
        self.assertIn(error_message, actual_message_str)

    @patch('smtplib.SMTP_SSL')
    def test_send_error_notification_uses_default_receiver_if_no_override(self, mock_smtp_ssl):
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server
        
        error_subject = "Pipeline Error"
        error_message = "Something went wrong."

        comm = GmailCommunication(sender_address=self.sender_address,
                                  app_password=self.app_password,
                                  receiver_address=self.receiver_address)
        
        comm.send_error_notification(error_subject, error_message) # No override

        mock_server.sendmail.assert_called_once()
        args, _ = mock_server.sendmail.call_args
        _, sent_to, _ = args
        self.assertEqual(sent_to, self.receiver_address) # Sent to default receiver


class TestConstructEmailBody(unittest.TestCase):

    def test_basic_content_and_dates(self):
        content = "Main email content."
        start_date = date(2023, 1, 10)
        end_date = date(2023, 1, 17)
        
        body = construct_email_body(content, start_date, end_date)
        
        self.assertIn("Summary of research papers from 2023-01-10 to 2023-01-17.", body)
        self.assertIn(content, body)
        self.assertIn("Best regards,", body)
        self.assertIn("Theseus Insight Team", body)
        self.assertNotIn("Link to the full newsletter", body) # No link provided

    def test_with_link_to_newsletter(self):
        content = "Check out these papers."
        start_date = date(2023, 3, 1)
        end_date = date(2023, 3, 7)
        newsletter_link = "http://example.com/newsletter/123"
        
        body = construct_email_body(content, start_date, end_date, newsletter_link)
        
        self.assertIn(f"Summary of research papers from {start_date} to {end_date}.", body)
        self.assertIn(content, body)
        self.assertIn(f"Link to the full newsletter: {newsletter_link}", body)

    def test_content_with_special_characters(self):
        content = "Content with\nnewlines and special characters like éàç."
        start_date = date(2023, 4, 1)
        end_date = date(2023, 4, 7)
        
        body = construct_email_body(content, start_date, end_date)
        
        self.assertIn(content, body) # Ensure original content is preserved

    def test_same_start_and_end_date(self):
        content = "Daily update."
        single_date = date(2023, 5, 5)
        
        body = construct_email_body(content, single_date, single_date)
        
        self.assertIn(f"Summary of research papers from {single_date} to {single_date}.", body)
        self.assertIn(content, body)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
