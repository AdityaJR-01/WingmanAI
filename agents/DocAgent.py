import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from google.oauth2.credentials import Credentials
from Tools.DocTool import DocAPI
from auth import token_manager  # 🔹 new import

load_dotenv()

class DocAgent:
    # The REQUIRED_SCOPE is now checked by the Director, but we keep it for reference
    # and potential use in error messages.
    REQUIRED_SCOPE = "https://www.googleapis.com/auth/documents"

    # 1. CRITICAL: Accept credentials object
    def __init__(self, credentials: Credentials):        
        self.credentials = credentials # Store locally
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # 2. CRITICAL: Pass credentials to the Tool
        self.DocTool = DocAPI(credentials=credentials)
        # 3. REMOVE the redundant scope check in the Agent
        # The Director only initializes this agent IF the scope is granted.
        self.available = True # If init succeeds, it's available.

    # 4. CRITICAL: Rename the analysis method
    def _analyze_query_to_json(self, user_query):
        """Ask ChatGPT to convert natural language into structured JSON commands."""
        system_prompt = (
            """"You are an AI assistant that helps users manage Google Docs files.
Always respond in **pure JSON format**, using double quotes and without any explanatory text.
Your job is to interpret the user's intent and respond in **pure JSON format only**, with double quotes for all keys and values. Do not include any explanations or extra text.

Supported actions and required keys:

1. "create": Create a new Google Doc.
   Required keys: "action", "file_name", "initial_content"
   - If the file_name is not mentioned, take it as New File by default. And the "initial_content" value is optional.

2. "retrieve": Retrieve a document by its name or ID.
   Required keys: "action", "file_name"
   - If the file_name is not mentioned, try to make it out from the context of the user query.

3. "add_text": Add text to an existing document.
   Required keys: "action", "file_name", "content"

4. "update": Update or replace specific text in a document.
   Required keys: "action", "file_name", "new_text"
   - If the file_name and/or new_text is not mentioned, try to make it out from the context of the user query.

5. "delete": Delete a document by name or ID.
   Required keys: "action", "file_name"
   - If the file_name is not mentioned, try to make it out from the context of the user query.

6. "summarize": Generate a summary of a document’s content.
   Required keys: "action", "file_name"
   - If the file_name is not mentioned, try to make it out from the context of the user query.

Examples of user queries and corresponding outputs:

- **"Create a document titled Project Plan and add the intro"**  
  → `{ "action": "create", "file_name": "Project Plan", "initial_content": "Add the intro" }`

- **"Summarize the document called Meeting Notes"**  
  → `{ "action": "summarize", "file_name": "Meeting Notes" }`

- **"Add this to the beginning of the file: Our mission is clear."**  
  → `{ "action": "add_text", "file_name": "Company Vision", "content": "Our mission is clear.", "location": "start" }`

If a query lacks enough detail, ask for clarification by responding with a JSON object:
`{ "error": "Missing [field_name]. Please provide more information." }'

Except if a file name is not found leave the file_name field empty.
"""
        )
        
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ]
        )
        content = response.choices[0].message.content
        if content.startswith("```json"):
            content = content.replace("```json", "").strip()
        if content.endswith("```"):
            content = content[:-3].strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"error": "⚠ Invalid response format."}

    # 5. Standardized handle_query method
    def handle_query(self, user_query):
        print("Docs Agent has received the query...")
        task = self._analyze_query_to_json(user_query) # Use renamed function
        print("Task:", task)
        response = self.handle_action(task)
        return response

    def get_doc_name(self, file):
        """Try to resolve an ambiguous or partial file name."""
        ten_docs = self.DocTool.get_recent_google_docs()
        doc_names = [doc["name"] for doc in ten_docs]
        if file in doc_names:
            return file
        doc_list_str = "\n".join([f"- {doc['name']}" for doc in ten_docs])
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Only reply with the name of the best-matching document from the list."},
                {"role": "user", "content": f"Here are some recent documents:\n{doc_list_str}"},
                {"role": "user", "content": f"The user is referring to: {file}"}
            ]
        )
        return response.choices[0].message.content

    def handle_action(self, response_data):
        """Core logic to execute the parsed action."""
        action = response_data.get("action")
        file_name = response_data.get("file_name", "Untitled Document")

        try:
            # CREATE
            if action == "create":
                content = response_data.get("initial_content", "")
                doc_id, link = self.DocTool.create_google_doc(title=file_name)
                if content:
                    self.DocTool.add_to_google_doc(doc_id, content, location="end")
                return f"Successfully created file {file_name}, with Doc_Id: {doc_id}!\nTo access click{link}"
                #return {"status": "success", "doc_id": doc_id, "message": f"📄 Created '{file_name}'", "link": link}

            # RETRIEVE
            elif action == "retrieve":
                doc_name = self.get_doc_name(file_name)
                doc_id = self.DocTool.resolve_file_name_to_id(doc_name)
                content = self.DocTool.get_google_doc_content(doc_id)
                return f"Successfully Retrieved {doc_name}! Content:-\n{content}"
                #return {"status": "success", "message": f"📄 Retrieved '{doc_name}'", "content": content}

            # ADD TEXT
            elif action == "add_text":
                doc_name = self.get_doc_name(file_name)
                doc_id = self.DocTool.resolve_file_name_to_id(doc_name)
                self.DocTool.add_to_google_doc(doc_id, response_data["content"])
                return f"Successfully added the content to {file_name}"
                #return {"status": "success", "message": f"✅ Added content to '{file_name}'"}

            # UPDATE
            elif action == "update":
                doc_id = self.DocTool.resolve_file_name_to_id(file_name)
                old_text = self.DocTool.get_google_doc_content(doc_id)
                new_text = response_data["new_text"]
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Merge new content with the old one without overwriting unnecessarily."},
                        {"role": "user", "content": f"Old:\n{old_text}"},
                        {"role": "user", "content": f"New:\n{new_text}"}
                    ]
                )
                updated_text = response.choices[0].message.content
                self.DocTool.edit_google_doc(doc_id, updated_text)
                return f"Successfully updated the content of {file_name}"
                #return {"status": "success", "message": f"✏️ Updated '{file_name}'"}

            # DELETE
            elif action == "delete":
                doc_name = self.get_doc_name(file_name)
                doc_id = self.DocTool.resolve_file_name_to_id(doc_name)
                self.DocTool.delete_google_doc(doc_id)
                return f"Successfully 🗑️ Deleted the file {file_name}"
                #return {"status": "success", "message": f"🗑️ Deleted '{file_name}'"}

            # SUMMARIZE
            elif action == "summarize":
                doc_id = self.DocTool.resolve_file_name_to_id(file_name)
                content = self.DocTool.get_google_doc_content(doc_id)
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Summarize the document. Include headings and sections if possible."},
                        {"role": "user", "content": content}
                    ]
                )
                return f"Here is the 📝 summary of {file_name}:-\n{response.choices[0].message.content}"
                return {"status": "success", "message": f"📝 Summary of '{file_name}'", "summary": response.choices[0].message.content}

            return f"Error: Unknown function {action}"
            #return {"status": "error", "message": f"Unknown action: {action}"}

        except Exception as e:
            return f"Error: Exception: {str(e)}"
            #return {"status": "error", "message": f"⚠️ Exception: {str(e)}"}
