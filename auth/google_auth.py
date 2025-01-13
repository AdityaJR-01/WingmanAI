from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import json
# Import the new saving function
from auth.token_manager import save_credentials

def login_user(email, selected_apps):
    # Load scopes
    try:
        with open("config/scopes.json") as f:
            scopes_map = json.load(f)
        scopes = [scopes_map[app] for app in selected_apps if app in scopes_map] 
    except FileNotFoundError:
        print("❌ Error: config/scopes.json not found. Cannot proceed with OAuth.")
        return

    try:
        # NOTE: This relies on client_secret.json having an 'installed' or 'web' top-level key.
        flow = InstalledAppFlow.from_client_secrets_file(
            "config/client_secret.json", scopes=scopes)
        
        creds = flow.run_local_server(port=8080) 
    except Exception as e:
        print(f"❌ An error occurred during the OAuth flow: {e}")
        return
    
    # Delegate saving to the Token Manager
    google_data = {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expiry": creds.expiry.isoformat(),
        "scopes": scopes
    }
    save_credentials(email, "google", google_data)