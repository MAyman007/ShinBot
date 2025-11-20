import logging
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import UserNotParticipant, ChatAdminRequired, UserAdminInvalid
from utils.decorators import admin_only, protect_admins, require_permission
from utils.helpers import extract_user_and_reason
from pyrogram import types
from utils.usage import save_usage

logger = logging.getLogger(__name__)

async def check_bot_promote_permissions(client: Client, chat_id: int) -> tuple[bool, str]:
    """Check if bot has permission to promote members"""
    try:
        me = await client.get_me()
        bot_member = await client.get_chat_member(chat_id, me.id)
        
        logger.info(f"Bot status: {bot_member.status}")
        
        # Check if bot is admin and has promote privileges
        if hasattr(bot_member, 'privileges') and bot_member.privileges:
            can_promote = bot_member.privileges.can_promote_members
            logger.info(f"Bot can_promote_members: {can_promote}")
            if not can_promote:
                return False, "I don't have the 'Add new admins' permission. Please grant this permission in chat settings."
            return True, ""
        
        # Check if bot has admin status
        status_str = str(bot_member.status).lower()
        if 'administrator' in status_str or 'admin' in status_str:
            return True, ""
        
        return False, "I'm not an administrator in this chat."
    except Exception as e:
        logger.error(f"Error checking bot permissions: {e}")
        return False, f"Error checking permissions: {str(e)}"

@admin_only
async def promote_user(client: Client, message: Message):
    """Promote a user to administrator"""
    chat = message.chat
    await save_usage(chat, "promote")
    
    try:
        # Check bot permissions first
        can_promote, error_msg = await check_bot_promote_permissions(client, message.chat.id)
        if not can_promote:
            await message.reply(f"❌ {error_msg}")
            return
        
        user, reason = await extract_user_and_reason(client, message)
        if not user:
            await message.reply("❌ Please specify a user to promote.\n**Usage:** `/promote @username [title]` or reply to a message with `/promote [title]`")
            return
        
        # Check if trying to promote yourself
        if user.id == message.from_user.id:
            await message.reply("❌ You cannot promote yourself!")
            return
        
        # Check if trying to promote the bot
        me = await client.get_me()
        if user.id == me.id:
            await message.reply("❌ I cannot promote myself!")
            return
        
        # Check if user is already an admin
        try:
            member = await client.get_chat_member(message.chat.id, user.id)
            status_str = str(member.status).lower()
            if ('owner' in status_str or 'creator' in status_str or 
                'administrator' in status_str or 'admin' in status_str):
                await message.reply(f"❌ {user.first_name} is already an administrator.")
                return
        except UserNotParticipant:
            await message.reply(f"❌ {user.first_name} is not in this chat.")
            return
        
        # Use reason as custom title if provided, otherwise use default
        custom_title = reason if reason and len(reason) <= 16 else None
        
        # Try promoting with minimal permissions first
        try:
            await client.promote_chat_member(
                message.chat.id, 
                user.id,
                privileges=types.ChatPrivileges(
                    can_manage_chat=False,
                    can_delete_messages=True,
                    can_manage_video_chats=False,
                    can_restrict_members=True,
                    can_promote_members=False,
                    can_change_info=False,
                    can_invite_users=True,
                    can_pin_messages=True,
                    can_manage_topics=False
                )
            )
        except Exception as e:
            logger.error(f"First promotion attempt failed: {e}")
            # Try with even more minimal permissions
            await client.promote_chat_member(
                message.chat.id, 
                user.id,
                privileges=types.ChatPrivileges(
                    can_manage_chat=False,
                    can_delete_messages=True,
                    can_manage_video_chats=False,
                    can_restrict_members=False,
                    can_promote_members=False,
                    can_change_info=False,
                    can_invite_users=False,
                    can_pin_messages=False,
                    can_manage_topics=False
                )
            )
        
        # Set custom title if provided (after promotion)
        if custom_title:
            try:
                await client.set_administrator_title(message.chat.id, user.id, custom_title)
            except Exception as e:
                logger.warning(f"Failed to set custom title: {e}")
        
        promote_text = f"⬆️ **User Promoted**\n"
        promote_text += f"**User:** {user.mention}\n"
        promote_text += f"**Admin:** {message.from_user.mention}\n"
        if custom_title:
            promote_text += f"**Title:** {custom_title}"
        
        await message.reply(promote_text)
        logger.info(f"User {user.id} promoted in chat {message.chat.id} by {message.from_user.id}")
        
    except ChatAdminRequired:
        await message.reply("❌ I need admin privileges with 'Add new admins' permission to promote users.")
    except Exception as e:
        await message.reply(f"❌ Error promoting user: {str(e)}")
        logger.error(f"Error in promote command: {e}")

@require_permission("can_restrict_members")
@protect_admins
async def kick_user(client: Client, message: Message):
    """Kick a user from the chat"""
    chat = message.chat
    await save_usage(chat, "kick")
    
    try:
        user, reason = await extract_user_and_reason(client, message)
        if not user:
            await message.reply("❌ Please specify a user to kick.\n**Usage:** `/kick @username [reason]` or reply to a message with `/kick [reason]`")
            return
        
        # Check if trying to kick yourself
        if user.id == message.from_user.id:
            await message.reply("❌ You cannot kick yourself!")
            return
        
        # Check if trying to kick the bot
        me = await client.get_me()
        if user.id == me.id:
            await message.reply("❌ I cannot kick myself!")
            return
        
        # Check if user is in the chat and their status
        try:
            member = await client.get_chat_member(message.chat.id, user.id)
            
            # Check if trying to kick an admin
            status_str = str(member.status).lower()
            if ('owner' in status_str or 'creator' in status_str or 
                'administrator' in status_str or 'admin' in status_str):
                await message.reply(f"❌ Cannot kick {user.first_name} - user is an admin.")
                return
                
        except UserNotParticipant:
            await message.reply(f"❌ {user.first_name} is not in this chat.")
            return
        
        # Kick the user (ban then unban to allow rejoining)
        await client.ban_chat_member(message.chat.id, user.id)
        await client.unban_chat_member(message.chat.id, user.id)
        
        kick_text = f"👢 **User Kicked**\n"
        kick_text += f"**User:** {user.mention}\n"
        kick_text += f"**Admin:** {message.from_user.mention}\n"
        if reason:
            kick_text += f"**Reason:** {reason}"
        
        await message.reply(kick_text)
        logger.info(f"User {user.id} kicked from chat {message.chat.id} by {message.from_user.id}")
        
    except ChatAdminRequired:
        await message.reply("❌ I need admin privileges to kick users.")
    except UserAdminInvalid:
        await message.reply("❌ Cannot kick this user.")
    except Exception as e:
        await message.reply(f"❌ Error kicking user: {str(e)}")
        logger.error(f"Error in kick command: {e}")
