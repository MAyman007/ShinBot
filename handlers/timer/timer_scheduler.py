import asyncio
import datetime
import aiosqlite
import os
from utils.helpers import get_markdown_mention

# Dictionary to track active timer tasks
# Key: (chat_id, timer_id), Value: asyncio task
active_timer_tasks = {}

async def init_timer_db():
    """Initialize the timer database with chat-specific tables."""
    os.makedirs('db', exist_ok=True)
    
    async with aiosqlite.connect("db/timers.db") as connection:
        # Make sure foreign keys are enforced
        await connection.execute("PRAGMA foreign_keys = ON")
        
        # Create master chats table to track all chats with timers
        async with connection.cursor() as cursor:
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS timer_chats (
                    chat_id INTEGER PRIMARY KEY
                )
            """)
            await connection.commit()

async def get_chat_timer_table(connection, chat_id):
    """Get or create a chat-specific timer table."""
    # Sanitize chat_id for table name
    chat_id_str = str(chat_id).replace("-", "")
    table_name = f"timers_for_{chat_id_str}"
    
    async with connection.cursor() as cursor:
        # Add chat to master table if not exists
        await cursor.execute(
            "INSERT OR IGNORE INTO timer_chats (chat_id) VALUES (?)",
            (chat_id,)
        )
        
        # Create chat-specific timer table if not exists
        await cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                end_time TEXT,
                reason TEXT,
                message_id INTEGER,
                status TEXT DEFAULT 'active',
                message_link TEXT
            )
        """)
        
        # Add message_link column if it doesn't exist (for backward compatibility)
        try:
            await cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN message_link TEXT")
            await connection.commit()
        except aiosqlite.OperationalError:
            # Column already exists, ignore
            pass
        
    return table_name

async def check_pending_timers(client):
    """
    Call this function once (in a background task) to schedule notifications
    for all timers that haven't expired.
    """
    # Ensure database and tables exist
    await init_timer_db()
    
    async with aiosqlite.connect("db/timers.db") as connection:
        # Get all chat IDs
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT chat_id FROM timer_chats")
            chat_ids = await cursor.fetchall()
        
        for (chat_id,) in chat_ids:
            table_name = await get_chat_timer_table(connection, chat_id)
            
            # Get all active timers for this chat
            async with connection.cursor() as cursor:
                await cursor.execute(f"SELECT id, user_id, end_time, reason, message_id, message_link FROM {table_name} WHERE status = 'active'")
                timers = await cursor.fetchall()
                
                for timer_id, user_id, end_time_str, reason, message_id, message_link in timers:
                    end_time = datetime.datetime.fromisoformat(end_time_str)
                    now = datetime.datetime.now()
                    
                    if end_time <= now:
                        # Timer has already expired, send notification
                        end_message = "Your timer has ended."
                        if reason:
                            end_message += f"\nReason: {reason}"
                        
                        # If it's a group chat, mention the user
                        if chat_id < 0:  # Negative chat_id indicates group/supergroup
                            try:
                                user = await client.get_users(user_id)
                                end_message = f"{get_markdown_mention(user)}, y" + end_message[1:]
                            except:
                                end_message = f"[@user](tg://user?id={user_id}), y" + end_message[1:]
                        
                        await client.send_message(chat_id, end_message, reply_to_message_id=message_id, disable_web_page_preview=True)
                        
                        # Update the timer status to 'ended'
                        await cursor.execute(f"UPDATE {table_name} SET status = 'ended' WHERE id = ?", (timer_id,))
                    else:
                        # Schedule timer notification for future
                        delay = (end_time - now).total_seconds()
                        task = asyncio.create_task(schedule_timer(client, chat_id, timer_id, delay, reason, message_id, user_id))
                        
                        # Store the task in our global dictionary
                        timer_key = (chat_id, timer_id)
                        active_timer_tasks[timer_key] = task
                        
                await connection.commit()

