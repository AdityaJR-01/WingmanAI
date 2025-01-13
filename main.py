# main.py

import logging
import sys
import os
from director import Director
from memory.chat_memory import ChatMemory
from auth.token_manager import load_user_credentials

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def print_help():
    help_text = """
WingMan - Available Commands:
----------------------------------------
Example Queries:
Weather:
  - "How's the weather?"
  - "What's the weather like in New York?"
  - "Is it raining in London?"

Email:
  - "Check my unread emails"
  - "Send an email to John about the meeting"
  - "Do I have any emails from Sarah?"
  - "Reply to email 1 accepting the invitation"

Web Search:
  - "What's the latest news about SpaceX?"
  - "Tell me about quantum computing"
  - "Who won the last World Cup?"
  - "Search for recent AI developments"

System Commands:
/help   - Show this help message
/bye    - Exit the program
/status - Check agents' status
/new    - Start new conversation
----------------------------------------
"""
    print(help_text)

def show_agent_status(director):
    status = director.get_agent_status()
    print("\nAgent Status:")
    for agent, active in status.items():
        emoji = "✅" if active else "❌"
        print(f"- {agent.capitalize()}: {emoji} {'Active' if active else 'Inactive'}")
    print()

def main():
    print("\nInitializing WingMan...")

    try:
        email = input("Enter your email: ").strip()
        
        # New check using the token manager to confirm user existence
        try:
            # We call this to check existence and potentially refresh token
            # The function raises ValueError if the user is not found
            load_user_credentials(email) 
        except ValueError:
            print(f"No credentials found for {email} in data/users.json. Please run login.py first.")
            return

        chat_memory = ChatMemory(user_email=email)
        chat_memory.start_new_conversation()
        director = Director(user_email=email)

        print("WingMan initialized successfully!")
        print("Type /help for example commands and queries")
        print("Type /bye to exit\n")

        while True:
            user_query = input("You: ").strip()
            if not user_query:
                continue

            command = user_query.lower()

            if command == "/bye":
                print("WingMan: Goodbye! 👋")
                break
            elif command == "/help":
                print_help()
                continue
            elif command == "/status":
                show_agent_status(director)
                continue
            elif command == "/new":
                chat_memory.start_new_conversation()
                print("\nWingMan: Started a new conversation! 🆕\n")
                continue

            # User message -> memory
            chat_memory.add_message("user", user_query)

            # Prepare context for the Director
            recent = chat_memory.get_recent_messages()
            director.conversation_history = [
                {
                    "role": msg["role"],
                    "content": msg["content"],
                    "timestamp": msg["timestamp"],
                    "metadata": msg.get("metadata", {})
                }
                for msg in recent
            ]

            # Get response from Director
            response = director.handle_query(user_query)

            # Assistant response -> memory
            metadata = {"agent": getattr(director, "last_used_agent", None)}
            chat_memory.add_message("assistant", response, metadata=metadata)

            print(f"\nWingMan: {response}\n")

    except Exception as e:
        print(f"\n❌ Error initializing WingMan: {str(e)}\n")
        print("Please check your API keys and internet connection.")
        print("Required keys:")
        print("- OPENAI_API_KEY")
        print("- GMAIL_CLIENT_ID")
        print("- GMAIL_CLIENT_SECRET")
        print("- GMAIL_REFRESH_TOKEN")
        print("- TAVILY_API_KEY")

if __name__ == "__main__":
    main()
