import datetime
import aiosqlite
import logging
from pyrogram import Client, types
from utils.usage import save_usage
from utils.decorators import admin_only
from utils.helpers import create_pagination_keyboard, extract_user_and_reason, split_text_into_pages

logger = logging.getLogger(__name__)

# Store pagination data temporarily
pagination_data = {}

async def init_warns_db(chat_id):
    """Initialize the warns database for a specific chat."""
    table_name = f"warns_chat_{abs(chat_id)}"
    async with aiosqlite.connect("db/warns.db") as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    warned_by INTEGER,
                    reason TEXT,
                    warn_date TEXT,
                    status TEXT DEFAULT 'active'
                )
            """)
            await connection.commit()
            logger.info(f"Warns database initialized for chat {chat_id}")

# ---------------------------
# Warn command
# ---------------------------
@admin_only
async def warn_command(client: Client, message: types.Message):
    chat = message.chat
    sender = message.from_user
    
    logger.info(f"Warn command called by user {sender.id} ({sender.first_name}) in chat {chat.id}")
    logger.info(f"Message text: {message.text}")
    
    await save_usage(chat, "warn")
    
    # Get target user using helper function
    user, reason = await extract_user_and_reason(client, message)
    
    if not user:
        await message.reply(
            "Please reply to a message or mention a user to warn them.\n"
            "Usage: /warn @username reason or /warn user_id reason or reply to a message with /warn reason"
        )
        return
    
    logger.info(f"Target user identified: {user.id} ({user.first_name})")
    
    # Use reason from helper function or default
    if not reason or reason.strip() == "":
        reason = "No reason provided"
    
    # Check if reason exceeds max length
    if len(reason) > 500:
        await message.reply("Reason is too long! Please limit to 500 characters.")
        return
    
    try:
        # Initialize database
        await init_warns_db(chat.id)
        table_name = f"warns_chat_{abs(chat.id)}"
        
        # Save warn to database
        warn_date = datetime.datetime.now().isoformat()
        async with aiosqlite.connect("db/warns.db") as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    f"INSERT INTO {table_name} (user_id, warned_by, reason, warn_date) VALUES (?, ?, ?, ?)",
                    (user.id, sender.id, reason, warn_date)
                )
                warn_id = cursor.lastrowid
                await connection.commit()
                logger.info(f"Warning issued: ID {warn_id} to user {user.id} in chat {chat.id}")
        
        # Get total warns for this user in this chat
        async with aiosqlite.connect("db/warns.db") as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    f"SELECT COUNT(*) FROM {table_name} WHERE user_id = ? AND status = 'active'",
                    (user.id,)
                )
                total_warns = await cursor.fetchone()
                total_warns = total_warns[0] if total_warns else 0
        
        # Send confirmation message
        await message.reply(
            f"⚠️ Warning issued to {user.mention}\n\n"
            f"**Warning ID:** #{warn_id}\n"
            f"**Reason:** {reason}\n"
            f"**Total warnings:** {total_warns}\n"
            f"**Issued by:** {sender.mention}"
        )
        
    except Exception as e:
        await message.reply(f"An error occurred while issuing the warning: {str(e)}")
        logger.error(f"Error in warn command: {e}")

# ---------------------------
# Warning delete command
# ---------------------------
@admin_only
async def warndel_command(client: Client, message: types.Message):
    chat = message.chat
    sender = message.from_user
    
    logger.info(f"Warndel command called by user {sender.id} in chat {chat.id}")
    
    await save_usage(chat, "warndel")
    
    # Extract warning ID from command
    args = message.text.split()
    if len(args) < 2:
        await message.reply("Please provide a warning ID. Usage: `/warndel [ID]`\nSee warnings IDs from `/warns` or `/warns @user`")
        return
    
    try:
        warn_id = int(args[1])
    except ValueError:
        await message.reply("Invalid warning ID. Please provide a numeric ID.")
        return
    
    try:
        await init_warns_db(chat.id)
        table_name = f"warns_chat_{abs(chat.id)}"
        
        # Check if warning exists
        async with aiosqlite.connect("db/warns.db") as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    f"SELECT user_id, reason, status FROM {table_name} WHERE id = ?",
                    (warn_id,)
                )
                warning = await cursor.fetchone()
                
                if not warning:
                    await message.reply(f"Warning #{warn_id} not found.")
                    return
                
                if warning[2] == 'deleted':
                    await message.reply(f"Warning #{warn_id} has already been deleted.")
                    return
                
                # Mark warning as deleted
                await cursor.execute(
                    f"UPDATE {table_name} SET status = 'deleted' WHERE id = ?",
                    (warn_id,)
                )
                await connection.commit()
                logger.info(f"Warning deleted: ID {warn_id} by admin {sender.id}")
        
        # Get user info
        try:
            warned_user = await client.get_users(warning[0])
            user_name = warned_user.first_name
        except:
            user_name = f"User {warning[0]}"
        
        await message.reply(
            f"✅ Warning #{warn_id} has been deleted\n\n"
            f"User: {user_name}\n"
            f"Reason: {warning[1]}\n"
            f"Deleted by: {sender.mention}"
        )
        
    except Exception as e:
        await message.reply(f"An error occurred while deleting the warning: {str(e)}")
        logger.error(f"Error in warndel command: {e}")

# ---------------------------
# Warns command (Merged list & user)
# ---------------------------
@admin_only
async def warns_command(client: Client, message: types.Message):
    chat = message.chat
    sender = message.from_user
    
    await save_usage(chat, "warns")
    
    # Check if it's a specific user lookup (reply or mention)
    user, _ = await extract_user_and_reason(client, message)
    
    # If user is found, show their warnings (Old /warnsuser behavior)
    if user:
        await show_user_warnings(client, message, chat, user)
    # If no user specified, show all warnings (Old /warnslist behavior)
    else:
        await show_all_warnings(client, message, chat, sender)

async def show_user_warnings(client: Client, message: types.Message, chat, user):
    try:
        await init_warns_db(chat.id)
        table_name = f"warns_chat_{abs(chat.id)}"
        
        # Get all active warnings for the user in this chat
        async with aiosqlite.connect("db/warns.db") as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    f"SELECT id, warned_by, reason, warn_date FROM {table_name} WHERE user_id = ? AND status = 'active' ORDER BY warn_date DESC",
                    (user.id,)
                )
                warnings = await cursor.fetchall()
        
        if not warnings:
            await message.reply(f"{user.first_name} has no active warnings in this chat.")
            return
        
        # Build response lines
        lines = [f"**⚠️ Warnings for {user.mention}**\n"]
        
        for warn_id, warned_by, reason, warn_date in warnings:
            # Format date
            try:
                date_obj = datetime.datetime.fromisoformat(warn_date)
                formatted_date = date_obj.strftime("%Y-%m-%d %H:%M")
            except:
                formatted_date = warn_date
            
            # Get admin info
            try:
                admin_user = await client.get_users(warned_by)
                admin_name = admin_user.mention
            except:
                admin_name = f"Admin {warned_by}"
            
            lines.append(
                f"#{warn_id} - {formatted_date}\n"
                f"**Reason:** {reason}\n"
                f"**By:** {admin_name}\n"
            )
        
        lines.append(f"\nTotal active warnings: {len(warnings)}")
        
        # Split into pages
        pages = await split_text_into_pages(lines)
        
        if len(pages) == 1:
            # Single page, no pagination needed
            await message.reply(pages[0])
        else:
            # Multiple pages, use pagination
            callback_prefix = f"warns_user_{chat.id}_{user.id}"
            
            # Store pagination data
            pagination_data[callback_prefix] = {
                'pages': pages,
                'user_name': user.first_name,
                'chat_id': chat.id,
                'user_id': message.from_user.id  # Store who requested it
            }
            
            # Send first page with navigation
            keyboard = await create_pagination_keyboard(1, len(pages), callback_prefix)
            await message.reply(pages[0], reply_markup=keyboard)
        
    except Exception as e:
        await message.reply(f"An error occurred while fetching warnings: {str(e)}")
        logger.error(f"Error in show_user_warnings: {e}")

async def show_all_warnings(client: Client, message: types.Message, chat, sender):
    try:
        await init_warns_db(chat.id)
        table_name = f"warns_chat_{abs(chat.id)}"
        
        # Get all active warnings in this chat
        async with aiosqlite.connect("db/warns.db") as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    f"SELECT id, user_id, warned_by, reason, warn_date FROM {table_name} WHERE status = 'active' ORDER BY warn_date DESC",
                    ()
                )
                warnings = await cursor.fetchall()
        
        if not warnings:
            await message.reply("No active warnings in this chat.")
            return
        
        # Group warnings by user
        user_warnings = {}
        for warn_id, user_id, warned_by, reason, warn_date in warnings:
            if user_id not in user_warnings:
                user_warnings[user_id] = []
            user_warnings[user_id].append((warn_id, warned_by, reason, warn_date))
        
        # Build response lines
        lines = [f"**⚠️ All Active Warnings in {chat.title or 'this chat'}**\n"]
        
        for user_id, user_warns in user_warnings.items():
            # Get user info
            try:
                user = await client.get_users(user_id)
                user_name = user.mention
            except:
                user_name = f"User {user_id}"
            
            lines.append(f"👤 **{user_name}** ({len(user_warns)} warnings):")
            
            for warn_id, warned_by, reason, warn_date in user_warns[:3]:  # Show max 3 per user
                # Format date
                try:
                    date_obj = datetime.datetime.fromisoformat(warn_date)
                    formatted_date = date_obj.strftime("%m-%d %H:%M")
                except:
                    formatted_date = warn_date
                
                # Get admin info
                try:
                    admin_user = await client.get_users(warned_by)
                    admin_name = admin_user.mention
                except:
                    admin_name = f"Admin {warned_by}"
                
                short_reason = reason[:50] + "..." if len(reason) > 50 else reason
                lines.append(f"  #{warn_id} - {formatted_date} by {admin_name}: {short_reason}")
            
            if len(user_warns) > 3:
                lines.append(f"  ... and {len(user_warns) - 3} more")
            
            lines.append("")
        
        lines.append(f"Total warnings: {len(warnings)}")
        lines.append("Use /warns @user for detailed user warnings")
        
        # Split into pages
        pages = await split_text_into_pages(lines)
        
        if len(pages) == 1:
            # Single page, no pagination needed
            await message.reply(pages[0])
        else:
            # Multiple pages, use pagination
            callback_prefix = f"warns_list_{chat.id}"
            
            # Store pagination data
            pagination_data[callback_prefix] = {
                'pages': pages,
                'chat_title': chat.title or 'this chat',
                'chat_id': chat.id,
                'user_id': sender.id  # Store who requested it
            }
            
            # Send first page with navigation
            keyboard = await create_pagination_keyboard(1, len(pages), callback_prefix)
            await message.reply(pages[0], reply_markup=keyboard)
        
    except Exception as e:
        await message.reply(f"An error occurred while fetching warnings: {str(e)}")
        logger.error(f"Error in show_all_warnings: {e}")

# ---------------------------
# Pagination callback handler
# ---------------------------
async def handle_warns_pagination(client: Client, callback_query):
    """Handle pagination callbacks for warns commands."""
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
        if callback_prefix not in pagination_data:
            await callback_query.answer("Pagination data expired. Please run the command again.", show_alert=True)
            return
        
        data_info = pagination_data[callback_prefix]
        
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
        logger.error(f"Error in warns pagination: {e}")
        await callback_query.answer("An error occurred while navigating.", show_alert=True)
