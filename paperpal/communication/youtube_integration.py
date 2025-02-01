import os

# 1) Load environment variables
from dotenv import load_dotenv
load_dotenv()

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.http
import google.auth.transport.requests
from google.oauth2.credentials import Credentials

# If modifying these scopes, delete the existing token.json.
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def get_authenticated_service(token_file="client_secret.json"):
    """
    Authenticates and returns a YouTube API client service using environment variables
    for client ID and client secret.
    """
    # 2) Build the client_config dictionary based on environment variables
    client_config = {
        "web": {
            "client_id": os.getenv("CLIENT_ID", ""),
            "project_id": os.getenv("PROJECT_ID", ""),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": os.getenv("CLIENT_SECRET", ""),
            "redirect_uris": [os.getenv("REDIRECT_URI", "http://localhost")]
        }
    }

    creds = None
    # 3) Check if a token file already exists
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    # 4) If no valid creds, or they are invalid/expired, we need to run OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(google.auth.transport.requests.Request())
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_config(
                client_config, SCOPES
            )
            # run_console() will prompt in the console; 
            # use run_local_server(port=xxxx) for a local browser flow
            creds = flow.run_console()

        # 5) Save the credentials for the next run
        with open(token_file, 'w') as token:
            token.write(creds.to_json())

    # 6) Build the YouTube service object
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
    return youtube

def upload_video(file_path, title, description, category_id="22", privacy_status="public"):
    """
    Uploads a video to the authenticated YouTube channel.
    
    :param file_path: Path to the video file to upload
    :param title: Video title
    :param description: Video description
    :param category_id: Numeric category ID, 22 is default for 'People & Blogs'
    :param privacy_status: 'public', 'private', or 'unlisted'
    """
    youtube = get_authenticated_service()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["podcast"],  # Optional
            "categoryId": category_id
        },
        "status": {
            "privacyStatus": privacy_status
        }
    }

    media = googleapiclient.http.MediaFileUpload(
        file_path,
        chunksize=-1,
        resumable=True
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%.")
        if response is not None:
            if "id" in response:
                print(f"Video id '{response['id']}' was successfully uploaded.")
                return response
            else:
                print("The upload failed with an unexpected response:", response)
                return None

    return response

# if __name__ == "__main__":
#     # Example usage
#     video_path = "/path/to/your/podcast-episode.mp4"
#     video_title = "My Podcast Episode via dotenv"
#     video_description = "Uploaded using environment variables for OAuth credentials."

#     upload_video(
#         file_path=video_path,
#         title=video_title,
#         description=video_description,
#         category_id="22",      # e.g., 'People & Blogs'
#         privacy_status="public"
#     )