from pyrogram import Client
import handlers

# ---------- General Callback Query Handler ----------
async def button_click_handler(client: Client, callback_query):
    data = callback_query.data
    
    # Handle help callbacks
    if data.startswith("help_"):
        await handlers.handle_help_callback(client, callback_query)
        return
    
    # Handle search navigation callbacks
    if data.startswith("search_"):
        await handlers.handle_search_callback(client, callback_query)
        return
    
    # Handle RPS callbacks
    if data.startswith("rps_"):
        await handlers.rps_callback_handler(client, callback_query)
        return
    
    # Handle TicTacToe callbacks
    if data.startswith("ttt_"):
        await handlers.tictactoe_callback_handler(client, callback_query)
        return
    
    # Handle warns pagination callbacks
    if data.startswith("warns_"):
        await handlers.handle_warns_pagination(client, callback_query)
        return
    
    # Handle mutes pagination callbacks
    if data.startswith("mutes_"):
        await handlers.handle_mutes_pagination(client, callback_query)
        return
    
    # Handle timer pagination callbacks
    if data.startswith("timers_") or data.startswith("timerdel_"):
        await handlers.handle_timer_pagination(client, callback_query)
        return
    
    # Handle YouTube callbacks
    if data.startswith("yt_"):
        if data.startswith("yt_audio_"):
            await handlers.yt_audio_button(client, callback_query)
        else:
            await handlers.yt_quality_button(client, callback_query)
        return
    
    # Handle subtitle callbacks
    if data.startswith("subs_"):
        await handlers.yt_subs_callback(client, callback_query)
        return
    
    # Handle cancel download callbacks
    if data.startswith("cancel_"):
        await handlers.cancel_download_callback(client, callback_query)
        return
    
    # Handle ignore callback
    if data == "ignore":
        await handlers.ignore_callback(client, callback_query)
        return
    
    # Handle anime pagination callbacks
    if data.startswith("anime"):
        await handlers.handle_anime_callback(client, callback_query)
        return
    
    # Handle manga pagination callbacks  
    if data.startswith("manga"):
        await handlers.handle_manga_callback(client, callback_query)
        return