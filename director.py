import os
import json
import logging
from auth.token_manager import load_google_credentials
from auth.token_manager import load_linkedin_tokens
from google.oauth2.credentials import Credentials
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

# ---- Agent Imports ----
from agents.EmailAgent import EmailAgent
from agents.CalendarAgent import CalendarAgent
from agents.DocAgent import DocAgent
# from agents.ResearchAgent import ResearchAgent
from agents.WeatherAgent import WeatherAgent
from agents.WebsearchAgent import WebsearchAgent

from agents.LinkedinAgent import LinkedinAgent
## from agents.SpotifyAgent import SpotifyAgent
## from agents.YouTubeAgent import YouTubeAgent

# ---- Load environment ----
load_dotenv()

class Director:
    # Map agents to the required Google API scope from config/scopes.json
    AGENT_SCOPE_MAP = {
        "Email": ["https://mail.google.com/"],
        "Calendar": ["https://www.googleapis.com/auth/calendar"],
        "Doc": ["https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/drive"],
        "Linkedin": ["w_member_social", "profile", "email"], # Use the actual LinkedIn scope name
        # Add non-Google agents here too, e.g., "linkedin": "r_liteprofile"
    }

    def __init__(self, user_email):
        self.user_email = user_email
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.credentials: Credentials = None
        self.agents = {}
        self.conversation_history = []
        self.last_used_agent = None
        self.google_credentials = None
        self.linkedin_tokens = None

        try:
            # Try loading Google credentials (refreshes if needed)
            self.google_credentials = load_google_credentials(user_email)
            self.user_scopes = set(self.google_credentials.scopes)
        except ValueError:
            self.user_scopes = set()
            logging.info(f"Google services not available for {user_email}.")
            
        try:
            # Try loading LinkedIn tokens (returns dict if available)
            self.linkedin_tokens = load_linkedin_tokens(user_email)
        except ValueError:
            logging.info(f"LinkedIn service not available for {user_email}.")

        # 2. Dynamically initialize agents based on granted scopes/available tokens
        for agent_name, required_scope_list in self.AGENT_SCOPE_MAP.items():
            agent_key = agent_name.lower()
            agent_class_name = f"{agent_name}Agent"
            AgentClass = globals().get(agent_class_name)

            if AgentClass:
                initialized = False
                # A. Google Agents check scope and credentials
                if agent_key in ["email", "calendar", "doc"]:
                    if self.google_credentials and all(scope in self.user_scopes for scope in required_scope_list):
                        self.agents[agent_key] = AgentClass(self.google_credentials)
                        logging.info(f"✅ Initialized {agent_name}Agent (Google).")
                        initialized = True
                
                # B. LinkedIn Agent check token dict availability
                elif agent_key == "linkedin":
                    # FIX: Renamed variable to avoid conflict with agent_name in previous scope
                    linkedin_key = "linkedin" # Use "linkedin" for lookup in self.agents
                    if self.linkedin_tokens:
                        self.agents[linkedin_key] = AgentClass(self.linkedin_tokens) 
                        logging.info(f"✅ Initialized LinkedInAgent.")
                        initialized = True
                
                # C. Final Logging
                if initialized:
                    pass
                else:
                    # If AgentClass was found but not initialized (i.e., missing tokens/scopes)
                    logging.info(f"❌ Skipping {agent_name}Agent: Scope/Token not granted.")
            else:
                logging.warning(f"Agent class {agent_class_name} not found.")

            # 3. Initialize Public/Unscoped Agents (Unconditional)
        try:
            self.agents["weather"] = WeatherAgent(credentials=None)
            logging.info("✅ Initialized WeatherAgent (Public).")
        except ImportError:
            logging.warning("WeatherAgent module not found.")

        try:
            self.agents["websearch"] = WebsearchAgent(credentials=None)
            logging.info("✅ Initialized WebsearchAgent (Public).")
        except ImportError:
            logging.warning("WebsearchAgent module not found.")

        # 4. Generate the dynamic system prompt
        self.system_prompt = self._generate_dynamic_system_prompt()

    def _generate_dynamic_system_prompt(self):
        """Generates the system prompt using only the agents available to the user."""
        
        # Start with the static instructions
        prompt = """You are WingMan's Director — an intelligent coordinator and assistant. You analyze user input and route it to the correct specialized agent.

🧠 ALWAYS return a valid JSON **single dictionary** in the following format:
{
    "agent": "name_of_agent",
    "query": "user's query meant for that agent"
}

Only include `agent` and `query` keys. DO NOT include actions, parameters, or any other fields.

---

🟡 Use these agents:

"""
        # Dictionary mapping agent names to descriptions (needs to be defined centrally or loaded)
        AGENT_DESCRIPTIONS = {
            "email": """
📧 **Email Agent** – for anything related to email:
{
    "agent": "email",
    "query": "user's email request like 'send an email to Alex' or 'check unread emails'"
}

Examples:
- "Send an email to Riya about the presentation"
- "Show me emails from Google"
- "Reply to John's message with a thank you"
""",
            "calendar": """📅 **Calendar Agent** – for scheduling, editing, or checking events:
{
    "agent": "calendar",
    "query": "calendar-related request like 'schedule a call at 3PM', 'delete my event tomorrow'"
}

Examples:
- "Add a meeting with Dev at 10AM"
- "Show my events for next week"
""",
            "doc": """📄 **Doc Agent** – for working with documents or notes:
{
    "agent": "doc",
    "query": "document or note related request like 'summarize this', 'search notes on finance'"
}

Examples:
- "Summarize the report I uploaded"
- "Find my notes on statistics"
""",
            "weather": """⛅ **Weather Agent** – for anything about the weather:
{
    "agent": "weather",
    "query": "weather-related request with location if mentioned"
}

Examples:
- "What's the weather like in Mumbai?"
- "Will it rain this weekend?"
""",
            "websearch": """🔍 **Web Search Agent** – for looking up anything online:
{
    "agent": "web",
    "query": "search query or knowledge-based question"
}

Examples:
- "What is generative AI?"
- "Latest news about cricket"
- "How does a black hole form?"
""",
            "research": """📚 **Research Agent** – for help with academic references, research material, or study topics:
{
    "agent": "research",
    "query": "request for academic help like 'give me 10 papers on machine learning' or 'list resources on quantum computing'"
}

Examples:
- "Give me 10 research papers on blockchain"
- "List references on fuzzy logic and its applications"
- "Find textbooks on data structures with summaries and links"
""",
            "linkedin": """💼 **LinkedIn Agent** – for interacting with LinkedIn:
{
    "agent": "linkedin",
    "query": "LinkedIn-related actions like 'send a connection request', 'search for jobs', or 'message a recruiter', or 'schedule a post'"
}

Examples:
- "Connect with the hiring manager at Google"
- "Send a thank you message to Sarah on LinkedIn"
- "Search for internships in data science"
""",
            "spotify": """🎵 **Spotify Agent** – for playing or managing music on Spotify:
{
    "agent": "spotify",
    "query": "Spotify music-related requests like 'play a song', 'add to playlist', or 'recommend music'"
}

Examples:
- "Play some Lo-fi beats"
- "Add this song to my workout playlist"
- "Recommend me some chill jazz"
""",
            "youtube": """📺 **YouTube Agent** – for searching and interacting with YouTube:
{
    "agent": "youtube",
    "query": "YouTube-related requests like 'search for a video', 'play something', or 'get video links'"
}

Examples:
- "Search YouTube for tutorials on ReactJS"
- "Play lo-fi music from YouTube"
- "Find the latest video by MKBHD"
""",    # Add descriptions for all potential agents here...
        }

        # Dynamically append available agents and their descriptions
        for agent_name in self.agents.keys():
            if agent_name in AGENT_DESCRIPTIONS:
                # This needs to be expanded to include the JSON format and examples
                # For brevity, we'll just add the header. You will need to fill out the full block.
                prompt += f"{AGENT_DESCRIPTIONS[agent_name]}\n" 

        # Always include the fallback self agent
        prompt += """💬 **Self (General Conversation)** – for normal questions, jokes, or discussion:
{
    "agent": "self",
    "query": "the user query as-is"
}

Examples:
- "What's your favorite movie?"
- "Tell me a joke"

---

🧠 Additional rules:
- Assume that the user provides only one request per message.
- If the query contains multiple requests, return only the **first** or **most important** one.
- Return only a single JSON dictionary, nothing else.
- Be clear and concise in assigning agent responsibility.
- DO NOT add any explanation, metadata, or extra content.

✅ Examples of valid output:

{ "agent": "calendar", "query": "schedule a team sync at 4 PM today" }

{ "agent": "web", "query": "What is CRISPR gene editing?" }

{ "agent": "self", "query": "Do you have a favorite book?" }
"""
        return prompt

    # -------------------- Utility Functions --------------------

    def get_agent_status(self):
        """Returns a dictionary of all potential agents and their current availability."""
        status = {}
        user_scopes = set(self.credentials.scopes) if self.credentials else set()
        
        # We need a comprehensive list of all potential agents and their display names
        # Assuming AGENT_SCOPE_MAP contains ALL agents you ever plan to build
        all_potential_agents = {
            "Email": "Email",         # Must match AGENT_DESCRIPTIONS key
            "Calendar": "Calendar", 
            "Doc": "Doc",
            "research": "Research", 
            "weather": "Weather",
            "websearch": "Web Search", # Need to check the routing key for this one
            "linkedin": "LinkedIn", # Assuming you'll use "linkedin" as the key
            "spotify": "Spotify",
            "youtube": "YouTube",
            # Ensure this list is comprehensive!
        }

        for agent_name, display_name in all_potential_agents.items():
            is_active = agent_name in self.agents
            status[display_name] = is_active
            
        return status

    def add_to_history(self, role, content):
        """Save conversation turns."""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

    def _clean_json_response(self, text):
        """Cleans JSON returned by the model."""
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("```json").strip("```").strip()
        return text

    # -------------------- Query Analysis --------------------

    def analyze_query(self, user_query):
        """Ask GPT to decide which agent should handle this query, using conversation history for context."""
        
        # 1. Start with the System Prompt
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        # 2. Add Conversation History (Context)
        # We limit the history sent to the LLM to prevent prompt bloat and manage cost.
        # Let's take the last 5 relevant turns (excluding the current user query, which is added last).
        # We assume the history added via add_to_history is already in the OpenAI format: 
        # {"role": "user"/"assistant", "content": "..."}
        
        # --- Context Filtering Logic ---
        # The history passed from main.py is added to self.conversation_history before this call.
        # We skip the *last* item added, which is the current user query, as it's added separately below.
        
        contextual_history = self.conversation_history[:-1] # Exclude the current user query
        
        # Add a maximum of the last 5 turns of conversation for context (adjust limit as needed)
        context_limit = 5 
        
        for message in contextual_history[-context_limit:]:
            # Clean up the message structure for the LLM call:
            messages.append({
                "role": message["role"],
                "content": message["content"]
            })
            
        # 3. Add the current User Query
        messages.append({"role": "user", "content": user_query})
        
        # --- LLM Call ---
        try:
            logging.debug(f"Sending messages for analysis: {messages}") # Use logging.debug to see the full prompt structure
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0
            ).choices[0].message.content.strip()

            cleaned = self._clean_json_response(response)
            result = json.loads(cleaned)

            if "agent" not in result or "query" not in result:
                raise ValueError("Invalid structure returned.")

            logging.info(f"Director routed query to: {result['agent']}")
            return result

        except Exception as e:
            logging.error(f"Error analyzing query: {e}")
            return {"agent": "self", "query": user_query}

    # -------------------- Agent Handling --------------------

    def call_agent(self, agent_name, query):
        """Routes the query to the correct agent."""
        agent = self.agents.get(agent_name)
        
        # 1. Check if the agent is initialized (should be true due to dynamic prompt)
        if not agent:
            logging.warning(f"No initialized agent found for '{agent_name}'.")
            
            # 2. Check if the agent is defined in the full scope map (i.e., it exists but is disabled)
            if agent_name in self.AGENT_SCOPE_MAP:
                return f"Sorry, you haven't enabled the **{agent_name.capitalize()} Agent** yet. To use this service, please run `login.py` again and grant access to the required scope."
            else:
                return f"Sorry, I don’t have an agent named '{agent_name}'."
        
        try:
            # ... (Rest of the call_agent function remains the same)
            response = agent.handle_query(query)
            self.last_used_agent = agent_name
            return response
        except Exception as e:
            logging.error(f"Error in {agent_name} agent: {e}")
            return f"An error occurred while using the {agent_name.capitalize()} Agent: {str(e)}"

    def structure_response(self, response_text):
        """Cleans and structures agent or model responses."""
        if not response_text:
            return "I couldn't find any useful information."
        return response_text.strip().replace("\n\n", "\n")

    # -------------------- Director Main Handler --------------------

    def handle_query(self, user_query):
        """Primary interface for main.py"""
        logging.info("Director received a new query.")
        self.add_to_history("user", user_query)

        analysis = self.analyze_query(user_query)
        agent_name = analysis.get("agent", "self")
        query = analysis.get("query", user_query)

        if agent_name == "self":
            # Fallback GPT chat
            messages = [{"role": "user", "content": user_query}]
            reply = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.7
            ).choices[0].message.content.strip()
            self.add_to_history("assistant", reply)
            return self.structure_response(reply)

        # If specialized agent
        response = self.call_agent(agent_name, query)
        self.add_to_history("agent", response)
        return self.structure_response(response)
