import random
import praw
import aiohttp
import asyncio
import time
from pyrogram import Client, types
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
from utils.usage import save_usage

# ---------------------------
# Coinflip Command Handler
# ---------------------------
async def coinflip_command(client: Client, message: types.Message):
    chat = message.chat
    await save_usage(chat, "coinflip")
    
    result = random.choice(["Heads", "Tails"])
    try:
        sender = message.from_user
        sender_name = sender.first_name if sender.first_name else "User"
        await message.reply(f"**{sender_name}** flipped a coin and got **{result}**!")
    except Exception as e:
        await message.reply(f"Coin flip result: **{result}**")

# ---------------------------
# Meme Command Handler (using PRAW)
# ---------------------------
async def meme_command(client: Client, message: types.Message):
    chat = message.chat
    await save_usage(chat, "meme")
    
    try:
        # Initialize Reddit API
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
            check_for_async=False
        )
        
        # Check if user specified "anime" parameter
        parts = message.text.split()
        if len(parts) > 1 and parts[1].lower() == "anime":
            subreddit_name = "animemes"
        else:
            subreddit_name = "memes"
        
        # Choose the appropriate subreddit
        subreddit = reddit.subreddit(subreddit_name)
        
        # Get hot submissions
        all_subs = []
        for submission in subreddit.hot(limit=50):
            # Filter out non-image posts and stickied posts
            if (submission.url.endswith(('.jpg', '.jpeg', '.png', '.gif')) and 
                not submission.stickied and not submission.is_self):
                all_subs.append(submission)
        
        if not all_subs:
            await message.reply("No suitable memes found. Try again later.")
            return
            
        # Select a random submission
        random_sub = random.choice(all_subs)
        name = random_sub.title
        url = random_sub.url
        
        # Send the meme
        await client.send_photo(chat.id, url, caption=name)
    except Exception as e:
        await message.reply(f"Error fetching meme: {str(e)}")

# ---------------------------
# Geekjoke Command Handler
# ---------------------------
async def geekjoke_command(client: Client, message: types.Message):
    chat = message.chat
    await save_usage(chat, "geekjoke")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://geek-jokes.sameerkumar.website/api?format=json") as response:
                if response.status == 200:
                    data = await response.json()
                    joke = data.get('joke', '')
                    if joke:
                        await message.reply(joke)
                    else:
                        await message.reply("Couldn't fetch a joke. Try again later.")
                else:
                    await message.reply(f"API Error: Status {response.status}")
    except Exception as e:
        await message.reply(f"Error fetching joke: {str(e)}")

# ---------------------------
# Dadjoke Command Handler
# ---------------------------
async def dadjoke_command(client: Client, message: types.Message):
    chat = message.chat
    await save_usage(chat, "dadjoke")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://icanhazdadjoke.com/slack") as response:
                if response.status == 200:
                    data = await response.json()
                    if 'attachments' in data and data['attachments']:
                        joke = data['attachments'][0]['text']
                        await message.reply(joke)
                    else:
                        await message.reply("Couldn't fetch a joke. Try again later.")
                else:
                    await message.reply(f"API Error: Status {response.status}")
    except Exception as e:
        await message.reply(f"Error fetching joke: {str(e)}")

# ---------------------------
# Dog Command Handler
# ---------------------------
async def dog_command(client: Client, message: types.Message):
    chat = message.chat
    await save_usage(chat, "dog")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://random.dog/woof.json") as response:
                if response.status == 200:
                    data = await response.json()
                    dog_url = data.get('url', '')
                    
                    if not dog_url:
                        await message.reply("Couldn't fetch a dog image. Try again later.")
                        return
                        
                    if dog_url.lower().endswith((".mp4", ".webm")):
                        await message.reply_video(dog_url, supports_streaming=True)
                    elif dog_url.lower().endswith((".jpg", ".jpeg", ".png")):
                        await message.reply_photo(dog_url)
                    elif dog_url.lower().endswith(".gif"):
                        await message.reply_animation(dog_url)
                    else:
                        await message.reply(f"Unsupported file type: {dog_url}")
                else:
                    await message.reply(f"API Error: Status {response.status}")
    except Exception as e:
        await message.reply(f"Error fetching dog image: {str(e)}")

# ---------------------------
# Cat Command Handler
# ---------------------------
async def cat_command(client: Client, message: types.Message):
    chat = message.chat
    await save_usage(chat, "cat")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.thecatapi.com/v1/images/search") as response:
                if response.status == 200:
                    data = await response.json()
                    cat_url = data[0].get('url', '')

                    if not cat_url:
                        await message.reply("Couldn't fetch a cat image. Try again later.")
                        return

                    if cat_url.lower().endswith((".mp4", ".webm")):
                        await message.reply_video(cat_url, supports_streaming=True)
                    elif cat_url.lower().endswith((".jpg", ".jpeg", ".png")):
                        await message.reply_photo(cat_url)
                    elif cat_url.lower().endswith(".gif"):
                        await message.reply_animation(cat_url)
                    else:
                        await message.reply(f"Unsupported file type: {cat_url}")
                else:
                    await message.reply(f"API Error: Status {response.status}")
    except Exception as e:
        await message.reply(f"Error fetching cat image: {str(e)}\nURL: {cat_url}")

