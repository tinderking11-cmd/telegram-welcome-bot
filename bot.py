"""
Telethon Multi-Group Manager Bot
==================================

Features:
1. Instant service/system message eraser (join/leave/photo/title/pin/voicechat) — deletes within ~1 sec.
2. Custom welcome message on join, auto-deleted after 5 minutes (300s).
3. /live or /stream command — admin-only, broadcasts a live-stream announcement to
   all TARGET_GROUPS at once, each copy auto-deleted after 10 minutes (600s).
4. Anti-spam / link filter — deletes messages containing links or @mentions from
   non-admin members.
5. /cleanall command — admin-only, scans the last 3000 messages in the current chat
   and deletes historical service messages, with a small delay to avoid FloodWait.

Requirements:
    pip install telethon

Run:
    python bot.py
"""

import asyncio
import logging
import re

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.tl.types import Chat, Channel

# ============================== CONFIG ==============================
# Get API_ID and API_HASH from https://my.telegram.org (required by Telethon
# even for bot accounts — log in with the phone number that owns the bot,
# or any account, and create an app to get these values).
API_ID = 38481512                      # <-- REPLACE with your api_id (int)
API_HASH = "94f42d72507a96e2b0f3ac43a218d666"        # <-- REPLACE with your api_hash (str)
BOT_TOKEN = "8752965494:AAEpbwRhyXjzksUB2pm90Btj8bxmGYyIrJQ"  # <-- REPLACE with token from @BotFather

# Telegram user IDs allowed to run /live, /stream, /cleanall.
# Get your own ID by messaging @userinfobot on Telegram.
ADMIN_IDS = [
    123456789,  # <-- REPLACE with your own Telegram user ID(s)
]

# Chat IDs (or @usernames) of every group this bot manages / broadcasts to.
# Use the /groupid command inside each group to fetch its numeric ID.
TARGET_GROUPS = [
    -1001111111111,  # group 1
    -1002222222222,  # group 2
    -1003333333333,  # group 3
    -1004444444444,  # group 4
    -1005555555555,  # group 5
]

WELCOME_DELETE_AFTER = 300   # 5 minutes
LIVE_DELETE_AFTER = 600      # 10 minutes
CLEANALL_SCAN_LIMIT = 3000   # how many past messages /cleanall scans
CLEANALL_DELAY = 0.2         # seconds between deletions to dodge FloodWait

WELCOME_TEXT = (
    "🎉 **Welcome to the group, {name}!**\n\n"
    "We're glad to have you here.\n\n"
    "📌 **Group rules:**\n"
    "✅ You can watch live streams\n"
    "❌ Sending messages is not allowed\n"
    "❌ Sharing links/content is not allowed\n\n"
    "Thanks for following the rules — enjoy your stay! 🙏"
)

LIVE_TEXT_TEMPLATE = (
    "🔴 **LIVE STREAM IS NOW ON!**\n\n"
    "Join now, don't miss it! 🎥✨\n"
    "{link_line}"
)

LINK_PATTERN = re.compile(r"(https?://|t\.me/|@\w+)", re.IGNORECASE)

# ======================================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

client = TelegramClient("group_manager_bot", API_ID, API_HASH)


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

async def schedule_delete(chat_id, message_id, delay):
    """Deletes a message after `delay` seconds without blocking the event loop."""
    async def _worker():
        try:
            await asyncio.sleep(delay)
            await client.delete_messages(chat_id, message_id)
        except Exception as e:
            logger.warning("Scheduled delete failed for %s/%s: %s", chat_id, message_id, e)

    asyncio.create_task(_worker())


async def is_authorized_admin(event) -> bool:
    """True if the sender is in ADMIN_IDS, or is an actual admin/creator of the chat."""
    sender_id = event.sender_id
    if sender_id in ADMIN_IDS:
        return True
    try:
        perms = await client.get_permissions(event.chat_id, sender_id)
        return perms.is_admin or perms.is_creator
    except Exception:
        return False


def is_group_chat(chat) -> bool:
    return isinstance(chat, (Chat, Channel))


# ------------------------------------------------------------------ #
# 1) Instant service message eraser (join / leave / photo / title / pin / voicechat)
# ------------------------------------------------------------------ #

@client.on(events.ChatAction())
async def on_chat_action(event):
    try:
        # Delete the underlying service message itself — covers join, add, leave,
        # kick, photo change, title change, pin notice, and voice-chat start/end,
        # since all of these arrive as Telegram service (action) messages.
        if event.action_message:
            await client.delete_messages(event.chat_id, event.action_message.id)
    except Exception as e:
        logger.warning("Could not delete service message in %s: %s", event.chat_id, e)

    # Welcome message only for actual joins (not leaves/kicks/other actions)
    try:
        if event.user_joined or event.user_added:
            users = await event.get_users()
            for user in users or []:
                if user.bot:
                    continue
                name = user.first_name or "friend"
                sent = await client.send_message(
                    event.chat_id, WELCOME_TEXT.format(name=name)
                )
                await schedule_delete(event.chat_id, sent.id, WELCOME_DELETE_AFTER)
    except Exception as e:
        logger.warning("Welcome message failed in %s: %s", event.chat_id, e)


