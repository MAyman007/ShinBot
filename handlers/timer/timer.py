import asyncio
import datetime
import aiosqlite
from utils.helpers import create_pagination_keyboard, split_text_into_pages
from utils.usage import save_usage
from pyrogram import Client, types
from handlers.timer.timer_scheduler import get_chat_timer_table, schedule_timer, cancel_timer
from utils.decorators import check_admin_permissions

# Store pagination data temporarily
timer_pagination_data = {}

# ---------------------------
# Timer Command Handler
# ---------------------------
async def timer_command(client: Client, message: types.Message):
    chat = message.chat
    await save_usage(chat, "timer")
    
    # Improved command parsing that handles username suffix
    text = message.text
    command_parts = text.split(None, 1)
    command = command_parts[0].split('@')[0]  # This removes any bot username
    
    # Get the actual parameters after the command
    if len(command_parts) > 1:
        timer_args = command_parts[1]
    else:
        timer_args = ""
    
    # Parse time and reason
    if " " in timer_args:
        parts = timer_args.split(" ", 1)
        time_str = parts[0]
        reason = parts[1].strip()  # Strip whitespace from reason
    else:
        time_str = timer_args
        reason = ""
    
    # Check if reason exceeds max length
    if len(reason) > 300:
        await message.reply(
            "Reason is too long! Please limit to 300 characters."
        )
        return
    
    if not time_str:
        await message.reply(
            "Type time and time unit (s, m, h, d, mo, w, y) correctly\nFor example: `/timer 30m remind me of studying`"
        )
        return

    time_units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "mo": 2592000, "y": 31536000}
    
    # Extract the unit and value with improved support for decimal numbers
    unit_extracted = False
    for unit in ["mo", "s", "m", "h", "d", "w", "y"]:
        if time_str.endswith(unit):
            time_unit = unit
            input_number = time_str[:-len(unit)]
            unit_extracted = True
            break
    
    if not unit_extracted:
        await message.reply(
            "Invalid time unit. Use s (seconds), m (minutes), h (hours), d (days), w (weeks), mo (months), or y (years)"
        )
        return
    
    # Validate that input_number is a valid number
    try:
        # Allow float numbers for input
        float_value = float(input_number)
        time_unit_number = time_units.get(time_unit)
        if time_unit_number is None:
            raise ValueError("Invalid time unit")
        
        # Calculate seconds and round to nearest second
        sleep_duration = round(float_value * time_unit_number)
        
        # Check if timer is too long (30 years max)
        MAX_TIMER = 30 * 365 * 24 * 3600  # 30 years in seconds
        if sleep_duration > MAX_TIMER:
            await message.reply(
                "Timer too long! Maximum allowed is 30 years."
            )
            return
        
        # Check if timer is too short (1 second min)
        if sleep_duration < 1:
            await message.reply(
                "Timer too short! Minimum allowed is 1 second."
            )
            return
        
        end_time = datetime.datetime.now() + datetime.timedelta(seconds=sleep_duration)
        
        time_unit_words = {
            "s": "seconds", "m": "minutes", "h": "hours", 
            "d": "days", "w": "weeks", "mo": "months", "y": "years"
        }
        time_unit_word = time_unit_words.get(time_unit, time_unit)
        
        # Format nicely for display
        if float_value == 1.0:
            # Remove plural from unit word
            if time_unit_word.endswith("s"):
                time_unit_word = time_unit_word[:-1]
            time_display = f"1 {time_unit_word}"
        elif float_value == int(float_value):
            # Integer value
            time_display = f"{int(float_value)} {time_unit_word}"
        else:
            # Float value
            time_display = f"{float_value} {time_unit_word}"
        
        response_message = None
        if reason:
            response_message = await message.reply(
                f"Timer set to **{time_display}**\nReason: **{reason}**"
            )
        else:
            response_message = await message.reply(
                f"Timer set to **{time_display}**"
            )
        
        sender = message.from_user
        user_id = sender.id
        message_id = message.id  # Get the ID of the command message
        
        # Save the timer to chat-specific table in timers.db
        async with aiosqlite.connect("db/timers.db") as connection:
            table_name = await get_chat_timer_table(connection, chat.id)
            
            async with connection.cursor() as cursor:
                await cursor.execute(
                    f"INSERT INTO {table_name} (user_id, end_time, reason, message_id) VALUES (?, ?, ?, ?)",
                    (user_id, end_time.isoformat(), reason, message_id)
                )
                timer_id = cursor.lastrowid
                await connection.commit()
        
        # Schedule the timer with its ID
        delay = (end_time - datetime.datetime.now()).total_seconds()
        asyncio.create_task(schedule_timer(client, chat.id, timer_id, delay, reason, message_id))
    except ValueError:
        await message.reply(
            "Please enter a valid number for the timer."
        )
    except Exception as e:
        await message.reply(
            f"An error occurred: {str(e)}"
        )

