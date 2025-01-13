import os
from openai import OpenAI
from dotenv import load_dotenv
from Tools.WebsearchTool import WebSearchTool
from typing import Dict, Any
from google.oauth2.credentials import Credentials

# Load environment variables
load_dotenv()

class WebsearchAgent:
    # Accept the credentials argument
    def __init__(self, credentials: Credentials = None): 
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.search_tool = WebSearchTool()
        self.system_prompt = """
        You are WingMan's Web Search Agent, designed to find and present information from the internet.
        Your responses should be:
        1. Accurate and based on search results
        2. Concise but informative
        3. Well-structured and easy to read
        4. Include sources when relevant
        5. Match the user's tone while maintaining professionalism
        
        When presenting information:
        - Start with the most relevant information
        - Use bullet points for multiple facts
        - Include brief source citations
        - Add emojis when appropriate for the tone
        - Highlight key information naturally
        """

    def handle_query(self, user_query):
        """Handle search requests and return formatted responses."""
        try:            
            # Perform search based on type
            result = self.search_tool.get_quick_answer(user_query)
            if result.get("answer"):
                return self._format_quick_answer(result, user_query)
            else:
                # If quick answer fails, try detailed search
                    result = self.search_tool.get_detailed_search(user_query)
                    return self._format_detailed_results(result, user_query)
                
        except Exception as e:
            return f"Oops! Something went wrong with the search: {str(e)}"

    def _format_quick_answer(self, result: Dict, query: str) -> str:
        """Format quick answer results using GPT."""
        if result.get("error"):
            return f"Sorry, I couldn't find a quick answer for that. {result['error']}"
            
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"""
            Format this search result into a natural, direct response:
            Query: {query}
            Answer: {result.get('answer')}
            Source: {result.get('source')}
            
            Remember to:
            1. Answer directly and clearly
            2. Include specific facts and numbers
            3. Add relevant emojis
            4. Keep it conversational
            """}
        ]
        
        completion = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7
        )
        
        return completion.choices[0].message.content

    def _format_detailed_results(self, result: Dict, query: str) -> str:
        """Format detailed search results using GPT."""
        if result.get("error"):
            return f"Sorry, I couldn't complete the detailed search. {result['error']}"
            
        # Prepare search results for formatting
        results_text = "\n".join([
            f"- {r.get('title', 'Untitled')}: {r.get('snippet', 'No snippet available')}"
            for r in result.get("results", [])[:3]
        ])
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"""
            Create a comprehensive but concise summary from these search results:
            Query: {query}
            Results:
            {results_text}
            """}
        ]
        
        completion = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7
        )
        
        return completion.choices[0].message.content