# ------------------------------------------------------------------ #
# 2) /live or /stream — broadcast live announcement to all TARGET_GROUPS
# ------------------------------------------------------------------ #

@client.on(events.NewMessage(pattern=r"^/(live|stream)(?:\s+(.+))?$"))
async def on_go_live(event):
    if event.sender_id not in ADMIN_IDS:
        await event.reply("❌ You are not authorized to use this command.")
        return

    link = event.pattern_match.group(2) or ""
    link_line = f"🔗 {link}" if link else ""
    text = LIVE_TEXT_TEMPLATE.format(link_line=link_line)

    sent_count, failed = 0, []
    for group in TARGET_GROUPS:
        try:
            sent = await client.send_message(group, text)
            sent_count += 1
            await schedule_delete(group, sent.id, LIVE_DELETE_AFTER)
        except Exception as e:
            logger.warning("Failed to send live message to %s: %s", group, e)
            failed.append(group)

    reply = f"✅ Live announcement sent to {sent_count}/{len(TARGET_GROUPS)} groups."
    if failed:
        reply += f"\n⚠️ Failed for: {failed}"
    await event.reply(reply)


# ------------------------------------------------------------------ #
# 3) Anti-spam / link filter for non-admin members
# ------------------------------------------------------------------ #

@client.on(events.NewMessage())
async def on_new_message(event):
    # Ignore private chats, commands (handled above), and non-group chats
    if event.is_private:
        return
    if event.raw_text.startswith("/"):
        return

    chat = await event.get_chat()
    if not is_group_chat(chat):
        return

    if not event.raw_text:
        return

    if not LINK_PATTERN.search(event.raw_text):
        return

    # Allow admins/owners and configured ADMIN_IDS to post links freely
    if await is_authorized_admin(event):
        return

    try:
        await client.delete_messages(event.chat_id, event.id)
        logger.info("Deleted a link/spam message from user %s in %s", event.sender_id, event.chat_id)
    except Exception as e:
        logger.warning("Could not delete spam message in %s: %s", event.chat_id, e)


# ------------------------------------------------------------------ #
# 4) /cleanall — bulk-delete historical service messages
# ------------------------------------------------------------------ #

@client.on(events.NewMessage(pattern=r"^/cleanall$"))
async def on_cleanall(event):
    if not await is_authorized_admin(event):
        await event.reply("❌ Only admins can use this command.")
        return

    status = await event.reply(
        f"🧹 Scanning the last {CLEANALL_SCAN_LIMIT} messages for old service "
        f"messages... this may take a while."
    )

    deleted = 0
    scanned = 0
    try:
        async for message in client.iter_messages(event.chat_id, limit=CLEANALL_SCAN_LIMIT):
            scanned += 1
            if message.action is not None:
                try:
                    await client.delete_messages(event.chat_id, message.id)
                    deleted += 1
                except FloodWaitError as fw:
                    logger.warning("FloodWait hit, sleeping %s seconds", fw.seconds)
                    await asyncio.sleep(fw.seconds)
                except Exception as e:
                    logger.warning("Could not delete message %s: %s", message.id, e)
            await asyncio.sleep(CLEANALL_DELAY)
    except Exception as e:
        logger.error("cleanall failed in %s: %s", event.chat_id, e)
        await status.edit(f"⚠️ Cleaning stopped early due to an error: {e}")
        return

    result = await status.edit(
        f"✅ Done. Scanned {scanned} messages, deleted {deleted} old service messages."
    )
    await schedule_delete(event.chat_id, result.id, 10)


# ------------------------------------------------------------------ #
# 5) Helper commands to make setup easier
# ------------------------------------------------------------------ #

@client.on(events.NewMessage(pattern=r"^/groupid$"))
async def on_groupid(event):
    await event.reply(f"This group's Chat ID:\n`{event.chat_id}`")


@client.on(events.NewMessage(pattern=r"^/myid$"))
async def on_myid(event):
    await event.reply(f"Your Telegram User ID:\n`{event.sender_id}`")


# ------------------------------------------------------------------ #
# Entrypoint
# ------------------------------------------------------------------ #

def main():
    if BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise SystemExit("❌ Set BOT_TOKEN before running.")
    if not API_ID or API_HASH == "your_api_hash_here":
        raise SystemExit("❌ Set API_ID and API_HASH before running (from https://my.telegram.org).")

    client.start(bot_token=BOT_TOKEN)
    logger.info("✅ Bot is up and running across all configured groups...")
    client.run_until_disconnected()


if __name__ == "__main__":
    main()
