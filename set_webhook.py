"""
Run this ONCE after deploying to Vercel, to tell Telegram where to send
messages.

Usage:
    python3 set_webhook.py

It reads TELEGRAM_BOT_TOKEN from your environment and asks for your
deployed Vercel URL, then registers the webhook.
"""

import os
import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or input("Enter your Telegram bot token: ").strip()
vercel_url = input("Enter your deployed Vercel URL (e.g. https://your-project.vercel.app): ").strip()

webhook_url = f"{vercel_url.rstrip('/')}/api/webhook"

resp = requests.post(
    f"https://api.telegram.org/bot{TOKEN}/setWebhook",
    json={"url": webhook_url},
)

print(resp.json())

if resp.json().get("ok"):
    print(f"\n✅ Webhook registered successfully: {webhook_url}")
else:
    print("\n❌ Something went wrong. Check your token and URL.")
