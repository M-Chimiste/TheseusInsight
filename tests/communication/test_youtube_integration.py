import unittest
from unittest.mock import patch, MagicMock
import os
import pickle # For mocking credentials

# Assuming the function is in this path, adjust if necessary
from theseus_insight.communication.youtube_integration import upload_video_to_youtube, get_youtube_credentials, YOUTUBE_UPLOADER_CLIENT_SECRET_FILE, YOUTUBE_UPLOADER_CREDENTIALS_PICKLE_FILE

class TestYoutubeIntegration(unittest.TestCase):

    def setUp(self):
        self.video_file = "test_video.mp4"
        self.title = "Test Video Title"
        self.description = "Test video description."
        self.playlist_id = "test_playlist_id"
        self.tags = ["test", "video"]

        # Create a dummy video file for tests that might need it
        with open(self.video_file, "w") as f:
            f.write("dummy video data")

        # Clean up env vars or files that might interfere
        if os.path.exists(YOUTUBE_UPLOADER_CREDENTIALS_PICKLE_FILE):
            os.remove(YOUTUBE_UPLOADER_CREDENTIALS_PICKLE_FILE)
        if os.path.exists(YOUTUBE_UPLOADER_CLIENT_SECRET_FILE):
            # If a real one exists, we should back it up and restore,
            # or ensure tests use a mock path for it. For now, just trying to remove if it was created by a test.
            pass


    def tearDown(self):
        if os.path.exists(self.video_file):
            os.remove(self.video_file)
        if os.path.exists(YOUTUBE_UPLOADER_CREDENTIALS_PICKLE_FILE):
            os.remove(YOUTUBE_UPLOADER_CREDENTIALS_PICKLE_FILE)
        # Restore client secret if it was part of test specific setup
        # For now, assume it's not managed by these unit tests directly

    @patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file')
    @patch('pickle.dump')
    @patch('builtins.open', new_callable=unittest.mock.mock_open) # Mock open for writing pickle
    def test_get_youtube_credentials_new_flow(self, mock_open_call, mock_pickle_dump, mock_from_client_secrets):
        mock_flow_instance = MagicMock()
        mock_flow_instance.run_local_server.return_value = "mock_credentials"
        mock_from_client_secrets.return_value = mock_flow_instance
        
        # Create a dummy client secret file for the function to "find"
        with patch('os.path.exists', side_effect=lambda path: YOUTUBE_UPLOADER_CLIENT_SECRET_FILE in path):
             # First call: no pickle, run flow
            creds = get_youtube_credentials()

        self.assertEqual(creds, "mock_credentials")
        mock_from_client_secrets.assert_called_once_with(
            YOUTUBE_UPLOADER_CLIENT_SECRET_FILE,
            scopes=['https://www.googleapis.com/auth/youtube.upload']
        )
        mock_flow_instance.run_local_server.assert_called_once_with(port=0)
        # Check that pickle.dump was called to save credentials
        mock_open_call.assert_called_with(YOUTUBE_UPLOADER_CREDENTIALS_PICKLE_FILE, 'wb')
        mock_pickle_dump.assert_called_once_with("mock_credentials", mock_open_call().__enter__())


    @patch('pickle.load')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    def test_get_youtube_credentials_from_pickle(self, mock_open_call, mock_pickle_load):
        mock_creds_from_pickle = MagicMock()
        mock_creds_from_pickle.valid = True # Assume valid credentials
        mock_creds_from_pickle.expired = False
        mock_creds_from_pickle.refresh_token = True # Assume refreshable

        mock_pickle_load.return_value = mock_creds_from_pickle
        
        # Simulate that the pickle file exists, but client secret doesn't (shouldn't matter for this path)
        def os_path_exists_side_effect(path):
            if path == YOUTUBE_UPLOADER_CREDENTIALS_PICKLE_FILE:
                return True
            return False

        with patch('os.path.exists', side_effect=os_path_exists_side_effect):
            creds = get_youtube_credentials()

        self.assertEqual(creds, mock_creds_from_pickle)
        mock_open_call.assert_called_with(YOUTUBE_UPLOADER_CREDENTIALS_PICKLE_FILE, 'rb')
        mock_pickle_load.assert_called_once_with(mock_open_call().__enter__())
        self.assertFalse(mock_creds_from_pickle.refresh.called) # Should not refresh if valid and not expired

    @patch('pickle.load')
    @patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file') # For refresh
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    def test_get_youtube_credentials_pickle_expired_refresh(self, mock_open_call, mock_from_client_secrets, mock_pickle_load):
        mock_creds_from_pickle = MagicMock()
        mock_creds_from_pickle.valid = True # Or False if refresh is always needed for expired
        mock_creds_from_pickle.expired = True
        mock_creds_from_pickle.refresh_token = "fake_refresh_token" # Needs a refresh token
        
        mock_pickle_load.return_value = mock_creds_from_pickle
        
        # Simulate pickle file exists, and client secret also exists for refresh
        def os_path_exists_side_effect(path):
            if path == YOUTUBE_UPLOADER_CREDENTIALS_PICKLE_FILE: return True
            if path == YOUTUBE_UPLOADER_CLIENT_SECRET_FILE: return True # Needed for refresh
            return False

        with patch('os.path.exists', side_effect=os_path_exists_side_effect), \
             patch('pickle.dump') as mock_pickle_dump_refresh: # To mock saving refreshed creds
            
            creds = get_youtube_credentials()

        self.assertEqual(creds, mock_creds_from_pickle)
        mock_creds_from_pickle.refresh.assert_called_once() # Check refresh was called
        # Check that refreshed credentials were saved
        mock_open_call.assert_any_call(YOUTUBE_UPLOADER_CREDENTIALS_PICKLE_FILE, 'wb')
        mock_pickle_dump_refresh.assert_called_with(mock_creds_from_pickle, mock_open_call().__enter__())


    @patch('theseus_insight.communication.youtube_integration.get_youtube_credentials')
    @patch('googleapiclient.discovery.build')
    @patch('googleapiclient.http.MediaFileUpload')
    def test_upload_video_to_youtube_success(self, mock_media_file_upload, mock_build, mock_get_credentials):
        mock_credentials = MagicMock()
        mock_get_credentials.return_value = mock_credentials

        mock_youtube_service = MagicMock()
        mock_build.return_value = mock_youtube_service
        
        mock_media_file = MagicMock()
        mock_media_file_upload.return_value = mock_media_file

        mock_insert_request = MagicMock()
        mock_youtube_service.videos.return_value.insert.return_value = mock_insert_request
        
        mock_upload_response = {"id": "new_video_id", "status": {"uploadStatus": "uploaded"}}
        mock_insert_request.execute.return_value = mock_upload_response

        video_id = upload_video_to_youtube(self.video_file, self.title, self.description, self.playlist_id, self.tags)

        self.assertEqual(video_id, "new_video_id")
        mock_get_credentials.assert_called_once()
        mock_build.assert_called_once_with('youtube', 'v3', credentials=mock_credentials)
        mock_media_file_upload.assert_called_once_with(self.video_file, chunksize=-1, resumable=True)
        
        expected_body = {
            'snippet': {
                'title': self.title,
                'description': self.description,
                'tags': self.tags,
                'categoryId': '28'  # Science & Technology
            },
            'status': {
                'privacyStatus': 'private',  # Default privacy status
                'selfDeclaredMadeForKids': False 
            }
        }
        mock_youtube_service.videos.return_value.insert.assert_called_once_with(
            part=','.join(expected_body.keys()), # snippet,status
            body=expected_body,
            media_body=mock_media_file
        )
        mock_insert_request.execute.assert_called_once()

        # Test adding to playlist
        mock_youtube_service.playlistItems.return_value.insert.assert_called_once()
        playlist_insert_args = mock_youtube_service.playlistItems.return_value.insert.call_args[1]['body']
        self.assertEqual(playlist_insert_args['snippet']['playlistId'], self.playlist_id)
        self.assertEqual(playlist_insert_args['snippet']['resourceId']['videoId'], "new_video_id")


    @patch('theseus_insight.communication.youtube_integration.get_youtube_credentials')
    @patch('googleapiclient.discovery.build')
    @patch('logging.error')
    def test_upload_video_to_youtube_api_error(self, mock_logging_error, mock_build, mock_get_credentials):
        mock_get_credentials.return_value = MagicMock()
        mock_youtube_service = MagicMock()
        mock_build.return_value = mock_youtube_service

        # Simulate an API error during video insert
        from googleapiclient.errors import HttpError
        mock_youtube_service.videos.return_value.insert.side_effect = HttpError(
            resp=MagicMock(status=403, reason="Forbidden"),
            content=b'{"error": {"message": "API error"}}'
        )

        video_id = upload_video_to_youtube(self.video_file, self.title, self.description, self.playlist_id, self.tags)

        self.assertIsNone(video_id)
        mock_logging_error.assert_called()
        # Check that the error message logged contains relevant info
        self.assertIn("Failed to upload video", mock_logging_error.call_args[0][0])
        self.assertIn("API error", mock_logging_error.call_args[0][0])


    @patch('theseus_insight.communication.youtube_integration.get_youtube_credentials', return_value=None) # No creds
    @patch('logging.error')
    def test_upload_video_no_credentials(self, mock_logging_error, mock_get_creds_none):
        video_id = upload_video_to_youtube(self.video_file, self.title, self.description, self.playlist_id, self.tags)
        self.assertIsNone(video_id)
        mock_logging_error.assert_called_with("Failed to get YouTube credentials. Video upload aborted.")

    def test_upload_video_file_not_found(self):
        with patch('logging.error') as mock_logging_error:
            video_id = upload_video_to_youtube("non_existent_file.mp4", self.title, self.description, self.playlist_id, self.tags)
        self.assertIsNone(video_id)
        mock_logging_error.assert_called_with("Video file non_existent_file.mp4 not found.")


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
