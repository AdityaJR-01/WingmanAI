# memory/chat_memory.py
import json
import os
import logging
import uuid
from datetime import datetime

class ChatMemory:
    def __init__(self, user_email=None, base_dir="memory", max_messages_per_conv=100):
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
        
        # Maintains the email-specific file routing
        file_name = f"{user_email}_chat_history.json" if user_email else "chat_history.json"
        self.file_path = os.path.join(base_dir, file_name)
        
        self.max_messages = max_messages_per_conv
        self.history = self._load_history()
        self.current_conversation_id = None

    def _load_history(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Migration: If the old file used a list for conversations, convert it to a UUID dictionary
                    if "conversations" in data and isinstance(data["conversations"], list):
                        new_convs = {}
                        for conv in data["conversations"]:
                            # Keep old integer IDs as strings for legacy chats, use UUID for new ones
                            conv_id = str(conv.get("id", uuid.uuid4()))
                            new_convs[conv_id] = {
                                "timestamp": conv.get("timestamp", datetime.now().isoformat()),
                                "messages": conv.get("messages", [])
                            }
                        data["conversations"] = new_convs
                        
                    return data
            except Exception as e:
                logging.error(f"Error loading chat history: {e}")
        
        return {"conversations": {}}

    def _save_history(self):
        """Atomic write to prevent corruption if the script crashes mid-save."""
        temp_path = f"{self.file_path}.tmp"
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
            # os.replace safely swaps the temp file over the old file
            os.replace(temp_path, self.file_path)
        except Exception as e:
            logging.error(f"Error saving chat history: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def start_new_conversation(self):
        """Replaces fragile integer length indexing with robust UUIDs."""
        new_id = str(uuid.uuid4())
        
        if "conversations" not in self.history:
            self.history["conversations"] = {}
            
        self.history["conversations"][new_id] = {
            "timestamp": datetime.now().isoformat(),
            "messages": []
        }
        self.current_conversation_id = new_id
        self._save_history()
        return new_id

    def add_message(self, role, content, metadata=None):
        if not self.current_conversation_id or self.current_conversation_id not in self.history["conversations"]:
            self.start_new_conversation()
            
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        if metadata:
            message["metadata"] = metadata
            
        conv = self.history["conversations"][self.current_conversation_id]
        conv["messages"].append(message)
        
        # Auto-prune to protect LLM context windows and save memory
        if len(conv["messages"]) > self.max_messages:
            conv["messages"] = conv["messages"][-self.max_messages:]
            
        self._save_history()

    def get_recent_messages(self, limit=5):
        if not self.current_conversation_id or self.current_conversation_id not in self.history["conversations"]:
            return []
        return self.history["conversations"][self.current_conversation_id]["messages"][-limit:]