# List timers command
async def list_timers_command(client: Client, message: types.Message):
    """Display active timers in the chat with detailed information."""
    chat = message.chat
    sender = message.from_user
    await save_usage(chat, "timers")

    # Get all timers for this chat
    now = datetime.datetime.now()
    async with aiosqlite.connect("db/timers.db") as connection:
        table_name = await get_chat_timer_table(connection, chat.id)
        
        async with connection.cursor() as cursor:
            await cursor.execute(
                f"SELECT id, end_time, reason, user_id, status FROM {table_name}"
            )
            timers = await cursor.fetchall()
    
    if not timers:
        await message.reply("No timers in this chat.")
        return
    
    # Filter active timers and calculate remaining time for sorting
    active_timer_data = []
    for db_id, end_time_str, reason, user_id, status in timers:
        if status == 'active':
            end_time = datetime.datetime.fromisoformat(end_time_str)
            time_remaining = (end_time - now).total_seconds()
            active_timer_data.append((db_id, end_time_str, reason, user_id, status, time_remaining))
    
    # Sort timers by time remaining (ascending)
    active_timer_data.sort(key=lambda x: x[5])
    
    # If no ID provided, list all timers that the user can remove
    lines = ["**🔔 Active Timers:**\n"]
    active_timers = False
    
    for db_id, end_time_str, reason, user_id, status, _ in active_timer_data:
        active_timers = True
        
        # Format time remaining for active timers only
        end_time = datetime.datetime.fromisoformat(end_time_str)
        diff = end_time - now
        
        # Format time display
        if diff.total_seconds() <= 0:
            time_left = "Ending soon..."
        else:
            d = diff.days
            h, remainder = divmod(diff.seconds, 3600)
            m, s = divmod(remainder, 60)
            
            time_parts = []
            if d > 0:
                time_parts.append(f"{d}d")
            if h > 0 or d > 0:
                time_parts.append(f"{h}h")
            if m > 0 or h > 0 or d > 0:
                time_parts.append(f"{m}m")
            time_parts.append(f"{s}s")
            
            time_left = " ".join(time_parts)

        # Try to get user info
        try:
            timer_user = await client.get_users(user_id)
            user_display = timer_user.mention
        except:
            user_display = f"User {user_id}"
        
        # Add to list
        lines.append(
            f"**ID #{db_id}** ⏰ **{time_left}** remaining\n"
            f"    👤 Set by: {user_display}\n"
            f"    📝 Reason: {reason or 'No reason provided'}\n"
        )

    if not active_timers:
        await message.reply("No active timers in this chat.")
        return

    # Split into pages
    pages = await split_text_into_pages(lines)
    
    if len(pages) == 1:
        # Single page, no pagination needed
        await message.reply(pages[0])
    else:
        # Multiple pages, use pagination
        callback_prefix = f"timers_{chat.id}"
        
        # Store pagination data
        timer_pagination_data[callback_prefix] = {
            'pages': pages,
            'chat_id': chat.id,
            'user_id': sender.id  # Store who requested it
        }
        
        # Send first page with navigation
        keyboard = await create_pagination_keyboard(1, len(pages), callback_prefix)
        await message.reply(pages[0], reply_markup=keyboard)

