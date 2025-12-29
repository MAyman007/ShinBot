import time
import math
import re
import asyncio
import io
import qrcode
from pyrogram import Client, types
from tcp_latency import measure_latency
from utils.usage import save_usage
from config import FEEDBACK_CHAT_ID, BOT_NAME


# ---------------------------
# Start command
# ---------------------------
async def start_command(client: Client, message: types.Message):
    chat = message.chat
    await save_usage(chat, "start")
    sender = message.from_user
    await message.reply(
        f"Hello {sender.first_name}! My name is {BOT_NAME}.\n\n"
        "I'm an all-in-one multipurpose bot developed by @MAymanKH.\n"
        "- Use /help to discover all my commands and features.\n"
        "- Use /feedback to send suggestions to developers.\n"
        "- I'm fully open-source and available on [GitHub](https://github.com/MAymanKH/ShinBot)."
    )

# ---------------------------
# Ping Command Handler
# ---------------------------
async def ping_command(client: Client, message: types.Message):
    chat = message.chat
    await save_usage(chat, "ping")
    
    try:
        # Measure bot response time (message processing + API call)
        start_time = time.time()
        sent_message = await message.reply("🏓 Measuring...")
        bot_response_time = int((time.time() - start_time) * 1000)
        
        # Measure network latency to Telegram servers
        try:
            telegram_latency = measure_latency(host='149.154.167.50', port=443, timeout=5)  # Telegram server IP
            if not telegram_latency or len(telegram_latency) == 0:
                network_latency_ms = "Failed"
            else:
                network_latency_ms = f"{int(telegram_latency[0])}ms"
        except:
            network_latency_ms = "Failed"
        
        # Final result
        await sent_message.edit_text(
            f"🏓 **Pong!**\n\n"
            f"**Bot Response:** `{bot_response_time}ms`\n"
            f"**Network:** `{network_latency_ms}`"
        )
        
    except Exception as e:
        await message.reply(f"❌ Error measuring latency: {str(e)}")

# ---------------------------
# Calculator command
# ---------------------------
async def calc_command(client: Client, message: types.Message):
    chat = message.chat
    await save_usage(chat, "calc")
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Usage: /calc <expression>\nExample: /calc 2 + 2 * 3\nSupports: +, -, *, /, %, ^ (power), ! (factorial), sin, cos, tan, log, sqrt, pi, e")
        return
    
    expression = args[1].strip()
    
    # Limit expression length to prevent abuse
    if len(expression) > 200:
        await message.reply("Error: Expression too long (max 200 characters)")
        return
    
    try:
        # Check for factorial abuse before processing
        factorial_matches = re.findall(r'(\d+)!', expression)
        for match in factorial_matches:
            if int(match) > 20:
                await message.reply("Error: Factorial input too large (max 20!)")
                return
        
        # Replace ^ with ** for exponentiation
        expression = re.sub(r'\^', '**', expression)
        
        # Replace factorial notation (e.g., 5! becomes math.factorial(5))
        expression = re.sub(r'(\d+)!', r'math.factorial(\1)', expression)
        
        # Replace common math functions with math module equivalents
        expression = re.sub(r'\bsin\b', 'math.sin', expression)
        expression = re.sub(r'\bcos\b', 'math.cos', expression)
        expression = re.sub(r'\btan\b', 'math.tan', expression)
        expression = re.sub(r'\blog\b', 'math.log', expression)
        expression = re.sub(r'\bsqrt\b', 'math.sqrt', expression)
        expression = re.sub(r'\bpi\b', 'math.pi', expression)
        expression = re.sub(r'\be\b', 'math.e', expression)
        
        # Use eval with restricted globals for safety
        allowed_names = {
            "__builtins__": {},
            "math": math,
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "pow": pow,
        }
        
        # Use asyncio timeout for cross-platform compatibility
        async def evaluate_expression():
            return eval(expression, allowed_names, {})
        
        try:
            result = await asyncio.wait_for(evaluate_expression(), timeout=5.0)
        except asyncio.TimeoutError:
            await message.reply("Error: Calculation timeout (too complex)")
            return
        
        # Check if result is too large
        if isinstance(result, (int, float)) and abs(result) > 1e15:
            await message.reply("Error: Result too large to display")
            return
        
        # Format the result nicely
        if isinstance(result, float):
            if result.is_integer():
                result = int(result)
            else:
                result = round(result, 10)
        
        await message.reply(f"**Expression:** `{args[1]}`\n**Result:** `{result}`")
        
    except ZeroDivisionError:
        await message.reply("Error: Division by zero!")
    except (SyntaxError, NameError, TypeError, ValueError) as e:
        await message.reply(f"Error: Invalid expression. {str(e)}")
    except Exception as e:
        await message.reply(f"Error: {str(e)}")

# ---------------------------
# Feedback command
# ---------------------------
async def feedback_command(client: Client, message: types.Message):
    chat = message.chat
    await save_usage(chat, "feedback")
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Usage: /feedback <your message>\nExample: /feedback Great bot! Could you add more features?")
        return
    
    feedback_text = args[1].strip()
    
    # Limit feedback length
    if len(feedback_text) > 1000:
        await message.reply("Error: Feedback message too long (max 1000 characters)")
        return
    
    try:
        sender = message.from_user
        chat_info = f"Group: {chat.title}" if chat.type != "private" else "Private Chat"
        
        feedback_message = (
            f"📝 **New Feedback**\n\n"
            f"**From:** {sender.first_name}"
            f"{' ' + sender.last_name if sender.last_name else ''} "
            f"(@{sender.username if sender.username else 'No username'})\n"
            f"**User ID:** `{sender.id}`\n"
            f"**Chat:** {chat_info}\n"
            f"**Chat ID:** `{chat.id}`\n\n"
            f"**Message:**\n{feedback_text}"
        )
        
        await client.send_message(FEEDBACK_CHAT_ID, feedback_message)
        await message.reply("✅ Thank you for your feedback! Your message has been sent to the developers.")
        
    except Exception as e:
        await message.reply(f"❌ Error sending feedback: {str(e)}")

# ---------------------------
# QR Code command
# ---------------------------
async def qr_command(client: Client, message: types.Message):
    chat = message.chat
    await save_usage(chat, "qr")
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Usage: /qr <text>\nExample: /qr Hello World")
        return
    
    text = args[1].strip()
    
    # Limit text length
    if len(text) > 1000:
        await message.reply("Error: Text too long (max 1000 characters)")
        return
    
    try:
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(text)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to BytesIO object
        bio = io.BytesIO()
        img.save(bio)
        bio.seek(0)
        bio.name = "qrcode.png"
        
        await message.reply_photo(photo=bio, caption=f"**QR Code for:** `{text}`")
        
    except Exception as e:
        await message.reply(f"❌ Error generating QR code: {str(e)}")