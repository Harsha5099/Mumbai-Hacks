import os
import google.generativeai as genai
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. SETUP: Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.error("❌ GEMINI_API_KEY not found in environment variables.")

def run_gemini_chat(user_query, provided_context=None):
    """
    Direct Gemini integration for the chat interface.
    """
    if not GEMINI_API_KEY:
        return "System Error: Gemini API Key is missing. Please check .env file."

    try:
        # 🔴 FIXED: Switched from 'gemini-1.5-flash' to 'gemini-pro' (More stable)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        # Construct the prompt
        prompt = f"""
        You are an intelligent forensic assistant for the 'ForenSight' system.
        You are analyzing digital evidence for a case.
        
        USER QUESTION: {user_query}
        """
        
        # Inject context if available
        if provided_context:
            prompt += f"\n\nCONTEXT / CASE EVIDENCE:\n{provided_context[:30000]}"

        prompt += "\n\nANSWER (Be concise and professional):"

        logger.info(f"🤖 Sending query to Gemini: {user_query}")
        
        # Generate response
        response = model.generate_content(prompt)
        
        # Return clean text
        return response.text

    except Exception as e:
        logger.error(f"❌ Gemini Chat Failed: {e}")
        return f"I encountered an error processing that request: {str(e)}"