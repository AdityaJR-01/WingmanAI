# memory/chat_memory.py
import json
import os
import uuid
import logging
import threading
from datetime import datetime, timezone
from typing import List, Dict, Optional


class ChatMemory:
    """Persists a user's chat history to disk as JSON, organized into conversations
    keyed by conversation id (uuid4)."""

    def __init__(self, user_email=None, base_dir="memory",
                 max_conversations=None, max_messages_per_conversation=100):
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
        file_name = f"{user_email}_chat_history.json" if user_email else "chat_history.json"
        self.file_path = os.path.join(base_dir, file_name)

        self.max_conversations = max_conversations
        self.max_messages_per_conversation = max_messages_per_conversation

        self._lock = threading.Lock()
        self.conversations: Dict[str, Dict] = self._load_history()
        self.current_conversation_id: Optional[str] = None

    def _load_history(self) -> Dict[str, Dict]:
        if not os.path.exists(self.file_path):
            return {}
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Error loading chat history: {e}")
            return {}

    def _save_history(self) -> None:
        """Atomic write: temp file + os.replace, so a crash mid-write can't corrupt the JSON."""
        tmp_path = f"{self.file_path}.tmp"
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(self.conversations, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.file_path)
        except IOError as e:
            logging.error(f"Error saving chat history: {e}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def start_new_conversation(self, resume_if_empty: bool = True) -> str:
        """Start a new conversation. If the current one exists and has no messages
        yet, resume it instead of creating a dangling empty one."""
        with self._lock:
            if resume_if_empty and self.current_conversation_id:
                current = self.conversations.get(self.current_conversation_id)
                if current and not current["messages"]:
                    return self.current_conversation_id

            if self.max_conversations and len(self.conversations) >= self.max_conversations:
                oldest_id = min(self.conversations, key=lambda cid: self.conversations[cid]["timestamp"])
                del self.conversations[oldest_id]

            conv_id = str(uuid.uuid4())
            self.conversations[conv_id] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "messages": []
            }
            self.current_conversation_id = conv_id
            self._save_history()
            return conv_id

    def set_current_conversation(self, conv_id: str) -> bool:
        """Resume an existing conversation by id."""
        if conv_id in self.conversations:
            self.current_conversation_id = conv_id
            return True
        return False

    def add_message(self, role: str, content: str, metadata: Optional[dict] = None,
                     conv_id: Optional[str] = None) -> None:
        with self._lock:
            target_id = conv_id or self.current_conversation_id
            if not target_id or target_id not in self.conversations:
                target_id = self.start_new_conversation()

            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            if metadata:
                message["metadata"] = metadata

            messages = self.conversations[target_id]["messages"]
            messages.append(message)

            if self.max_messages_per_conversation and len(messages) > self.max_messages_per_conversation:
                del messages[:len(messages) - self.max_messages_per_conversation]

            self._save_history()

    def get_recent_messages(self, limit: int = 5, conv_id: Optional[str] = None) -> List[Dict]:
        target_id = conv_id or self.current_conversation_id
        conversation = self.conversations.get(target_id) if target_id else None
        if not conversation:
            return []
        return conversation["messages"][-limit:]

    def get_conversation(self, conv_id: Optional[str] = None) -> List[Dict]:
        """Full message list for a conversation (defaults to the current one)."""
        target_id = conv_id or self.current_conversation_id
        conversation = self.conversations.get(target_id) if target_id else None
        return conversation["messages"] if conversation else []

    def list_conversations(self) -> List[Dict]:
        return [
            {"id": cid, "timestamp": c["timestamp"], "message_count": len(c["messages"])}
            for cid, c in self.conversations.items()
        ]

    def clear_conversation(self, conv_id: Optional[str] = None) -> bool:
        with self._lock:
            target_id = conv_id or self.current_conversation_id
            if target_id in self.conversations:
                del self.conversations[target_id]
                if target_id == self.current_conversation_id:
                    self.current_conversation_id = None
                self._save_history()
                return True
            return False

    def clear_all(self) -> None:
        with self._lock:
            self.conversations = {}
            self.current_conversation_id = None
            self._save_history()