async def schedule_timer(client, chat_id, timer_id, delay, reason, message_id=None, user_id=None):
    """
    Sleeps for the specified delay, then notifies the user that the timer has ended.
    After sending a message, update the timer status to 'ended'.
    """
    try:
        await asyncio.sleep(delay)
        
        # Check if the timer still exists and is active
        async with aiosqlite.connect("db/timers.db") as connection:
            table_name = await get_chat_timer_table(connection, chat_id)
            
            async with connection.cursor() as cursor:
                await cursor.execute(
                    f"SELECT user_id FROM {table_name} WHERE id = ? AND status = 'active'",
                    (timer_id,)
                )
                result = await cursor.fetchone()
                
                if result:  # Timer still exists and is active
                    if user_id is None:
                        user_id = result[0]  # Get user_id from database if not provided
                    
                    # Send notification
                    end_message = "Your timer has ended."
                    if reason:
                        end_message += f"\nReason: **{reason}**"
                    
                    # If it's a group chat, mention the user
                    if chat_id < 0:  # Negative chat_id indicates group/supergroup
                        try:
                            user = await client.get_users(user_id)
                            end_message = f"{get_markdown_mention(user)}, y" + end_message[1:]
                        except:
                            end_message = f"[@user](tg://user?id={user_id}), y" + end_message[1:]
                    
                    if message_id:
                        await client.send_message(chat_id, end_message, reply_to_message_id=message_id, disable_web_page_preview=True)
                    else:
                        await client.send_message(chat_id, end_message, disable_web_page_preview=True)
                    
                    # Update the timer status to 'ended'
                    await cursor.execute(
                        f"UPDATE {table_name} SET status = 'ended' WHERE id = ?",
                        (timer_id,)
                    )
                    await connection.commit()
    finally:
        # Clean up the task from our dictionary
        timer_key = (chat_id, timer_id)
        if timer_key in active_timer_tasks:
            del active_timer_tasks[timer_key]

async def cancel_timer(chat_id, timer_id):
    """
    Cancel a timer by updating its status to 'canceled' and
    cancelling any scheduled task.
    """
    try:
        async with aiosqlite.connect("db/timers.db") as connection:
            table_name = await get_chat_timer_table(connection, chat_id)
            
            async with connection.cursor() as cursor:
                # Check if timer exists
                await cursor.execute(
                    f"SELECT id FROM {table_name} WHERE id = ? AND status = 'active'",
                    (timer_id,)
                )
                result = await cursor.fetchone()
                
                if result:
                    # Update the timer status to 'canceled'
                    await cursor.execute(
                        f"UPDATE {table_name} SET status = 'canceled' WHERE id = ?",
                        (timer_id,)
                    )
                    await connection.commit()
                    
                    # Try to cancel the associated task if it exists
                    timer_key = (chat_id, timer_id)
                    if timer_key in active_timer_tasks:
                        task = active_timer_tasks[timer_key]
                        if not task.done():
                            task.cancel()
                        del active_timer_tasks[timer_key]
                        
                    return True
        return False
    except Exception as e:
        print(f"Error cancelling timer: {e}")
        return False

async def get_timers(chat_id, include_inactive=False):
    """
    Get all timers for a chat, optionally including inactive (ended/canceled) timers.
    Returns a list of (id, user_id, end_time, reason, message_id, status) tuples.
    """
    try:
        async with aiosqlite.connect("db/timers.db") as connection:
            table_name = await get_chat_timer_table(connection, chat_id)
            
            async with connection.cursor() as cursor:
                if include_inactive:
                    # Get all timers regardless of status
                    await cursor.execute(
                        f"SELECT id, user_id, end_time, reason, message_id, status, message_link FROM {table_name}"
                    )
                else:
                    # Get only active timers
                    await cursor.execute(
                        f"SELECT id, user_id, end_time, reason, message_id, status, message_link FROM {table_name} WHERE status = 'active'"
                    )
                
                timers = await cursor.fetchall()
                return timers
    except Exception as e:
        print(f"Error getting timers: {e}")
        return []