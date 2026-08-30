import os
import requests
from datetime import datetime, timedelta

def main():
    # Attempt to read from environment variables, or prompt user if not set
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_ANON_KEY")

    if not supabase_url:
        supabase_url = input("Enter your SUPABASE_URL: ").strip()
    if not supabase_key:
        supabase_key = input("Enter your SUPABASE_ANON_KEY: ").strip()

    if not supabase_url or not supabase_key:
        print("Error: Supabase URL and Key are required.")
        return

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    url = f"{supabase_url.rstrip('/')}/rest/v1/bot_events"

    print("Fetching analytics data from Supabase...")
    try:
        # Fetch all events (in a production scenario with millions of rows, 
        # you would want to use pagination or Supabase Edge Functions/Postgres aggregations)
        response = requests.get(url, headers=headers, params={"select": "*"}, timeout=15)
        response.raise_for_status()
        events = response.json()
    except Exception as e:
        print(f"Failed to fetch data: {e}")
        return

    if not events:
        print("\nNo events found yet. Have you run the SQL script to create the table and triggered some bot events?")
        return

    # Basic Analytics
    unique_users = set()
    total_searches = 0
    movie_searches = {}
    
    # Calculate daily active users for the last 7 days
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)
    dau_map = {}

    for event in events:
        user_id = event.get("user_id")
        event_type = event.get("event_type")
        query = event.get("query")
        movie_title = event.get("movie_title")
        timestamp_str = event.get("timestamp")
        
        if user_id:
            unique_users.add(user_id)
            
        if event_type == "search":
            total_searches += 1
            
        if movie_title:
            movie_searches[movie_title] = movie_searches.get(movie_title, 0) + 1
            
        if timestamp_str:
            # Parse ISO timestamp (e.g. 2026-08-30T10:00:00.000Z or similar)
            try:
                # Handle standard ISO8601 strings
                ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                # Remove timezone info for simple date comparison
                ts = ts.replace(tzinfo=None)
                if ts >= seven_days_ago:
                    day_str = ts.strftime("%Y-%m-%d")
                    if day_str not in dau_map:
                        dau_map[day_str] = set()
                    dau_map[day_str].add(user_id)
            except ValueError:
                pass

    # Print Analytics
    print("\n" + "="*40)
    print(" TELEGRAM BOT ANALYTICS DASHBOARD")
    print("="*40)
    print(f"Total Unique Users (All Time): {len(unique_users)}")
    print(f"Total Searches Made:           {total_searches}")
    
    print("\n--- Daily Active Users (Last 7 Days) ---")
    if not dau_map:
        print("  No activity in the last 7 days.")
    else:
        for day in sorted(dau_map.keys()):
            print(f"  {day}: {len(dau_map[day])} users")

    print("\n--- Top 10 Most Interacted Movies ---")
    sorted_movies = sorted(movie_searches.items(), key=lambda x: x[1], reverse=True)
    if not sorted_movies:
        print("  No movies interacted with yet.")
    else:
        for title, count in sorted_movies[:10]:
            print(f"  [{count} clicks/views] {title}")

    print("="*40 + "\n")

if __name__ == "__main__":
    main()
