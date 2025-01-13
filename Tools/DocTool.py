import os
import json
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

class DocAPI:
    # 1. CRITICAL: Accept Credentials object
    def __init__(self, credentials: Credentials):
        """Initialize with a guaranteed valid Credentials object."""
        self.creds = credentials # Store the credentials object
    
    def get_recent_google_docs(self, limit=10):
        # Service creation must now use self.creds
        service = build("drive", "v3", credentials=self.creds)
        try:
            query = "mimeType='application/vnd.google-apps.document'"
            results = service.files().list(
                q=query,
                orderBy="viewedByMeTime desc",
                pageSize=limit,
                fields="files(id, name, viewedByMeTime)"
            ).execute()

            files = results.get("files", [])
            return files

        except HttpError as error:
            raise RuntimeError(f"❌ Google Drive API error: {error}")
    
    def resolve_file_name_to_id(self, file_name):
        drive_service = build("drive", "v3", credentials=self.creds)
        print("Resolving the file id...")
        try:
            query = f"name = '{file_name}' and mimeType = 'application/vnd.google-apps.document'"
            results = drive_service.files().list(
                q=query,
                spaces="drive",
                fields="files(id, name)",
                pageSize=1
            ).execute()
            files = results.get("files", [])

            if not files:
                print(f"❌ No document found with name: {file_name}")
                return None

            return files[0]["id"]

        except HttpError as error:
            print(f"❌ Failed to resolve file name: {error}")
            return None
                
    def create_google_doc(self, title="New Document", initial_content=None):
        service = build("docs", "v1", credentials=self.creds)
        print("Creating the new document...")

        try:
            document = service.documents().create(body={"title": title}).execute()
            doc_id = document.get("documentId")
            doc_link = f"https://docs.google.com/document/d/{doc_id}"

            print(f"📄 Google Doc '{title}' created successfully!")
            print(f"🔗 View Document: {doc_link}")

            if initial_content:
                requests = [{
                    "insertText": {
                        "location": {"index": 1},
                        "text": f"{initial_content}\n"
                    }
                }]
                service.documents().batchUpdate(
                    documentId=doc_id, body={"requests": requests}
                ).execute()
                print("📝 Initial content added.")

            return doc_id, doc_link

        except Exception as e:
            print(f"❌ Failed to create document: {e}")
            return None, None
        
    def get_google_doc_content(self, doc_id):
        service = build("docs", "v1", credentials=self.creds)
        print("Retrieving document content...")

        try:
            doc = service.documents().get(documentId=doc_id).execute()
            content = doc.get("body", {}).get("content", [])

            text = ""
            for element in content:
                if "paragraph" in element:
                    for part in element["paragraph"].get("elements", []):
                        if "textRun" in part:
                            text += part["textRun"].get("content", "")

            return text.strip()

        except Exception as e:
            print(f"❌ Failed to retrieve document content: {e}")
            return ""

    def add_to_google_doc(self, doc_id, text, location="end"):
        service = build("docs", "v1", credentials=self.creds)
        print("Adding content...")

        doc = service.documents().get(documentId=doc_id).execute()
        end_index = doc.get("body", {}).get("content", [])[-1]["endIndex"] - 1

        requests = [{
            "insertText": {
                "location": {"index": end_index},
                "text": f"\n{text}\n"
            }
        }]

        service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests}
        ).execute()

        print(f"✅ Text appended successfully to Google Doc: {doc_id}")

    def delete_google_doc(self, doc_id):
        print("Deleting the document...")
        drive_service = build("drive", "v3", credentials=self.creds)
        try:
            drive_service.files().delete(fileId=doc_id).execute()
            print(f"🗑️ Deleted Google Doc (file): {doc_id}")
        except HttpError as error:
            print(f"❌ Failed to delete document: {error}")

    def edit_google_doc(self, doc_id, text):
        service = build("docs", "v1", credentials=self.creds)
        print("Editing the document...")

        doc = service.documents().get(documentId=doc_id).execute()
        end_index = doc['body']['content'][-1]['endIndex']

        requests = [
            {
                "deleteContentRange": {
                    "range": {
                        "startIndex": 1,
                        "endIndex": end_index - 1
                    }
                }
            },
            {
                "insertText": {
                    "location": {"index": 1},
                    "text": text
                }
            }
        ]

        service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