# ---------------------------
# Affirmation Command Handler
# ---------------------------
async def affirmation_command(client: Client, message: types.Message):
    chat = message.chat
    await save_usage(chat, "affirmation")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://www.affirmations.dev/") as response:
                if response.status == 200:
                    data = await response.json()
                    affirmation_text = data.get('affirmation', '')
                    if affirmation_text:
                        await message.reply(affirmation_text)
                    else:
                        await message.reply("Couldn't fetch an affirmation. Try again later.")
                else:
                    await message.reply(f"API Error: Status {response.status}")
    except Exception as e:
        await message.reply(f"Error fetching affirmation: {str(e)}")

# ---------------------------
# Advice Command Handler
# ---------------------------
async def advice_command(client: Client, message: types.Message):
    chat = message.chat
    await save_usage(chat, "advice")
    
    try:
        headers = {"Accept": "application/json"}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get("https://api.adviceslip.com/advice") as response:
                data = await response.json(content_type="text/html")
                advice_text = data['slip']['advice']
                await message.reply(advice_text)
    except Exception as e:
        await message.reply(f"Error fetching advice: {str(e)}")

# ---------------------------
# Echo Command Handler
# ---------------------------
async def echo_command(client: Client, message: types.Message):
    chat = message.chat
    await save_usage(chat, "echo")
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or parts[1].strip() == "":
        await message.reply("Type something in the message")
    else:
        text = parts[1].strip()
        # Check if input exceeds max length
        if len(text) > 4000:
            await message.reply("Message is too long! Please limit to 300 characters.")
            return
        await message.reply(f"{text}\n\n||— Echoed from **{message.from_user.mention}**||")

# ---------------------------
# Reverse Command Handler
# ---------------------------
async def reverse_command(client: Client, message: types.Message):
    chat = message.chat
    await save_usage(chat, "reverse")
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or parts[1].strip() == "":
        await message.reply("Type some words.")
        return
    your_words = parts[1].strip()
    # Check if input exceeds max length
    if len(your_words) > 4000:
        await message.reply("Message is too long! Please limit to 300 characters.")
        return
    t_rev = your_words[::-1].replace("@", "@\u200B").replace("&", "&\u200B")
    await message.reply(f"🔁 {t_rev}")

# Dictionary to track user cooldowns for the choose command
choose_cooldowns = {}  # user_id -> timestamp

# ---------------------------
# Choose Command Handler
# ---------------------------
async def choose_command(client: Client, message: types.Message):
    chat = message.chat
    await save_usage(chat, "choose")
    
    # Get the text after the command
    parts = message.text.split(maxsplit=1)
    
    if len(parts) < 2 or not parts[1].strip():
        await message.reply("Please provide options to choose from, separated by commas. Example: /choose option1, option2, option3")
        return
    
    # Replace both Latin and Arabic commas with a common delimiter, then split
    input_text = parts[1].replace(',', '|').replace('،', '|')
    
    # Split the text by the common delimiter and strip whitespace
    options = [option.strip() for option in input_text.split('|')]
    
    # Filter out empty options
    options = [option for option in options if option]
    
    if not options:
        await message.reply("No valid options provided. Please use format: /choose option1, option2, option3")
        return
    
    if len(options) == 1:
        await message.reply("I need at least two options to make a choice!")
        return
    
    # Get user ID for rate limiting
    try:
        user_id = message.from_user.id
        current_time = time.time()
        
        # Check if user is on cooldown
        if user_id in choose_cooldowns:
            last_used = choose_cooldowns[user_id]
            time_passed = current_time - last_used
            if time_passed < 10:  # 10-second cooldown
                remaining = int(10 - time_passed)
                await message.reply(f"Please wait {remaining} seconds before using this command again.")
                return
    
        # Update the cooldown timestamp
        choose_cooldowns[user_id] = current_time
    except Exception as e:
        # If we can't get the sender ID for some reason, continue without rate limiting
        pass
    
    # Select a random option
    chosen_option = random.choice(options)
    
    try:
        # Send initial "thinking" message
        response = await message.reply("Hmmm...")
        
        # First edit after a short delay
        await asyncio.sleep(2)
        await response.edit_text("Lemme think for a bit...")

        # Second edit after a short delay
        await asyncio.sleep(4)
        await response.edit_text("Okay, I choose: ...")
        
        # Final edit with the answer
        await asyncio.sleep(1.5)
        await response.edit_text(f"Okay, I choose: **{chosen_option}**")
    except Exception as e:
        await message.reply(f"Error while choosing: {str(e)}")
