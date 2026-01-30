from pyrogram import filters, Client
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from config import ENABLE_GEMINI_COMMAND, ENABLE_IMAGINE_COMMAND, ENABLE_MEME_COMMAND
import handlers as handlers
from handlers.callback_handlers import button_click_handler
from handlers.trivia.trivia_commands import register_trivia_handlers


# Register command handlers
def register_handlers(client: Client):
    # Pyrogram's command filter handles the bot username suffix automatically.
    client.add_handler(MessageHandler(handlers.start_command, filters.command("start")))
    client.add_handler(MessageHandler(handlers.help_command, filters.command("help")))
    client.add_handler(MessageHandler(handlers.mute_command, filters.command("mute")))
    client.add_handler(MessageHandler(handlers.unmute_command, filters.command("unmute")))
    client.add_handler(MessageHandler(handlers.mutes_command, filters.command("mutes")))
    client.add_handler(MessageHandler(handlers.lock_command, filters.command("lock")))
    client.add_handler(MessageHandler(handlers.unlock_command, filters.command("unlock")))
    client.add_handler(MessageHandler(handlers.list_join_dates, filters.command("joindate")))
    client.add_handler(MessageHandler(handlers.usagedata_command, filters.command("usagedata")))
    client.add_handler(MessageHandler(handlers.character_command, filters.command("character")))
    client.add_handler(MessageHandler(handlers.anime_command, filters.command("anime")))
    client.add_handler(MessageHandler(handlers.manga_command, filters.command("manga")))
    client.add_handler(MessageHandler(handlers.aghpb_command, filters.command("aghpb")))
    client.add_handler(MessageHandler(handlers.echo_command, filters.command("echo")))
    client.add_handler(MessageHandler(handlers.ping_command, filters.command("ping")))
    client.add_handler(MessageHandler(handlers.feedback_command, filters.command("feedback")))
    client.add_handler(MessageHandler(handlers.search_command, filters.command("search")))
    client.add_handler(MessageHandler(handlers.chatid_command, filters.command("chatid")))
    client.add_handler(MessageHandler(handlers.pfp_command, filters.command("pfp")))
    client.add_handler(MessageHandler(handlers.userinfo_command, filters.command("userinfo")))
    client.add_handler(MessageHandler(handlers.chatpfp_command, filters.command("chatpfp")))
    client.add_handler(MessageHandler(handlers.calc_command, filters.command("calc")))
    client.add_handler(MessageHandler(handlers.qr_command, filters.command("qr")))
    client.add_handler(MessageHandler(handlers.groupinfo_command, filters.command("groupinfo")))
    client.add_handler(MessageHandler(handlers.timer_command, filters.command("timer")))
    client.add_handler(MessageHandler(handlers.list_timers_command, filters.command("timers")))
    client.add_handler(MessageHandler(handlers.remove_timer_command, filters.command("timerdel")))
    client.add_handler(MessageHandler(handlers.reverse_command, filters.command("reverse")))
    client.add_handler(MessageHandler(handlers.slot_command, filters.command("slot")))
    client.add_handler(MessageHandler(handlers.coinflip_command, filters.command("coinflip")))
    client.add_handler(MessageHandler(handlers.choose_command, filters.command("choose")))
    client.add_handler(MessageHandler(handlers.rps_command, filters.command("rps")))
    client.add_handler(MessageHandler(handlers.tictactoe_command, filters.command("tictactoe")))
    client.add_handler(MessageHandler(handlers.geekjoke_command, filters.command("geekjoke")))
    client.add_handler(MessageHandler(handlers.dadjoke_command, filters.command("dadjoke")))
    client.add_handler(MessageHandler(handlers.dog_command, filters.command("dog")))
    client.add_handler(MessageHandler(handlers.cat_command, filters.command("cat")))
    client.add_handler(MessageHandler(handlers.affirmation_command, filters.command("affirmation")))
    client.add_handler(MessageHandler(handlers.advice_command, filters.command("advice")))
    client.add_handler(MessageHandler(handlers.warn_command, filters.command("warn")))
    client.add_handler(MessageHandler(handlers.warndel_command, filters.command("warndel")))
    client.add_handler(MessageHandler(handlers.warns_command, filters.command("warns")))
    client.add_handler(MessageHandler(handlers.ban_user, filters.command("ban")))
    client.add_handler(MessageHandler(handlers.unban_user, filters.command("unban")))
    client.add_handler(MessageHandler(handlers.banslist_command, filters.command("bans")))
    client.add_handler(MessageHandler(handlers.kick_user, filters.command("kick")))
    client.add_handler(MessageHandler(handlers.promote_user, filters.command("promote")))
    client.add_handler(MessageHandler(handlers.yt_command, filters.command("yt")))
    if ENABLE_MEME_COMMAND: client.add_handler(MessageHandler(handlers.meme_command, filters.command("meme")))
    if ENABLE_GEMINI_COMMAND: client.add_handler(MessageHandler(handlers.gemini_command, filters.command("gemini")))
    if ENABLE_IMAGINE_COMMAND: client.add_handler(MessageHandler(handlers.imagine_command, filters.command("imagine")))

    # Register a handler for text messages that are not commands
    all_commands = [
        "start", "help", "mute", "unmute", "mutelist", "lock", "unlock", "joindate", "usagedata", "character", "anime","manga", "aghpb",
        "echo", "ping", "search", "feedback", "calc", "qr", "groupinfo", "pfp", "chatpfp", "chatid", "timer", "userinfo",
        "timers", "timerdel", "reverse", "slot", "coinflip", "geekjoke", "dadjoke", "tictactoe",
        "dog", "cat", "affirmation", "advice", "choose", "rps", "yt", "warn", "warndel", "warns",
        "ban", "unban", "bans", "kick", "mute", "unmute", "promote"
    ]

    # Add conditional commands to the list
    if ENABLE_MEME_COMMAND:
        all_commands.append("meme")
    if ENABLE_GEMINI_COMMAND:
        all_commands.append("gemini")
    if ENABLE_IMAGINE_COMMAND:
        all_commands.append("imagine")

    # Register Arabic greeting handlers (before the generic text handler)
    register_trivia_handlers(client)

    client.add_handler(
        MessageHandler(
            filters.text & ~filters.command(all_commands)
        )
    )

    # Register a callback query handler for button clicks
    client.add_handler(CallbackQueryHandler(button_click_handler))
