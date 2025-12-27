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
        # Full ordered list of agents used for the most recent multi-task query,
        # so callers (e.g. main.py) aren't limited to just the last one.
        self.last_used_agents = []
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
                    linkedin_key = "linkedin"
                    if self.linkedin_tokens:
                        self.agents[linkedin_key] = AgentClass(self.linkedin_tokens)
                        logging.info(f"✅ Initialized LinkedInAgent.")
                        initialized = True

                # C. Final Logging
                if initialized:
                    pass
                else:
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

        prompt = """You are WingMan's Director — an intelligent coordinator and assistant. You analyze user input and break it down into actionable, sequential tasks.

🧠 ALWAYS return a valid JSON **array of dictionaries** in the following format:
[
    {
        "agent": "name_of_agent",
        "query": "user's query meant for that agent"
    }
]

Only include `agent` and `query` keys. DO NOT include actions, parameters, or any other fields. If there is only one task, still return it inside an array.

---

🟡 Use these agents:

"""
        AGENT_DESCRIPTIONS = {
            "email": """📧 **Email Agent** – for anything related to email:
{ "agent": "email", "query": "user's email request like 'send an email to Alex' or 'check unread emails'" }
Examples:
- "Send an email to Riya about the presentation"
- "Show me emails from Google"
""",
            "calendar": """📅 **Calendar Agent** – for scheduling, editing, or checking events:
{ "agent": "calendar", "query": "calendar-related request like 'schedule a call at 3PM', 'delete my event tomorrow'" }
Examples:
- "Add a meeting with Dev at 10AM"
- "Show my events for next week"
""",
            "doc": """📄 **Doc Agent** – for working with documents or notes:
{ "agent": "doc", "query": "document or note related request like 'summarize this', 'search notes on finance'" }
Examples:
- "Summarize the report I uploaded"
- "Find my notes on statistics"
""",
            "weather": """⛅ **Weather Agent** – for anything about the weather:
{ "agent": "weather", "query": "weather-related request with location if mentioned" }
Examples:
- "What's the weather like in Mumbai?"
- "Will it rain this weekend?"
""",
            "websearch": """🔍 **Web Search Agent** – for looking up anything online:
{ "agent": "web", "query": "search query or knowledge-based question" }
Examples:
- "What is generative AI?"
- "Latest news about cricket"
""",
            "research": """📚 **Research Agent** – for help with academic references, research material, or study topics:
{ "agent": "research", "query": "request for academic help like 'give me 10 papers on machine learning'" }
Examples:
- "Give me 10 research papers on blockchain"
""",
            "linkedin": """💼 **LinkedIn Agent** – for interacting with LinkedIn:
{ "agent": "linkedin", "query": "LinkedIn-related actions like 'send a connection request', 'search for jobs'" }
Examples:
- "Connect with the hiring manager at Google"
""",
            "spotify": """🎵 **Spotify Agent** – for playing or managing music on Spotify:
{ "agent": "spotify", "query": "Spotify music-related requests like 'play a song', 'add to playlist'" }
""",
            "youtube": """📺 **YouTube Agent** – for searching and interacting with YouTube:
{ "agent": "youtube", "query": "YouTube-related requests like 'search for a video', 'play something'" }
"""
        }

        for agent_name in self.agents.keys():
            if agent_name in AGENT_DESCRIPTIONS:
                prompt += f"{AGENT_DESCRIPTIONS[agent_name]}\n"

        prompt += """💬 **Self (General Conversation)** – for normal questions, jokes, or discussion:
{ "agent": "self", "query": "the user query as-is" }

---

🧠 Additional rules:
- Break complex requests into logical, sequential steps.
- Return only a single JSON array, nothing else.
- DO NOT add any explanation, metadata, or extra content.

✅ Examples of valid output:
[ { "agent": "calendar", "query": "schedule a team sync at 4 PM today" } ]

[
  { "agent": "web", "query": "Find the current stock price of Apple" },
  { "agent": "email", "query": "Email the Apple stock price to John" }
]
"""
        return prompt

    # -------------------- Utility Functions --------------------

    def get_agent_status(self):
        """Returns a dictionary of all potential agents and their current availability."""
        status = {}
        all_potential_agents = {
            "Email": "Email", "Calendar": "Calendar", "Doc": "Doc",
            "research": "Research", "weather": "Weather",
            "websearch": "Web Search", "linkedin": "LinkedIn",
            "spotify": "Spotify", "youtube": "YouTube"
        }
        for agent_name, display_name in all_potential_agents.items():
            status[display_name] = agent_name in self.agents
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
        """Ask GPT to break the query into an array of tasks."""
        messages = [{"role": "system", "content": self.system_prompt}]

        contextual_history = self.conversation_history[:-1]  # Exclude the current user query
        context_limit = 5
        for message in contextual_history[-context_limit:]:
            messages.append({"role": message["role"], "content": message["content"]})

        messages.append({"role": "user", "content": user_query})

        try:
            logging.debug(f"Sending messages for analysis: {messages}")
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0
            ).choices[0].message.content.strip()

            cleaned = self._clean_json_response(response)
            tasks = json.loads(cleaned)

            # Ensure it is a list, even if the model returns a single object
            if not isinstance(tasks, list):
                if isinstance(tasks, dict):
                    tasks = [tasks]
                else:
                    raise ValueError("Invalid structure returned: Expected array.")

            for task in tasks:
                if "agent" not in task or "query" not in task:
                    raise ValueError("Invalid task structure returned.")

            logging.info(f"Director routed query into {len(tasks)} task(s): {[t['agent'] for t in tasks]}")
            return tasks

        except Exception as e:
            logging.error(f"Error analyzing query: {e}")
            return [{"agent": "self", "query": user_query}]

    # -------------------- Agent Handling --------------------

    def call_agent(self, agent_name, query):
        """Routes the query to the correct agent."""
        agent = self.agents.get(agent_name)

        if not agent:
            logging.warning(f"No initialized agent found for '{agent_name}'.")
            if agent_name in self.AGENT_SCOPE_MAP:
                return f"Sorry, you haven't enabled the **{agent_name.capitalize()} Agent** yet. To use this service, please run `login.py` again and grant access to the required scope."
            else:
                return f"Sorry, I don't have an agent named '{agent_name}'."

        try:
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
        """Primary interface for main.py. Executes tasks sequentially, feeding each
        step's output forward as context for the next."""
        logging.info("Director received a new query.")
        self.add_to_history("user", user_query)

        tasks = self.analyze_query(user_query)
        execution_results = []
        self.last_used_agents = []

        for index, task in enumerate(tasks):
            agent_name = task.get("agent", "self")
            query = task.get("query", user_query)

            logging.info(f"Executing step {index + 1}/{len(tasks)} -> Agent: {agent_name}")

            if agent_name == "self":
                # Pass prior steps' results so the model knows what already happened.
                context_str = "\n".join(execution_results) if execution_results else "No previous steps."
                prompt = f"Context from previous steps:\n{context_str}\n\nUser request: {query}"

                messages = [{"role": "user", "content": prompt}]
                reply = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.7
                ).choices[0].message.content.strip()

                response = self.structure_response(reply)
            else:
                response = self.call_agent(agent_name, query)
                response = self.structure_response(response)

            self.last_used_agents.append(agent_name)
            execution_results.append(f"[{agent_name.capitalize()} Agent]: {response}")

        final_summary = "\n\n".join(execution_results)
        self.add_to_history("assistant", final_summary)

        return final_summary
