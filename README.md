# Telethon Multi-Group Manager Bot — Setup Guide

## What it does
- Deletes join/leave/photo-change/title-change/pin/voice-chat service messages within ~1 second.
- Sends a custom welcome message on join, auto-deleted after 5 minutes.
- `/live` or `/stream [link]` — admin-only, broadcasts a live-stream announcement to every group in `TARGET_GROUPS`, auto-deleted after 10 minutes.
- Deletes any message containing a link or `@mention` from non-admin members.
- `/cleanall` — admin-only, scans the last 3000 messages of the current chat and deletes old service messages, with a small delay to avoid FloodWait errors.
- `/groupid` and `/myid` — helper commands to fetch IDs for configuration.

## Step 1: Get API_ID and API_HASH
1. Go to https://my.telegram.org and log in with any phone number.
2. Click **API Development Tools** → create an app (any name/description is fine).
3. Copy the **api_id** and **api_hash** shown.

## Step 2: Get a Bot Token
1. Message **@BotFather** on Telegram.
2. `/newbot`, give it a name and username.
3. Copy the token it gives you.

## Step 3: Install dependencies
```bash
pip install -r requirements.txt
```

## Step 4: Configure `bot.py`
Open `bot.py` and fill in:
```python
API_ID = 12345678
API_HASH = "your_api_hash_here"
BOT_TOKEN = "your_bot_token_here"
ADMIN_IDS = [your_telegram_user_id]
TARGET_GROUPS = [-100xxxxxxxxxx, -100xxxxxxxxxx, ...]
```
To get IDs easily: add the bot to each group as admin first, then run `/groupid` inside each group, and `/myid` in a DM to the bot.

## Step 5: Add the bot to each group
1. Add the bot to all 4–5 groups.
2. Promote it to **Admin** in each group.
3. Make sure it has **Delete Messages** permission — required for everything in this bot to work.

## Step 6: Run
```bash
python bot.py
```
First run will ask you to log in via the bot token automatically (no phone verification needed since it authenticates as a bot).

## Notes
- `/cleanall` only removes **service messages** (join/leave/photo/title/pin/voicechat notices) from history — it does not touch normal user text messages. Run it once per group after setup to clear the old backlog you already have.
- The anti-spam filter allows links from `ADMIN_IDS` and actual Telegram admins/creators of the group — everyone else gets their link/mention message deleted instantly.
- For 24/7 uptime, host this on a free-forever VPS like **Oracle Cloud Free Tier**, then keep it running in the background with `screen` or `tmux`:
  ```bash
  screen -S groupbot
  python3 bot.py
  ```
  Press `Ctrl+A` then `D` to detach — the bot keeps running. Reattach anytime with `screen -r groupbot`.
