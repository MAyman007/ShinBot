import re
import asyncio
import aiosqlite
import logging
from datetime import datetime, timedelta
from pyrogram import Client, types
from pyrogram.errors import UserAdminInvalid
from pyrogram.enums import ChatMembersFilter
from utils.usage import save_usage
from utils.decorators import admin_only, protect_admins
from utils.helpers import create_pagination_keyboard, extract_user_and_reason, split_text_into_pages

logger = logging.getLogger(__name__)

# Assume pagination_data is defined globally, similar to your warns implementation
pagination_data = {}

async def init_mute_db():
    """Initialize the mute schedules database."""
    async with aiosqlite.connect("db/mute_schedules.db") as connection:
        async with connection.cursor() as cursor:
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS mute_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    user_id INTEGER,
                    unmute_time TEXT,
                    reason TEXT,
                    muted_by INTEGER,
                    mute_message_id INTEGER,
                    status TEXT DEFAULT 'active'
                )
            """)
            # Add the new column if it doesn't exist (for existing databases)
            try:
                await cursor.execute("ALTER TABLE mute_schedules ADD COLUMN mute_message_id INTEGER")
            except:
                pass  # Column already exists
            await connection.commit()

async def record_mute(chat_id: int, user_id: int, unmute_time: datetime | None, reason: str, muted_by: int, mute_message_id: int = None):
    """Records a mute (temporary or permanent) in the database."""
    await init_mute_db()
    async with aiosqlite.connect("db/mute_schedules.db") as connection:
        async with connection.cursor() as cursor:
            # If unmute_time is a datetime object, convert to string. Otherwise, use None (for NULL).
            unmute_time_iso = unmute_time.isoformat() if unmute_time else None
            
            # First, cancel any previous active mute for the same user to avoid duplicates
            await cursor.execute(
                "UPDATE mute_schedules SET status = 'cancelled' WHERE chat_id = ? AND user_id = ? AND status = 'active'",
                (chat_id, user_id)
            )

            # Insert the new mute record
            await cursor.execute(
                "INSERT INTO mute_schedules (chat_id, user_id, unmute_time, reason, muted_by, mute_message_id) VALUES (?, ?, ?, ?, ?, ?)",
                (chat_id, user_id, unmute_time_iso, reason, muted_by, mute_message_id)
            )
            await connection.commit()
            logger.info(f"Recorded mute for user {user_id} in chat {chat_id}. Expiration: {unmute_time_iso or 'Permanent'}")

async def cancel_scheduled_unmute(chat_id: int, user_id: int):
    """Cancel a scheduled unmute for a user."""
    await init_mute_db()
    async with aiosqlite.connect("db/mute_schedules.db") as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                "UPDATE mute_schedules SET status = 'cancelled' WHERE chat_id = ? AND user_id = ? AND status = 'active'",
                (chat_id, user_id)
            )
            await connection.commit()
            logger.info(f"Cancelled scheduled unmute for user {user_id} in chat {chat_id}")

async def check_pending_unmutes(client: Client):
    """Check for and execute pending unmutes."""
    await init_mute_db()
    try:
        async with aiosqlite.connect("db/mute_schedules.db") as connection:
            async with connection.cursor() as cursor:
                now = datetime.now().isoformat()
                await cursor.execute(
                    "SELECT id, chat_id, user_id, reason, mute_message_id FROM mute_schedules WHERE unmute_time <= ? AND status = 'active'",
                    (now,)
                )
                pending_unmutes = await cursor.fetchall()
                
                for unmute_id, chat_id, user_id, reason, mute_message_id in pending_unmutes:
                    try:
                        # Unmute the user
                        await client.unban_chat_member(chat_id, user_id)
                        
                        # Mark as completed
                        await cursor.execute(
                            "UPDATE mute_schedules SET status = 'completed' WHERE id = ?",
                            (unmute_id,)
                        )
                        
                        # Try to send notification with user mention and reply to mute message
                        try:
                            user = await client.get_users(user_id)
                            unmute_message = f"🔊 **Automatic Unmute**\n{user.mention} has been automatically unmuted."
                            
                            if mute_message_id:
                                await client.send_message(
                                    chat_id,
                                    unmute_message,
                                    reply_to_message_id=mute_message_id
                                )
                            else:
                                await client.send_message(chat_id, unmute_message)
                        except:
                            pass  # Don't fail if we can't send message
                        
                        logger.info(f"Auto-unmuted user {user_id} in chat {chat_id}")
                        
                    except Exception as e:
                        logger.error(f"Error auto-unmuting user {user_id} in chat {chat_id}: {e}")
                        # Mark as failed
                        await cursor.execute(
                            "UPDATE mute_schedules SET status = 'failed' WHERE id = ?",
                            (unmute_id,)
                        )
                
                await connection.commit()
                
    except Exception as e:
        logger.error(f"Error checking pending unmutes: {e}")

# Background task to check for pending unmutes
async def unmute_checker_task(client: Client):
    """Background task that runs every 10 seconds to check for pending unmutes."""
    while True:
        try:
            await check_pending_unmutes(client)
            await asyncio.sleep(10)  # Check every 10 seconds for better accuracy
        except Exception as e:
            logger.error(f"Error in unmute checker task: {e}")
            await asyncio.sleep(10)

async def is_user_muted(client: Client, chat_id: int, user_id: int) -> bool:
    """Check if a user is currently muted."""
    try:
        member = await client.get_chat_member(chat_id, user_id)
        # Check if user has restricted permissions (muted)
        if member.restricted_by and member.permissions:
            # If all main permissions are False, user is muted
            perms = member.permissions
            return not (perms.can_send_messages or 
                       perms.can_send_media_messages or 
                       perms.can_add_web_page_previews)
        return False
    except:
        return False

# ---------------------------
# Mute command
# ---------------------------
@admin_only
@protect_admins
async def mute_command(client: Client, message: types.Message):
    chat = message.chat
    await save_usage(chat, "mute")
    
    # Get target user and initial reason using helper function
    user, initial_reason = await extract_user_and_reason(client, message)
    
    if not user:
        await message.reply("Please specify a user to mute.\n**Usage:** `/mute @username [time] [reason]`")
        return
    
    # Check if user is already muted
    if await is_user_muted(client, chat.id, user.id):
        await message.reply(f"❌ User {user.mention} is already muted.")
        return
    
    # Parse remaining arguments for time and reason from the initial reason
    duration = None
    reason_parts = []
    
    if initial_reason:
        args = initial_reason.split()
        for arg in args:
            time_match = re.match(r'^(\d+)([hmds])$', arg.lower())
            if time_match and duration is None:  # Only take first time found
                amount = int(time_match.group(1))
                unit = time_match.group(2)
                if unit == 'd':
                    duration = amount * 60 * 60 * 24
                elif unit == 'h':
                    duration = amount * 60 * 60
                elif unit == 'm':
                    duration = amount * 60
                elif unit == 's':
                    duration = amount
            else:
                reason_parts.append(arg)
    
    reason = ' '.join(reason_parts) if reason_parts else "No reason provided"
    
    # Calculate until when the user will be muted (None for infinite)
    mute_until = None if duration is None else datetime.now() + timedelta(seconds=duration)
    
    try:
        # Apply mute restriction
        if mute_until:
            # Temporary mute with expiration
            await client.restrict_chat_member(
                chat.id,
                user.id,
                types.ChatPermissions(), # No permissions
                until_date=mute_until
            )
        else:
            # Permanent mute (no until_date parameter)
            await client.restrict_chat_member(
                chat.id,
                user.id,
                types.ChatPermissions() # No permissions
            )
        
        await record_mute(chat.id, user.id, mute_until, reason, message.from_user.id, message.id)
        
        # Send confirmation message
        if duration is None:
            mute_time_str = "Indefinitely"
        else:
            if duration >= 86400:  # 1 day in seconds
                days = duration // 86400
                hours = (duration % 86400) // 3600
                minutes = (duration % 3600) // 60
                seconds = duration % 60
                time_parts = []
                if days > 0:
                    time_parts.append(f"{days}d")
                if hours > 0:
                    time_parts.append(f"{hours}h")
                if minutes > 0:
                    time_parts.append(f"{minutes}m")
                if seconds > 0:
                    time_parts.append(f"{seconds}s")
                mute_time_str = " ".join(time_parts)
            elif duration >= 3600:  # 1 hour in seconds
                hours = duration // 3600
                minutes = (duration % 3600) // 60
                seconds = duration % 60
                time_parts = []
                if hours > 0:
                    time_parts.append(f"{hours}h")
                if minutes > 0:
                    time_parts.append(f"{minutes}m")
                if seconds > 0:
                    time_parts.append(f"{seconds}s")
                mute_time_str = " ".join(time_parts)
            elif duration >= 60:  # 1 minute in seconds
                minutes = duration // 60
                seconds = duration % 60
                time_parts = []
                if minutes > 0:
                    time_parts.append(f"{minutes}m")
                if seconds > 0:
                    time_parts.append(f"{seconds}s")
                mute_time_str = " ".join(time_parts)
            else:
                mute_time_str = f"{duration}s"
        
        await message.reply_text(
            f"🔇 **User Muted**\n"
            f"**User:** {user.mention}\n"
            f"**Duration:** {mute_time_str}\n"
            f"**Reason:** {reason}\n"
            f"**Admin:** {message.from_user.mention}"
            + (f"\n**Auto-unmute:** {mute_until.strftime('%Y-%m-%d %H:%M:%S')}" if mute_until else "")
        )
    except UserAdminInvalid:
        await message.reply("❌ I need admin privileges to mute users.")
    except Exception as e:
        logger.error(f"Error in mute command: {e}")
        await message.reply(f"❌ An error occurred: {str(e)}")

# ---------------------------
# Unmute command
# ---------------------------
@admin_only
async def unmute_command(client: Client, message: types.Message):
    chat = message.chat
    await save_usage(chat, "unmute")
    
    # Get target user and reason using helper function
    user, reason = await extract_user_and_reason(client, message)
    
    if not user:
        await message.reply("Please mention a user with @ or reply to their message.\n**Usage:** `/unmute @username [reason]`")
        return
    
    reason = reason if reason else "No reason provided"
    
    try:
        # Cancel any scheduled unmute
        await cancel_scheduled_unmute(chat.id, user.id)
        
        # Remove mute restrictions by setting default permissions
        await client.unban_chat_member(
            chat.id,
            user.id
        )
        
        # Send confirmation message
        await message.reply_text(
            f"🔊 **User Unmuted**\n"
            f"**User:** {user.mention}\n"
            f"**Admin:** {message.from_user.mention}"
        )
    except UserAdminInvalid:
        await message.reply("❌ I need admin privileges to unmute users.")
    except Exception as e:
        logger.error(f"Error in unmute command: {e}")
        await message.reply(f"❌ An error occurred: {str(e)}")

# ---------------------------
# List all muted members command
# ---------------------------
@admin_only
async def mutes_command(client: Client, message: types.Message):
    """Lists all currently muted members in the chat."""
    chat = message.chat
    sender = message.from_user
    
    logger.info(f"Mutes command called by user {sender.id} in chat {chat.id}")
    await save_usage(chat, "mutes")
    
    try:
        # Step 1: Fetch mute reasons and admin info from your database first
        db_mutes = {}
        await init_mute_db()
        async with aiosqlite.connect("db/mute_schedules.db") as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "SELECT user_id, reason, muted_by FROM mute_schedules WHERE chat_id = ? AND status = 'active'",
                    (chat.id,)
                )
                # Store in a dictionary for quick lookup: {user_id: (reason, muted_by_id)}
                rows = await cursor.fetchall()
                db_mutes = {row[0]: (row[1], row[2]) for row in rows}

        # Step 2: Fetch all restricted (muted) members from Telegram's API
        muted_members = []
        async for member in client.get_chat_members(chat.id, filter=ChatMembersFilter.RESTRICTED):
            # Ensure the user is actually muted (not just restricted from other things)
            if not member.permissions.can_send_messages:
                muted_members.append(member)

        if not muted_members:
            await message.reply("✅ No members are currently muted in this chat.")
            return
            
        # Step 3: Build the response message
        lines = [f"🔇 **All Muted Members in {chat.title or 'this chat'}** ({len(muted_members)} total)\n"]
        
        for member in muted_members:
            user = member.user
            
            # Format the expiration date or show as permanent
            if member.until_date:
                remaining = member.until_date - datetime.now()
                if remaining.total_seconds() > 0:
                    days = remaining.days
                    hours = remaining.seconds // 3600
                    minutes = (remaining.seconds % 3600) // 60
                    
                    parts = []
                    if days > 0: parts.append(f"{days}d")
                    if hours > 0: parts.append(f"{hours}h")
                    if minutes > 0: parts.append(f"{minutes}m")
                    
                    duration_str = f"{' '.join(parts) or '<1m'} remaining"
                else:
                    duration_str = "Expiring..."
            else:
                duration_str = "Permanent"
            
            # Get reason and muting admin from our DB cache if available
            reason_str = "N/A (Manual mute or by another bot)"
            admin_name_str = "N/A"
            if user.id in db_mutes:
                reason, admin_id = db_mutes[user.id]
                reason_str = reason if reason else "No reason provided"
                try:
                    admin_user = await client.get_users(admin_id)
                    admin_name_str = admin_user.mention
                except Exception:
                    admin_name_str = f"Admin ID: {admin_id}"

            lines.append(f"👤 {user.mention} (`{user.id}`)")
            lines.append(f"  - **Duration:** {duration_str}")
            lines.append(f"  - **Reason:** {reason_str}")
            lines.append(f"  - **Muted by:** {admin_name_str}\n") # Add a newline for better spacing

        # Step 4: Handle pagination
        pages = await split_text_into_pages(lines)
        
        if len(pages) == 1:
            await message.reply(pages[0], disable_web_page_preview=True)
        else:
            callback_prefix = f"mutes_{chat.id}"
            
            pagination_data[callback_prefix] = {
                'pages': pages,
                'chat_title': chat.title or 'this chat',
                'user_id': sender.id # Store who requested it
            }
            
            keyboard = await create_pagination_keyboard(1, len(pages), callback_prefix)
            await message.reply(pages[0], reply_markup=keyboard, disable_web_page_preview=True)
            
    except Exception as e:
        logger.error(f"Error in mutes_command for chat {chat.id}: {e}")
        await message.reply(f"❌ An error occurred while fetching the mute list: {str(e)}")


# ---------------------------
# Pagination callback handler for mutes
# ---------------------------
async def handle_mutes_pagination(client: Client, callback_query: types.CallbackQuery):
    """Handle pagination callbacks for the mutes command."""
    try:
        data = callback_query.data
        parts = data.rsplit("_", 1)
        callback_prefix = parts[0]
        
        # Check if the data is in our cache
        if callback_prefix not in pagination_data:
            await callback_query.answer("Pagination data expired. Please run the command again.", show_alert=True)
            return

        data_info = pagination_data[callback_prefix]
        
        # Security check: only the original command user can navigate
        if callback_query.from_user.id != data_info['user_id']:
            await callback_query.answer("You didn't request this list.", show_alert=True)
            return
            
        page_num = int(parts[1])
        pages = data_info['pages']
        
        if not 1 <= page_num <= len(pages):
            await callback_query.answer("Invalid page.", show_alert=True)
            return
            
        keyboard = await create_pagination_keyboard(page_num, len(pages), callback_prefix)
        
        await callback_query.edit_message_text(
            pages[page_num - 1],
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        await callback_query.answer()

    except Exception as e:
        logger.error(f"Error in mutes pagination: {e}")
        await callback_query.answer("An error occurred during navigation.", show_alert=True)

def start_unmute_checker(client: Client):
    """Start the background unmute checker task."""
    asyncio.create_task(unmute_checker_task(client))