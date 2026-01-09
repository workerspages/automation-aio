
import os
import sys
import requests

def check_env():
    print("--- Environment Check ---")
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    print(f"TELEGRAM_BOT_TOKEN: {'Set' if token else 'Missing'} ({token[:5]}... if set)")
    print(f"TELEGRAM_CHAT_ID: {'Set' if chat_id else 'Missing'}")
    
    return token, chat_id

def check_network(token, chat_id):
    if not token or not chat_id:
        print("Skipping network check due to missing credentials.")
        return

    print("\n--- Network Check ---")
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        print(f"Connecting to {url.replace(token, '***')}...")
        resp = requests.get(url, timeout=10)
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {resp.text}")
    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    token, chat_id = check_env()
    check_network(token, chat_id)
