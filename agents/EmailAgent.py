import os
from openai import OpenAI
from dotenv import load_dotenv
from Tools.mailTool import MailTool # Corrected import path for clarity
from typing import List, Dict, Optional, Any
import json
from google.oauth2.credentials import Credentials # NEW: Import Credentials for type hinting
import logging

# Load .env file (Still needed for OPENAI_API_KEY)
load_dotenv()

class EmailAgent:
    def __init__(self, credentials: Credentials): 
        """Initialize EmailAgent with its own MailTool instance, using credentials."""
        
        # 2. CRITICAL FIX: Pass the credentials to the MailTool
        self.mail_tool = MailTool(credentials=credentials) 
        
        self.credentials = credentials # Store locally if needed for future functions
        self.last_emails = []  # Will store the last fetched emails
        self._pending_email = {} # Added instance variable for clarity
        
        # 3. Setup LLM client (Still relies on .env for API key)
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # 4. Get sender's name (Logic is fine, relies on refactored MailTool)
        self.sender_name = self._get_sender_name() 

        # --- Prompts remain the same ---
        self.compose_prompt = f"""
        You are an AI email assistant. Format emails professionally with clear structure:
        1. Start with an appropriate greeting (e.g., "Hi [name]," or "Dear [name],")
        2. Skip a line after greeting
        3. Write the main content in clear paragraphs
        4. Skip a line before the sign-off
        5. End with an appropriate closing (e.g., "Best regards," or "Thanks,") followed by the sender's name

        Current sender's name: {self.sender_name}

        Format the email with proper line breaks using \n for new lines.
        """
        self.system_prompt = """
        You are an email assistant. Analyze user requests and help manage emails.
        Keep responses conversational and match the user's tone.
        
        For email summaries:
        - Focus on the key message or request
        - Use natural language
        - Keep it brief but informative
        - Start with the sender's name
        
        Example summaries:
        "John's asking about the project deadline and needs your update by tomorrow"
        "Sarah shared the meeting notes from yesterday's team sync"
        """
    
    # --------------------------------------------------------------------------
    # NOTE: The method name 'EmailAgent' below must be renamed to adhere to Python standards
    # and to avoid confusion with the class name. We will rename it to '_analyze_query_to_json'.
    # --------------------------------------------------------------------------

    # Renamed the method and wrapped it in a consistent try/except
    def _analyze_query_to_json(self, user_query):
        system_prompt = system_prompt = (
    "You are an intelligent Email Agent that helps users manage their emails effectively.\n\n"

    "Your job is to **understand the user's request** and output a **valid JSON object** with exactly two keys:\n"
    "{\n"
    '  "action": "action_type",\n'
    '  "params": { key-value pairs based on the action }\n'
    "}\n\n"

    "Supported actions (as string values under the 'action' key):\n"
    "- \"send\": Compose and send a new email\n"
    "- \"reply\": Reply to a specific email\n"
    "- \"forward\": Forward an email to someone else\n"
    "- \"read\": Show unread or specific emails\n"
    "- \"delete\": Delete an email by ID or subject\n"
    "- \"search\": Search emails based on sender, subject, or keyword\n\n"

    "The `params` dictionary can include the following keys, depending on the action:\n"
    "- \"to\": recipient email address(es) (for send, forward)\n"
    "- \"subject\": subject line (for send, search, delete)\n"
    "- \"body\": content of the message (for send, reply, forward)\n"
    "- \"message_id\": unique ID of the email (for reply, forward, delete)\n"
    "- \"sender\": sender's name or email (for search, read)\n"
    "- \"query\": short summary of what the message should say (if no full body is provided)\n"
    "- \"date_range\": time filter for search/read, like \"last week\" or \"today\"\n\n"

    "Always return values in **pure JSON format** with double quotes and no explanations or markdown.\n\n"

    "Examples:\n\n"

    "User: 'Send an email to Alex about the demo on Friday'\n"
    "Output:\n"
    '{\n'
    '  "action": "send",\n'
    '  "params": {\n'
    '    "to": "Alex",\n'
    '    "subject": "Demo on Friday",\n'
    '    "query": "Inform Alex about the upcoming demo on Friday."\n'
    '  }\n'
    '}\n\n'

    "User: 'Reply to John's email with a thank you note'\n"
    "Output:\n"
    '{\n'
    '  "action": "reply",\n'
    '  "params": {\n'
    '    "sender": "John",\n'
    '    "query": "Thank you for your message.",\n'
    '    "message_id": "REQUIRED_FROM_SYSTEM_CONTEXT"\n'
    '  }\n'
    '}\n\n'

    "If any required details (like message_id) are missing, fill in what you can and use placeholder like default or leave them out.\n"
    "Do not include any text outside the JSON block."
)

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ]
            )
            content = response.choices[0].message.content            
            # Use the clean method to parse JSON
            if content.startswith("```json"):
                content = content.replace("```json", "").strip()
            if content.endswith("```"):
                content = content[:-3].strip()
            return json.loads(content)
        except Exception as e:
            logging.error(f"Error parsing LLM response in Email Agent: {e}")
            return {"error": "⚠ Invalid response format or API error."}

    # CRITICAL: This method name is standardized for all Field Agents
    def handle_query(self, user_query) -> str:
        """Handle incoming query from the Director, analyze it, and execute the action."""
        # 1. Analyze the query to get the structured task
        task = self._analyze_query_to_json(user_query) # Use the renamed function
        if task.get("error"):
            return f"Error analyzing request: {task['error']}"
        action = task.get("action")
        params = task.get("params")
        logging.info(f"EmailAgent executing action: {action} with params: {params}")
        # 2. Execute the action
        response = self.handle_action(action, params)
        return response
    
    def handle_action(self, action, params):
        if action == "read":
            # If no specific sender is provided, list all unread emails
            if not params.get("sender"):
                return self._handle_read_emails(params.get("max_results", 5))
            # If sender is provided, show that specific email
            return self._handle_specific_email(params.get("sender"))

        elif action == "send":
            # Get recipient info
            to_email = params.get("to")
            if not to_email:
                return "I need a recipient's email address or name to send the email."

            # Get the email content
            email_context = params.get("query")
            if not email_context:
                return "I need the content for the email. What would you like me to write?"
                # If it's an email address, use it directly; otherwise try to find it
            if '@' not in to_email:
                contact_suggestions = self._suggest_contacts(to_email)
                if "No contacts found" in contact_suggestions:
                    # Store the current request for later use
                    self._pending_email = {
                        "content": email_context,
                        "recipient_name": to_email
                    }
                    return f"I couldn't find an email address for {to_email}. Could you please provide their email address?"
                elif "\n" in contact_suggestions:  # Multiple contacts found
                    return f"I found multiple possible contacts:\n{contact_suggestions}\nWhich email should I use?"
                else:
                    # Extract email from the single suggestion
                    to_email = contact_suggestions.split('<')[1].split('>')[0]

                # Compose the email
            composed = self.compose_email(
                to=to_email,
                subject=None,  # Will be generated based on content
                content_prompt=email_context
            )
                
            if composed["status"] == "error":
                return f"Sorry, I had trouble composing the email: {composed['error']}"

            # Show preview to user
            preview = f"""
                Here's the email I've composed:

                To: {to_email}
                Subject: {composed['subject']}

                {composed['body']}

                Should I send this email? (Please respond with 'yes' to send or provide any changes needed)"""

            print(preview)
            reply = input()
            if reply == "yes":
                # Send the email using MailTool
                success = self.mail_tool.send_email(
                    to=to_email,
                    subject=composed["subject"],
                    body=composed["body"]
                )

                if success:
                    return f"✉️ Email sent successfully to {to_email}!"
                else:
                    return f"Sorry, couldn't send the email: {self.mail_tool.last_error}"
                
                # Store the composed email for later sending
            self._pending_email = {
                "composed_email": composed,
                "to_email": to_email,
                "awaiting_approval": True
            }
                
            return preview

        elif action == "reply":
            # Handle email replies using compose_and_reply
            original_message_id = params.get("message_id")
            to_email = params.get("to")
            content = params.get("query")
                
            if not all([original_message_id, to_email, content]):
                return "I need the original message ID, recipient's email, and reply content to send a reply."
            
            # Compose and send the reply
            result = self.compose_and_reply(
                original_message_id=original_message_id,
                to=to_email,
                content_prompt=content
            )
                
            if result["status"] == "success":
                return f"✉️ Reply sent successfully to {to_email}!"
            else:
                return f"Sorry, couldn't send the reply: {result['error']}"

        else:
            return "I'm not sure what you want me to do with the emails. Could you be more specific?"

    def _handle_read_emails(self, max_results: int = 5) -> str:
        """Handle requests to read emails."""
        try:
            # Always refresh the email list when explicitly checking
            self.last_emails = self.mail_tool.get_unread_emails(max_results)
            
            if not self.last_emails:
                return "No unread emails at the moment! 📭"
                
            # Format emails in a conversational way
            senders = []
            for email in self.last_emails:
                sender = email['sender']
                # Clean up sender name
                sender = sender.replace('"', '').strip()
                if '<' in sender:
                    sender = sender.split('<')[0].strip()
                senders.append(sender)

            if len(senders) == 1:
                return f"You've got an unread email from {senders[0]}! Want me to tell you what it's about? 📧"
            else:
                sender_list = ", ".join(senders[:-1]) + f" and {senders[-1]}"
                return f"You've got {len(senders)} unread emails from {sender_list}! Which one you wanna hear about? 📧"

        except Exception as e:
            return f"Had trouble checking your emails: {str(e)}"

    def _handle_specific_email(self, sender: str) -> str:
        """Handle requests for specific emails."""
        try:
            if not self.last_emails:
                self.last_emails = self.mail_tool.get_unread_emails()
                if not self.last_emails:
                    return "No unread emails at the moment! 📭"

            # Find exact sender match
            for email in self.last_emails:
                if sender.lower() in email['sender'].lower():
                    # Store the complete email context for potential replies
                    if hasattr(self, '_director'):
                        # Clean up the sender email if it's in angle brackets format
                        sender_email = email['sender']
                        if '<' in sender_email:
                            sender_email = sender_email.split('<')[1].split('>')[0]
                        
                        self._director.last_email_context = {
                            "id": email.get("id"),
                            "sender": sender_email,  # Store clean email address
                            "subject": email.get("subject"),
                            "body": email.get("body"),
                            "thread_id": email.get("thread_id")  # Store thread ID if available
                        }
                    
                    # Use the summarize function instead of showing full content
                    summary = self._summarize_email(email)
                    return f"Here's what {email['sender'].split('<')[0].strip()} said:\n\n{summary}\n\nWant me to reply to this email? 📝"
            
            return f"I don't see any emails from {sender} in the current unread messages. 🤔"

        except Exception as e:
            return f"Had trouble getting that email details: {str(e)}"

    def _summarize_email(self, email: dict) -> str:
        """Create a summary of an email."""
        try:
            messages = [
                {"role": "system", "content": """
                Summarize the email content briefly and accurately.
                - Focus on the main message or purpose
                - Don't add information that's not in the email
                - Keep the tone casual but factual
                - Don't make assumptions about content not present
                - Keep it concise but include important details like dates, times, or action items
                """},
                {"role": "user", "content": f"""
                Summarize this email casually:
                From: {email['sender']}
                Subject: {email['subject']}
                Body: {email['body']}
                """}
            ]
            
            completion = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.7
            )
            
            return completion.choices[0].message.content.strip()
        except Exception as e:
            return f"Error summarizing email: {str(e)}"

    def _get_sender_name(self) -> str:
        """Get the sender's full name from Gmail profile."""
        try:
            profile = self.mail_tool.get_sender_profile()
            if profile and profile.get('name'):
                return profile['name']
            return "Anuj Sharad Mankumare"  # Fallback to your full name
        except Exception as e:
            print(f"Error getting sender name: {e}")
            return "Anuj Sharad Mankumare"  # Fallback to your full name

    def compose_email(self, to: str, subject: str, content_prompt: str) -> Dict[str, str]:
        """Compose an email using GPT-4o-mini."""
        try:
            # Generate subject if not provided
            if not subject:
                subject_completion = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Generate a concise email subject line based on the content."},
                        {"role": "user", "content": content_prompt}
                    ]
                )
                subject = subject_completion.choices[0].message.content.strip('"')

            # Get sender name, fallback to a default if not available
            sender_name = self.sender_name or "Anuj Sharad Mankumare"

            messages = [
                {"role": "system", "content": f"""
                You are an AI email assistant. Format emails professionally with clear structure:
                1. Start with an appropriate greeting (e.g., "Hi [name]," or "Dear [name],")
                2. Skip a line after greeting
                3. Write the main content in clear paragraphs
                4. Skip a line before the sign-off
                5. End with an appropriate closing (e.g., "Best regards," or "Thanks,") followed by:
                {sender_name}

                IMPORTANT: Always use the exact name provided above for the signature, never use placeholders like [Your name].
                Format the email with proper line breaks using \n for new lines.
                """},
                {"role": "user", "content": f"Compose an email with the following requirements:\nTo: {to}\nSubject: {subject}\nContent guidelines: {content_prompt}"}
            ]

            completion = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.7
            )

            composed_email = completion.choices[0].message.content

            return {
                "to": to,
                "subject": subject,
                "body": composed_email,
                "status": "success"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    def analyze_email_content(self, email_content: str) -> Dict[str, str]:
        """Analyze email content using GPT-4o-mini."""
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Analyze this email content:\n\n{email_content}"}
            ]

            completion = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages
            )

            analysis = completion.choices[0].message.content

            return {
                "analysis": analysis,
                "status": "success"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    def send_composed_email(self, to: str, subject: str, content_prompt: str) -> Dict[str, str]:
        """Compose and send an email."""
        try:
            # First compose the email
            composed = self.compose_email(to, subject, content_prompt)
            
            if composed["status"] == "error":
                return composed

            # Send the email using MailTool
            success = self.mail_tool.send_email(
                to=to,
                subject=subject,
                body=composed["body"]
            )

            if success:
                return {
                    "status": "success",
                    "message": "Email composed and sent successfully",
                    "email_content": composed["body"]
                }
            else:
                return {
                    "status": "error",
                    "error": "Failed to send email"
                }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    def get_unread_emails(self, max_results: int = 10) -> List[Dict]:
        """Get unread emails and mark them as read."""
        emails = self.mail_tool.get_unread_emails(max_results)
        
        # Analyze each email and mark as read
        analyzed_emails = []
        for email in emails:
            # Analyze the email content
            analysis = self.analyze_email_content(email["body"])
            
            # Mark the email as read
            self.mail_tool.mark_as_read(email["id"])
            
            # Add analysis to email data
            email["analysis"] = analysis.get("analysis", "Analysis failed")
            analyzed_emails.append(email)
        
        return analyzed_emails

    def get_emails_from_sender(self, sender_email: str, max_results: int = 10) -> List[Dict]:
        """Get emails from a specific sender with analysis."""
        emails = self.mail_tool.get_emails_from_sender(sender_email, max_results)
        
        # Analyze each email
        analyzed_emails = []
        for email in emails:
            analysis = self.analyze_email_content(email["body"])
            email["analysis"] = analysis.get("analysis", "Analysis failed")
            analyzed_emails.append(email)
        
        return analyzed_emails

    def compose_and_reply(self, original_message_id: str, to: str, content_prompt: str) -> Dict[str, str]:
        """Compose and send a reply to an email."""
        try:
            # Get the original email's subject from the director's context
            original_subject = ""
            if hasattr(self, '_director') and self._director.last_email_context:
                original_subject = self._director.last_email_context.get("subject", "")
            
            # Ensure subject starts with "Re: " if it doesn't already
            if original_subject:
                if not original_subject.startswith("Re:"):
                    original_subject = f"Re: {original_subject}"
            else:
                original_subject = "Re: Previous Email"

            # First compose the reply
            composed = self.compose_email(
                to=to,
                subject=original_subject,
                content_prompt=content_prompt
            )
            
            if composed["status"] == "error":
                return composed

            # Extract email address from the "to" field if it contains angle brackets
            to_email = to
            if '<' in to:
                to_email = to.split('<')[1].split('>')[0]

            # Send the reply using MailTool
            success = self.mail_tool.reply_to_email(
                message_id=original_message_id,
                to=to_email,
                body=composed["body"]
            )

            if success:
                return {
                    "status": "success",
                    "message": "Reply composed and sent successfully",
                    "email_content": composed["body"]
                }
            else:
                return {
                    "status": "error",
                    "error": "Failed to send reply"
                }

        except Exception as e:
            print(f"Error in compose_and_reply: {str(e)}")  # Add debug print
            return {
                "status": "error",
                "error": str(e)
            }

    def _suggest_contacts(self, partial_name: str) -> str:
        """Get contact suggestions based on partial name."""
        suggestions = self.mail_tool.get_email_suggestions(partial_name)
        if not suggestions:
            return f"No contacts found matching '{partial_name}'"

        response = f"Found these matching contacts for '{partial_name}':\n"
        for name, email in suggestions:
            response += f"- {name} <{email}>\n"
        return response

    def _generate_email_content(self, to: str, context: str, subject: Optional[str] = None) -> Dict[str, Any]:
        """Generate email content using GPT."""
        try:
            messages = [
                {"role": "system", "content": f"""
                You are an email composer. Generate a professional email based on the given context.
                Current sender's name: {self.sender_name}

                1. First, analyze the context to understand:
                   - The purpose of the email
                   - The intended tone (formal/informal)
                   - Key points to be communicated

                2. Then generate a JSON response with:
                   - An appropriate subject line that matches the content
                   - A well-structured email body that includes:
                     * Appropriate greeting
                     * Clear message based on the context
                     * Professional closing
                     * Sender's name

                Return the response in this format:
                {{
                    "subject": "Generated subject line",
                    "body": "Complete email body with proper formatting",
                    "success": true
                }}
                """},
                {"role": "user", "content": f"""
                To: {to}
                Context/Request: {context}
                Subject: {subject if subject else 'Generate appropriate subject'}
                
                Please compose a suitable email based on this context.
                """}
            ]

            completion = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                temperature=0.7
            )

            response = completion.choices[0].message.content
            
            # Parse the JSON response
            if isinstance(response, str):
                if response.startswith("```json"):
                    response = response[7:-3]
                elif response.startswith("```"):
                    response = response[3:-3]
            
            content = json.loads(response.strip())
            
            # Ensure all required fields are present
            if not content.get("subject"):
                # Generate subject from context if none provided
                subject_completion = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Generate a concise, appropriate subject line for this email context."},
                        {"role": "user", "content": context}
                    ]
                )
                content["subject"] = subject_completion.choices[0].message.content.strip()
            
            if not content.get("body"):
                raise ValueError("Generated email body is empty")
            
            content["success"] = True
            return content

        except Exception as e:
            print(f"Error generating email content: {e}")
            return {
                "success": False,
                "error": str(e)
            }
