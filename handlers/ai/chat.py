import asyncio
from google import genai
from pyrogram import Client, types
from config import BOT_USERNAME, GEMINI_API_KEY, GEMINI_MODEL
from utils.usage import save_usage

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
        response = await genai_client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
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