# Remove timer command
async def remove_timer_command(client: Client, message: types.Message):
    """
    Allows users to remove timers they've set or admins to remove any timer in the chat
    """
    chat = message.chat
    sender = message.from_user
    await save_usage(chat, "timerdel")
    
    # Check if user provided a timer ID
    command_parts = message.text.split()
    timer_id = None
    if len(command_parts) > 1:
        try:
            timer_id = int(command_parts[1])
        except ValueError:
            await message.reply("Invalid timer ID. Please provide a numeric ID from the timer list.")
            return
    
    # Use the robust admin checking function
    is_admin = await check_admin_permissions(client, chat.id, sender.id)
    
    # Get all timers for this chat
    now = datetime.datetime.now()
    async with aiosqlite.connect("db/timers.db") as connection:
        table_name = await get_chat_timer_table(connection, chat.id)
        
        async with connection.cursor() as cursor:
            await cursor.execute(
                f"SELECT id, end_time, reason, user_id, status FROM {table_name}"
            )
            timers = await cursor.fetchall()
    
    if not timers:
        await message.reply("No timers in this chat.")
        return
    
    # If timer_id was provided, try to remove that specific timer
    if timer_id is not None:
        found = False
        for db_id, end_time_str, reason, user_id, status in timers:
            if db_id == timer_id:
                found = True
                # Check if user has permission to remove this timer
                if sender.id == user_id or is_admin:
                    # Only allow canceling active timers
                    if status == 'active':
                        success = await cancel_timer(chat.id, db_id)
                        if success:
                            await message.reply(f"✅ Timer #{db_id} has been canceled.")
                        else:
                            await message.reply("❌ Failed to cancel timer. It may have already ended.")
                    else:
                        await message.reply(f"❌ Timer #{db_id} is already {status} and cannot be canceled.")
                else:
                    await message.reply("❌ You can only remove your own timers (or you need to be an admin).")
                break
                
        if not found:
            await message.reply(f"❌ Timer #{timer_id} not found.")
        return
    
    # If no ID provided, list all timers that the user can remove
    lines = ["**🔔 Timers You Can Remove:**\n"]
    active_timers = False
    
    # Filter timers and add remaining time for sorting
    removable_timers = []
    for db_id, end_time_str, reason, user_id, status in timers:
        # Determine if this user can remove this timer
        can_remove = (sender.id == user_id or is_admin) and status == 'active'
        
        if can_remove:
            end_time = datetime.datetime.fromisoformat(end_time_str)
            time_remaining = (end_time - now).total_seconds()
            removable_timers.append((db_id, end_time_str, reason, user_id, status, time_remaining))
    
    # Sort timers by time remaining (ascending)
    removable_timers.sort(key=lambda x: x[5])
    
    for db_id, end_time_str, reason, user_id, status, _ in removable_timers:
        active_timers = True
        
        # Format time remaining for active timers only
        end_time = datetime.datetime.fromisoformat(end_time_str)
        diff = end_time - now
        
        # Format time display
        if diff.total_seconds() <= 0:
            time_left = "Ending soon..."
        else:
            d = diff.days
            h, remainder = divmod(diff.seconds, 3600)
            m, s = divmod(remainder, 60)
            
            time_parts = []
            if d > 0:
                time_parts.append(f"{d}d")
            if h > 0 or d > 0:
                time_parts.append(f"{h}h")
            if m > 0 or h > 0 or d > 0:
                time_parts.append(f"{m}m")
            time_parts.append(f"{s}s")
            
            time_left = " ".join(time_parts)
        
        # Try to get user info
        try:
            timer_user = await client.get_users(user_id)
            user_display = timer_user.mention
        except:
            user_display = f"User {user_id}"
        
        # Add to list
        lines.append(
            f"**ID #{db_id}** ⏰ **{time_left}** remaining\n"
            f"    👤 Set by: {user_display}\n"
            f"    📝 Reason: {reason or 'No reason provided'}\n"
        )
    
    if not active_timers:
        await message.reply("No active timers that you can remove.")
        return
    
    lines.append("\nUse `/timerdel ID` to cancel a specific timer.")
    
    # Split into pages
    pages = await split_text_into_pages(lines)
    
    if len(pages) == 1:
        # Single page, no pagination needed
        await message.reply(pages[0])
    else:
        # Multiple pages, use pagination
        callback_prefix = f"timerdel_{chat.id}"
        
        # Store pagination data
        timer_pagination_data[callback_prefix] = {
            'pages': pages,
            'chat_id': chat.id,
            'user_id': sender.id  # Store who requested it
        }
        
        # Send first page with navigation
        keyboard = await create_pagination_keyboard(1, len(pages), callback_prefix)
        await message.reply(pages[0], reply_markup=keyboard)

# ---------------------------
# Timer pagination callback handler
# ---------------------------
async def handle_timer_pagination(client: Client, callback_query):
    """Handle pagination callbacks for timer commands."""
    try:
        data = callback_query.data
        
        # Extract callback prefix and page number
        if "_" not in data:
            return
        
        parts = data.rsplit("_", 1)
        callback_prefix = parts[0]
        try:
            page_num = int(parts[1])
        except ValueError:
            return
        
        # Check if we have pagination data for this prefix
        if callback_prefix not in timer_pagination_data:
            await callback_query.answer("Pagination data expired. Please run the command again.", show_alert=True)
            return
        
        data_info = timer_pagination_data[callback_prefix]
        
        # Check if the user who clicked is the one who requested it
        if callback_query.from_user.id != data_info['user_id']:
            await callback_query.answer("You didn't request this information.", show_alert=True)
            return
        
        pages = data_info['pages']
        
        # Validate page number
        if page_num < 1 or page_num > len(pages):
            await callback_query.answer("Invalid page number.", show_alert=True)
            return
        
        # Create new keyboard
        keyboard = await create_pagination_keyboard(page_num, len(pages), callback_prefix)
        
        # Edit message with new page
        await callback_query.edit_message_text(
            pages[page_num - 1],
            reply_markup=keyboard
        )
        
        await callback_query.answer()
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in timer pagination: {e}")
        await callback_query.answer("An error occurred while navigating.", show_alert=True)