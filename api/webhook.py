"""
Vercel Serverless Function - Telegram Movie Bot Webhook Handler
------------------------------------------------------------------
This replaces polling with a webhook: Telegram sends each incoming
message as an HTTP POST to this function's URL. Vercel spins the
function up, it processes the message, replies via Telegram's API,
and shuts down. No long-running process needed - perfect for Vercel.

ENV VARS (set these in Vercel dashboard -> Project -> Settings -> Environment Variables):
  TELEGRAM_BOT_TOKEN   - from @BotFather
  TMDB_API_KEY         - from themoviedb.org
  SITE_BASE_URL        - e.g. https://yoursite.com/movie
"""

import os
import json
import requests
from http.server import BaseHTTPRequestHandler

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://yoursite.com/movie")

# Supabase (used for logging bot usage -> powers the analytics dashboard)
SUPABASE_URL = os.environ.get("SUPABASE_URL")            # e.g. https://xxxx.supabase.co
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")  # service_role key (secret!)

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def log_event(user_id, username, event_type, query=None, movie_title=None):
    """Fire-and-forget log of a bot interaction, for the analytics dashboard.
    Never raises - a logging failure should never break the bot itself."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return
    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/bot_events",
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "user_id": user_id,
                "username": username,
                "event_type": event_type,
                "query": query,
                "movie_title": movie_title,
            },
            timeout=5,
        )
    except Exception as e:
        print(f"log_event failed: {e}")
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_DETAILS_URL = "https://api.themoviedb.org/3/movie/{}"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


def send_message(chat_id, text):
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        timeout=10,
    )


def send_photo_with_button(chat_id, photo_url, caption, button_text, button_url):
    keyboard = {"inline_keyboard": [[{"text": button_text, "url": button_url}]]}
    requests.post(
        f"{TELEGRAM_API}/sendPhoto",
        json={
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": "Markdown",
            "reply_markup": keyboard,
        },
        timeout=10,
    )


def send_text_with_button(chat_id, text, button_text, button_url):
    keyboard = {"inline_keyboard": [[{"text": button_text, "url": button_url}]]}
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": keyboard,
        },
        timeout=10,
    )


def reply_with_movie(chat_id, tmdb_id, user_id=None, username=None, search_query=None):
    resp = requests.get(
        TMDB_DETAILS_URL.format(tmdb_id),
        params={"api_key": TMDB_API_KEY},
        timeout=10,
    )
    if resp.status_code != 200:
        send_message(chat_id, f"❌ Couldn't find a movie with TMDB ID {tmdb_id}.")
        return

    movie = resp.json()
    title = movie.get("title", "Unknown Title")
    year = (movie.get("release_date") or "----")[:4]
    rating = movie.get("vote_average", "N/A")
    overview = movie.get("overview", "No description available.")
    poster_path = movie.get("poster_path")

    watch_url = f"{SITE_BASE_URL}/{tmdb_id}"
    caption = f"🎬 *{title}* ({year})\n⭐ Rating: {rating}/10\n\n{overview}"

    if poster_path:
        poster_url = f"{TMDB_IMAGE_BASE}{poster_path}"
        send_photo_with_button(chat_id, poster_url, caption, "▶️ Watch Now", watch_url)
    else:
        send_text_with_button(chat_id, caption, "▶️ Watch Now", watch_url)

    # Log this as a "watch_click" since we generated a Watch Now link for the user.
    log_event(user_id or chat_id, username, "watch_click", query=search_query, movie_title=title)


def handle_search(chat_id, query, user_id=None, username=None):
    log_event(user_id or chat_id, username, "search", query=query)

    resp = requests.get(
        TMDB_SEARCH_URL,
        params={"api_key": TMDB_API_KEY, "query": query, "include_adult": False},
        timeout=10,
    )
    if resp.status_code != 200:
        send_message(chat_id, "⚠️ Sorry, couldn't reach TMDB right now. Try again later.")
        return

    results = resp.json().get("results", [])
    if not results:
        send_message(chat_id, f"❌ No movie found for '{query}'. Try a different spelling.")
        return

    top_match = results[0]
    reply_with_movie(chat_id, top_match["id"], user_id=user_id, username=username, search_query=query)


def process_update(update: dict):
    message = update.get("message")
    if not message:
        return

    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    from_user = message.get("from", {})
    user_id = from_user.get("id", chat_id)
    username = from_user.get("username") or from_user.get("first_name")

    if not text:
        return

    if text.startswith("/start"):
        log_event(user_id, username, "start")
        send_message(
            chat_id,
            "👋 Welcome to XilfFlix Movie Bot!\n\n"
            "Simply send me the name of any movie (add the year for best "
            "results, e.g. \"Dune 2021\"), and I'll find the details and a "
            "direct link to watch it on XilfFlix! 🎬🍿",
        )
    elif text.startswith("/id"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_message(chat_id, "Usage: /id <tmdb_id>\nExample: /id 27205")
            return
        reply_with_movie(chat_id, parts[1].strip(), user_id=user_id, username=username)
    else:
        handle_search(chat_id, text, user_id=user_id, username=username)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            update = json.loads(body)
            process_update(update)
        except Exception as e:
            print(f"Error processing update: {e}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode())

    def do_GET(self):
        # Simple health check endpoint
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "Movie bot webhook is live"}).encode())