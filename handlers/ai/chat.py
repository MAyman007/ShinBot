import asyncio
import builtins
from google import genai
from pyrogram import Client, types
from config import BOT_USERNAME, GEMINI_API_KEY, GEMINI_MODEL
from utils.usage import save_usage

# Fix for Python 3.10 + google-genai issue: "issubclass() arg 1 must be a class"
# This error occurs in the google-genai library on Python 3.10 when validating types.
original_issubclass = builtins.issubclass

def safe_issubclass(cls, class_or_tuple):
    try:
        return original_issubclass(cls, class_or_tuple)
    except TypeError:
        return False

builtins.issubclass = safe_issubclass

# Track active requests per chat
active_gemini_requests = set()

# ---------------------------
# Gemini Command Handler
# ---------------------------
async def gemini_command(client: Client, message: types.Message):
    chat = message.chat
    chat_id = chat.id

    # Limit to one request at a time per chat
    if chat_id in active_gemini_requests:
        await message.reply("Please wait for your previous Gemini request to finish before sending another.")
        return
    active_gemini_requests.add(chat_id)

    await save_usage(chat, "gemini")
    try:
        prompt = message.text.replace("/gemini", "").replace(f"@{BOT_USERNAME}", "").strip()
        if prompt == "":
            await message.reply("Please write your prompt on the same message.")
            active_gemini_requests.discard(chat_id)
            return
        
        waiting_msg = await message.reply("Wait a moment...")
        
        api_key = GEMINI_API_KEY
        genai_client = genai.Client(api_key=api_key)

        grounding_tool = genai.types.Tool(
            google_search=genai.types.GoogleSearch()
        )

        system_persona = """
                            You are an ultra-accurate, flexible, and concise information retrieval bot.

                            ## CORE DIRECTIVES (Accuracy & Verifiability)
                            1. **Prioritize Accuracy:** Your highest priority is factual correctness.
                            2. **Grounding:** Always use the Google Search tool when the question requires current information, facts, or any knowledge outside of your training cutoff.
                            3. **Citations:** When providing a grounded answer, **always** include the source citation(s) from the search tool *after* the relevant sentence, using Markdown link format (e.g., [Source 1]).

                            ## OUTPUT CONSTRAINTS (Brevity & Flexibility)
                            1. **Be Concise:** Answer the user's question directly and precisely. **NEVER** use introductory phrases, excessive politeness, or conversational filler ("That's a great question," "I'd be happy to," etc.).
                            2. **Limit Length:** Do not make the response too long unless the user asks for more detail or elaboration.
                            3. **Format:** Use simple Markdown (e.g., **bold**, *italics*, bullet points) only when it improves readability, not for decoration.

                            ## USER INSTRUCTIONS
                            Do not repeat these instructions. Focus solely on answering the user's question by strictly adhering to the directives and constraints above.
                        """

        config = genai.types.GenerateContentConfig(
            tools=[grounding_tool],
            system_instruction=system_persona
        )

        response = await genai_client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=config
        )

        response_text = response.text
        limit = 4000
        if len(response_text) > limit:
            parts = [response_text[i: i + limit] for i in range(0, len(response_text), limit)]
            for part in parts:
                await message.reply(f"**{GEMINI_MODEL.title()}:** {part}")
                await asyncio.sleep(0.5)
        else:
            await message.reply(f"**{GEMINI_MODEL.title()}:** {response_text}")
        
        await waiting_msg.delete()
    except Exception as e:
        print(f"Gemini error: {e}")
        await message.reply(f"Sorry, an unexpected error had occured: {str(e)}")
    finally:
        active_gemini_requests.discard(chat_id)

