import os
import json
import logging
from openai import OpenAI
from duckduckgo_search import DDGS
from dotenv import load_dotenv

# Load env variables
load_dotenv()

logger = logging.getLogger(__name__)

# Initialize Client using the Env Variable
api_key = os.getenv("OPENAI_API_KEY")
client = None

if api_key:
    client = OpenAI(api_key=api_key)
else:
    logger.warning("⚠️ OPENAI_API_KEY not found in .env. Fact Check Agent will fail.")

def search_web(query: str) -> str:
    """
    Real web search tool using DuckDuckGo.
    Returns snippets of top search results.
    """
    print(f"🔎 Searching web for: {query}...")
    try:
        # DuckDuckGo search
        results = DDGS().text(query, max_results=3)
        if not results:
            return "No results found."
        # Format results for the model
        context = "\n".join([f"Source: {r['title']}\nSnippet: {r['body']}\nURL: {r['href']}" for r in results])
        return context
    except Exception as e:
        return f"Search failed: {str(e)}"

def fact_check_agent(claim: str):
    if not client:
        return "Error: OpenAI API Key missing."

    # 1. Define the tools the agent can use
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "Search the internet for evidence to verify a claim.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query optimized for fact-checking."
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]

    # 2. Initial messages
    messages = [
        {"role": "system", "content": (
            "You are a rigorous Fact Checking Agent. "
            "Your goal is to verify user claims using available tools. "
            "1. ALWAYS use the 'search_web' tool to gather evidence before answering. "
            "2. Be skeptical. Look for reputable sources. "
            "3. Classify the claim as: TRUE, FALSE, MISLEADING, or UNVERIFIED. "
            "4. Cite your sources clearly."
        )},
        {"role": "user", "content": f"Verify this claim: {claim}"}
    ]

    try:
        # 3. First API Call: Model decides if it needs to search
        response = client.chat.completions.create(
            model="gpt-4o",  # or gpt-3.5-turbo
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        # 4. Handle Tool Calls
        if tool_calls:
            # Append the model's tool request to history
            messages.append(response_message)

            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                if function_name == "search_web":
                    # Execute the function
                    function_response = search_web(function_args.get("query"))
                    
                    # Feed the evidence back to the model
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": "search_web",
                        "content": function_response,
                    })

            # 5. Second API Call: Model analyzes evidence and gives verdict
            final_response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages
            )
            return final_response.choices[0].message.content
        else:
            # Model didn't search (relying on internal knowledge)
            return response_message.content

    except Exception as e:
        return f"Fact Check Error: {str(e)}"

# --- SAFE EXECUTION BLOCK ---
# This ensures the code below ONLY runs if you run this file directly.
# It will NOT run when imported by app.py
if __name__ == "__main__":
    claim = "The Eiffel Tower was originally intended for Barcelona."
    verdict = fact_check_agent(claim)
    print("\n--- 📝 Fact Check Report ---")
    print(verdict)