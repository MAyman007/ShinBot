import asyncio
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
import logging

logger = logging.getLogger(__name__)

async def extract_user_and_reason(client: Client, message: Message):
    """Extract target user from reply, mention, or username argument."""
    user = None
    reason = None
    
    # First check if replying to a message
    if message.reply_to_message and message.reply_to_message.from_user:
        user = message.reply_to_message.from_user
        # Get reason from command text (everything after the command)
        command_parts = message.text.split(' ', 1)
        if len(command_parts) > 1:
            reason = command_parts[1].strip()
        logger.debug(f"User extracted from reply: {user.first_name} (ID: {user.id})")
        return user, reason
    
    # Check for entities in the message
    if message.entities:
        logger.debug(f"Message text: '{message.text}'")
        logger.debug(f"Found {len(message.entities)} entities")
        
        for i, entity in enumerate(message.entities):
            logger.debug(f"Entity {i}: type={entity.type}, offset={entity.offset}, length={entity.length}")
            
            # Handle text_mention (display name mentions without @)
            if entity.type.name == "TEXT_MENTION" or entity.type == "text_mention":
                if hasattr(entity, 'user') and entity.user:
                    user = entity.user
                    logger.debug(f"Found text_mention: {user.first_name} {user.last_name or ''} (ID: {user.id})")
                    
                    # Extract reason from everything after this entity
                    mention_end = entity.offset + entity.length
                    if mention_end < len(message.text):
                        reason_text = message.text[mention_end:].strip()
                        # Clean leading punctuation
                        reason_text = reason_text.lstrip('.,!?;: ')
                        if reason_text:
                            reason = reason_text
                    
                    return user, reason
            
            # Handle regular mentions with @username
            elif entity.type.name == "MENTION" or entity.type == "mention":
                mention_text = message.text[entity.offset:entity.offset + entity.length]
                logger.debug(f"Found mention: '{mention_text}'")
                
                try:
                    # Get user by username (with or without @)
                    username = mention_text.lstrip('@')
                    user = await client.get_users(username)
                    logger.debug(f"Resolved mention to user: {user.first_name} {user.last_name or ''} (ID: {user.id})")
                    
                    # Extract reason from everything after this entity
                    mention_end = entity.offset + entity.length
                    if mention_end < len(message.text):
                        reason_text = message.text[mention_end:].strip()
                        # Clean leading punctuation
                        reason_text = reason_text.lstrip('.,!?;: ')
                        if reason_text:
                            reason = reason_text
                    
                    return user, reason
                    
                except Exception as e:
                    logger.warning(f"Could not resolve mention '{mention_text}': {e}")
                    continue
    
    # Fallback: Parse command arguments
    logger.debug("No entities found or no user extracted from entities, trying command arguments")
    
    if not message.text:
        logger.debug("No message text available")
        return None, None
    
    command_parts = message.text.split()
    logger.debug(f"Command parts: {command_parts}")
    
    if len(command_parts) < 2:
        logger.debug("Not enough command parts")
        return None, None
    
    user_identifier = command_parts[1]
    logger.debug(f"Trying to resolve user identifier: '{user_identifier}'")
    
    # Clean the user identifier
    cleaned_identifier = user_identifier.strip('.,!?;:')
    if cleaned_identifier.startswith('@'):
        cleaned_identifier = cleaned_identifier[1:]
    
    # Skip if it looks like a display name with spaces or special characters
    if not user_identifier.startswith('@') and not cleaned_identifier.isdigit():
        full_text = ' '.join(command_parts[1:])
        if ' ' in full_text or any(ord(char) > 127 for char in cleaned_identifier):
            logger.debug(f"Skipping resolution for apparent display name: '{full_text}'")
            return None, None
    
    # Try to resolve user
    try:
        if user_identifier.startswith('@') or not cleaned_identifier.isdigit():
            # Username
            user = await client.get_users(cleaned_identifier)
            logger.debug(f"Resolved username '{cleaned_identifier}' to user: {user.first_name}")
        else:
            # User ID
            user_id = int(cleaned_identifier)
            user = await client.get_users(user_id)
            logger.debug(f"Resolved user ID {user_id} to user: {user.first_name}")
        
        # Extract reason from remaining parts
        if len(command_parts) > 2:
            reason = ' '.join(command_parts[2:]).strip()
        
        return user, reason
        
    except Exception as e:
        logger.warning(f"Could not resolve user identifier '{user_identifier}': {e}")
        return None, None

async def split_text_into_pages(lines, max_length=1000):
    """Split text lines into pages that fit within message limits."""
    pages = []
    current_page = ""
    
    for i, line in enumerate(lines):
        # Yield control every 50 lines for very large datasets
        if i % 50 == 0:
            await asyncio.sleep(0)
            
        # Check if adding this line would exceed the limit
        if len(current_page) + len(line) + 2 > max_length and current_page:
            pages.append(current_page.strip())
            current_page = line
        else:
            if current_page:
                current_page += "\n" + line
            else:
                current_page = line
    
    # Add the last page
    if current_page:
        pages.append(current_page.strip())
    
    return pages

async def create_pagination_keyboard(current_page, total_pages, callback_prefix):
    """Create pagination keyboard with Previous/Next buttons."""
    keyboard = []
    buttons = []
    
    # Previous button
    if current_page > 1:
        buttons.append(InlineKeyboardButton(
            "◀️ Previous", 
            callback_data=f"{callback_prefix}_{current_page - 1}"
        ))
    
    # Page indicator
    buttons.append(InlineKeyboardButton(
        f"{current_page}/{total_pages}", 
        callback_data="ignore"
    ))
    
    # Next button
    if current_page < total_pages:
        buttons.append(InlineKeyboardButton(
            "Next ▶️", 
            callback_data=f"{callback_prefix}_{current_page + 1}"
        ))
    
    if buttons:
        keyboard.append(buttons)
    
    return InlineKeyboardMarkup(keyboard) if keyboard else None

def get_markdown_mention(user):
    """Return a markdown link to the user's profile."""
    try: md_mention = f"[{user.first_name}](https://t.me/{user.user_name})"
    except: md_mention = f"[{user.first_name}](tg://user?id={user.id})"
    return md_mention