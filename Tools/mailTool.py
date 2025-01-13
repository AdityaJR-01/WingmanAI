import os
import logging
import json
from google.oauth2.credentials import Credentials 
from googleapiclient.discovery import build
from googleapiclient import errors
from email.mime.text import MIMEText
import base64
from typing import List, Dict, Optional
import re # Keep re for email parsing
from datetime import datetime, timedelta

class MailTool:
    # 1. CRITICAL: Accept Credentials object
    def __init__(self, credentials: Credentials): 
        """Initialize with a guaranteed valid Credentials object."""
        self.credentials = credentials
        self.service = self._get_service()
        self._contact_cache = {} 
        self.last_error = None

    # 2. Simplied _get_service
    def _get_service(self):
        """Build the Gmail API service using the provided Credentials."""
        try:
            # The credentials object is guaranteed to be refreshed by the Director/Token Manager
            return build("gmail", "v1", credentials=self.credentials)
        except Exception as e:
            logging.error(f"Error building Gmail service: {e}")
            self.last_error = str(e)
            raise
    
    def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send an email via Gmail API."""
        try:
            message = MIMEText(body, 'plain', 'utf-8')
            message["to"] = to
            message["subject"] = subject

            # Preserve line breaks in the email
            raw_message = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode('utf-8')

            self.service.users().messages().send(
                userId="me",
                body={'raw': raw_message}
            ).execute()

            return True

        except Exception as e:
            self.last_error = str(e)
            logging.error(f"Error sending email: {e}")
            return False
            
    # ... All other methods must be checked for self.authenticate() calls and reliance on old token logic.
    # The complexity of the other methods is okay, as long as authentication is clean.
    # For now, we will assume self.service usage is correct in the original code, 
    # but any place it calls self.authenticate() needs to be checked and removed.

    def read_emails(self, query="is:unread", max_results=5, sender_name=None):
        """Fetch emails based on query."""
        try:            
            if sender_name:
                query += f' from:{sender_name}'

            results = self.service.users().messages().list(
                userId="me", q=query, maxResults=max_results
            ).execute()

            messages = results.get("messages", [])
            email_data = []

            for msg in messages:
                msg_data = self.service.users().messages().get(
                    userId="me", id=msg["id"]
                ).execute()
                
                email = self._extract_email_parts(msg_data)
                email_data.append(email)

            return email_data
            
        except Exception as e:
            self.last_error = str(e)
            logging.error(f"Error reading emails: {e}")
            return []

    # Fix for get_unread_emails: remove _get_service check
    def get_unread_emails(self, max_results=5) -> List[Dict]:
        """Get unread emails in a more structured format."""
        try:
            service = self.service # Use the instance variable directly
            results = service.users().messages().list(
                userId='me',
                labelIds=['UNREAD'],
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            emails = []
            
            for message in messages:
                msg = service.users().messages().get(
                    userId='me',
                    id=message['id'],
                    format='full'
                ).execute()
                
                # Extract email details
                headers = msg['payload']['headers']
                email_data = {
                    'id': message['id'],
                    'sender': next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown'),
                    'subject': next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject'),
                    'body': self._get_email_body(msg),
                    'thread_id': msg['threadId']
                }
                
                # Clean up sender name (extract from email format if needed)
                if '<' in email_data['sender']:
                    email_data['sender'] = email_data['sender'].split('<')[0].strip()
                
                emails.append(email_data)
            
            return emails
        
        except Exception as e:
            self.last_error = str(e)
            print(f"Error fetching emails: {str(e)}")
            return []
            
    # Fix for get_sender_profile: remove _get_service check
    def get_sender_profile(self) -> dict:
        """Get sender's profile information."""
        try:
            profile = self.service.users().getProfile(userId='me').execute()
            
            # Get display name from email address if settings.get() is not available
            display_name = profile.get('emailAddress', '').split('@')[0].replace('.', ' ').title()
            
            return {
                'email': profile.get('emailAddress'),
                'name': display_name
            }
        
        except Exception as e:
            self.last_error = str(e)
            print(f"Error getting sender profile: {e}")
            return {
                'email': None,
                'name': "User"
            }

    def _get_email_body(self, message) -> str:
        """Extract email body in a cleaner format."""
        try:
            if 'parts' in message['payload']:
                for part in message['payload']['parts']:
                    if part['mimeType'] == 'text/plain':
                        return base64.urlsafe_b64decode(
                            part['body']['data'].encode('ASCII')
                        ).decode('utf-8').strip()
            elif 'body' in message['payload']:
                return base64.urlsafe_b64decode(
                    message['payload']['body']['data'].encode('ASCII')
                ).decode('utf-8').strip()
            return "No readable content"
        except Exception as e:
            print(f"Error extracting email body: {str(e)}")
            return "Error extracting content"
 
    def decode_base64(self, data):
        """Decode base64-encoded email body text."""
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    
    def _extract_email_parts(self, msg_data):
        """Extract relevant parts from email data."""
        headers = msg_data["payload"]["headers"]
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown Sender")
        date = next((h["value"] for h in headers if h["name"] == "Date"), "")

        # Extract body
        body = self._get_email_body(msg_data["payload"])

        return {
            "id": msg_data["id"],
            "thread_id": msg_data["threadId"],
            "subject": subject,
            "sender": sender,
            "date": date,
            "body": body
        }
    
    def mark_as_read(self, email_ids):
        """Mark emails as read."""
        try:
            if isinstance(email_ids, str):
                email_ids = [email_ids]
                
            for email_id in email_ids:
                self.service.users().messages().modify(
                    userId="me",
                    id=email_id,
                    body={"removeLabelIds": ["UNREAD"]}
                ).execute()
            return True
        except Exception as e:
            print(f"Error marking emails as read: {e}")
            return False
        
    def get_emails_from_sender(self, sender_email: str, max_results: int = 10) -> List[Dict]:
        """Fetch emails from a specific sender."""
        try:
            # Handle partial email addresses or names
            if '@' not in sender_email:
                query = f"from:*{sender_email}*"
            else:
                query = f"from:{sender_email}"

            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()

            messages = results.get('messages', [])
            emails = []

            for message in messages:
                email_data = self.service.users().messages().get(
                    userId='me',
                    id=message['id'],
                    format='full'
                ).execute()
                
                email = self._extract_email_parts(email_data)
                emails.append(email)

            return emails

        except Exception as e:
            print(f"Error fetching emails from {sender_email}: {e}")
            return []

    def search_emails(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search emails using Gmail's search syntax."""
        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()

            messages = results.get('messages', [])
            emails = []

            for message in messages:
                email_data = self.service.users().messages().get(
                    userId='me',
                    id=message['id'],
                    format='full'
                ).execute()
                
                email = self._extract_email_parts(email_data)
                emails.append(email)

            return emails

        except Exception as e:
            print(f"Error searching emails: {e}")
            return []

    def reply_to_email(self, message_id: str, to: str, body: str) -> bool:
        """Reply to an existing email."""
        try:
            # Get the original message to extract thread ID and subject
            original = self.service.users().messages().get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["Subject", "References", "Message-ID"]
            ).execute()

            # Get the subject
            headers = original["payload"]["headers"]
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "")
            if not subject.startswith("Re:"):
                subject = f"Re: {subject}"

            # Create reply message
            message = MIMEText(body)
            message["to"] = to
            message["subject"] = subject
            
            # Add threading headers
            message["In-Reply-To"] = message_id
            references = next((h["value"] for h in headers if h["name"] == "References"), "")
            if references:
                message["References"] = f"{references} {message_id}"
            else:
                message["References"] = message_id

            # Encode and send
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            self.service.users().messages().send(
                userId="me",
                body={
                    "raw": raw_message,
                    "threadId": original["threadId"]
                }
            ).execute()

            return True

        except Exception as e:
            print(f"Error replying to email: {e}")
            return False

    def get_thread(self, thread_id: str) -> List[Dict]:
        """Get all messages in a thread."""
        try:
            thread = self.service.users().threads().get(
                userId='me',
                id=thread_id,
                format='full'
            ).execute()

            emails = []
            for message in thread['messages']:
                email = self._extract_email_parts(message)
                emails.append(email)

            return emails

        except Exception as e:
            print(f"Error fetching thread: {e}")
            return []
        
    def get_recent_emails(self, days: int = 7, max_results: int = 10) -> List[Dict]:
        """Get recent emails from the last X days."""
        try:
            after_date = datetime.now() - timedelta(days=days)
            query = f"after:{after_date.strftime('%Y/%m/%d')}"
            
            return self.search_emails(query, max_results)

        except Exception as e:
            print(f"Error fetching recent emails: {e}")
            return []

    def get_email_suggestions(self, name_query: str) -> list:
        """Get email suggestions based on name query."""
        try:
            # First check cache
            if name_query.lower() in self._contact_cache:
                return self._contact_cache[name_query.lower()]

            # Search in sent and received emails
            query = f"from:{name_query} OR to:{name_query}"
            results = self.service.users().messages().list(
                userId="me",
                q=query,
                maxResults=10
            ).execute()

            messages = results.get("messages", [])
            email_addresses = set()

            for msg in messages:
                email_data = self.service.users().messages().get(
                    userId="me",
                    id=msg["id"],
                    format="metadata",
                    metadataHeaders=["From", "To"]
                ).execute()

                headers = email_data["payload"]["headers"]
                
                for header in headers:
                    if header["name"] in ["From", "To"]:
                        addresses = self._extract_email_addresses(header["value"])
                        for name, email in addresses:
                            if name_query.lower() in name.lower():
                                email_addresses.add((name, email))

            # Filter out system emails and cache results
            valid_emails = [
                (name, email) for name, email in email_addresses 
                if not any(x in email.lower() for x in [
                    'noreply', 'linkedin', 'drive-shares', 
                    'invitations', 'maps.google'
                ])
            ]
            
            self._contact_cache[name_query.lower()] = valid_emails
            return valid_emails

        except Exception as e:
            print(f"Error getting email suggestions: {e}")
            return []

    def _extract_email_addresses(self, header_value: str) -> list:
        """Extract name and email from header value."""
        results = []
        # Handle multiple addresses separated by commas
        for addr in header_value.split(","):
            addr = addr.strip()
            # Match patterns like: "Name <email@domain.com>" or "email@domain.com"
            if "<" in addr and ">" in addr:
                name = addr[:addr.find("<")].strip()
                email = addr[addr.find("<")+1:addr.find(">")].strip()
                results.append((name, email))
            else:
                results.append((addr, addr))
        return results

    def resolve_email_address(self, name_or_email: str) -> str:
        """Resolve a name or partial email to a full email address."""
        if "@" in name_or_email:
            return name_or_email

        suggestions = self.get_email_suggestions(name_or_email)
        if suggestions:
            return suggestions[0][1]  # Return the exact email address
        
        return None
