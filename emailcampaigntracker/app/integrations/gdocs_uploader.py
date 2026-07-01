import io
import os
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials

logger = logging.getLogger("gdocs_uploader")

ENV_PATH = r"c:\git\emailcampaigntracker\.env"

def load_env(env_path):
    env = {}
    if not os.path.exists(env_path):
        return env
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                v = v.strip()
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                env[k.strip()] = v
    return env

def upload_to_gdocs(title: str, html_content: str) -> str:
    """Uploads HTML content to Google Drive, converts it to Google Docs format, shares it, and returns the URL."""
    try:
        env = load_env(ENV_PATH)
        scope = [
            "https://www.googleapis.com/auth/drive",
        ]
        from google.oauth2.credentials import Credentials as UserCredentials
        token_path = env.get("GMAIL_OAUTH_CREDENTIALS_PATH", r"C:\git\emailcampaigntracker\gmail_token.json")
        user_creds = None
        if os.path.exists(token_path):
            try:
                user_creds = UserCredentials.from_authorized_user_file(token_path, scope)
                print(f"Using User OAuth credentials from: {token_path}")
            except Exception as ue:
                print(f"  Warning: Could not load user credentials ({ue})")

        # Define service account info dictionary
        info = {
            "type": env.get("GOOGLE_TYPE"),
            "project_id": env.get("GOOGLE_PROJECT_ID"),
            "private_key_id": env.get("GOOGLE_PRIVATE_KEY_ID"),
            "private_key": env.get("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n"),
            "client_email": env.get("GOOGLE_CLIENT_EMAIL"),
            "client_id": env.get("GOOGLE_CLIENT_ID"),
            "auth_uri": env.get("GOOGLE_AUTH_URI"),
            "token_uri": env.get("GOOGLE_TOKEN_URI"),
            "auth_provider_x509_cert_url": env.get("GOOGLE_AUTH_PROVIDER_CERT_URL"),
            "client_x509_cert_url": env.get("GOOGLE_CLIENT_CERT_URL"),
            "universe_domain": env.get("GOOGLE_UNIVERSE_DOMAIN"),
        }

        drive_service = None
        if user_creds:
            try:
                # Test refreshing the token to trigger RefreshError early and catch it
                from google.auth.transport.requests import Request
                user_creds.refresh(Request())
                drive_service = build('drive', 'v3', credentials=user_creds)
            except Exception as re:
                print(f"  Warning: Failed to refresh/use User credentials ({re}). Falling back to Service Account...")
                user_creds = None

        if not drive_service:
            print("Using Google Sheets Service Account credentials...")
            creds = Credentials.from_service_account_info(info, scopes=scope)
            drive_service = build('drive', 'v3', credentials=creds)

        file_metadata = {
            'name': title,
            'mimeType': 'application/vnd.google-apps.document'
        }
        
        # Avoid storageQuotaExceeded error by saving inside a folder shared by the user.
        # This bills storage to the folder owner instead of the Service Account.
        folder_id = env.get("GOOGLE_DRIVE_FOLDER_ID")
        if folder_id:
            file_metadata['parents'] = [folder_id]
            print(f"  Saving document inside configured shared folder ID: {folder_id}")
        else:
            sheet_id = env.get("GOOGLE_SHEET_ID")
            if sheet_id:
                try:
                    sheet_metadata = drive_service.files().get(fileId=sheet_id, fields='parents', supportsAllDrives=True).execute()
                    parents = sheet_metadata.get('parents', [])
                    if parents:
                        file_metadata['parents'] = parents
                        print(f"  Saving document inside sheet parent folder: {parents[0]}")
                except Exception as pe:
                    print(f"  Warning: Could not fetch spreadsheet parents ({pe})")

        # Google Drive converts mimetype='text/html' directly into a formatted Google Doc
        media = MediaIoBaseUpload(io.BytesIO(html_content.encode('utf-8')), mimetype='text/html')
        
        print(f"Uploading merged report '{title}' to Google Docs...")
        file = drive_service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id',
            supportsAllDrives=True
        ).execute()
        file_id = file.get('id')
        
        # Share the document so that anyone with the link can view/edit
        permission = {
            'type': 'anyone',
            'role': 'reader',
        }
        drive_service.permissions().create(
            fileId=file_id, 
            body=permission,
            supportsAllDrives=True
        ).execute()
        
        doc_url = f"https://docs.google.com/document/d/{file_id}/edit"
        print(f"Uploaded successfully! Link: {doc_url}")
        return doc_url
        
    except Exception as e:
        logger.exception("Failed to upload document to Google Docs")
        print(f"Error uploading to Google Docs: {e}")
        raise e
