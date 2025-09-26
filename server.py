# server.py (Final Version with Threading Fix)

import asyncio
import websockets
import json
import time
import os
import threading
from twitchio.ext import commands
from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# --- CONFIGURATION ---
TWITCH_OAUTH_TOKEN = "oauth:n25sw825eychrdh169jauitzkohrti" 
TWITCH_USERNAME = "mighty_bombjack"
TWITCH_CHANNEL = "mighty_bombjack"
TIKTOK_USERNAME = "@kcnaynayx" # Your TikTok username
YOUTUBE_VIDEO_ID = "BNqxi9VApnQ" # Get this from the URL of your live stream after the ?v= whatever shit


# --- WebSocket Server ---
CONNECTED_CLIENTS = set()

async def client_handler(websocket):
    CONNECTED_CLIENTS.add(websocket)
    print(f"New client connected. Total clients: {len(CONNECTED_CLIENTS)}")
    try:
        welcome_message = { "platform": "System", "author": "Headsup", "message": "Successfully connected to chat server!", "color": "#1E90FF" }
        await websocket.send(json.dumps(welcome_message))
        await websocket.wait_closed()
    finally:
        CONNECTED_CLIENTS.remove(websocket)
        print(f"Client disconnected. Total clients: {len(CONNECTED_CLIENTS)}")

async def broadcast_message(message_data):
    if CONNECTED_CLIENTS:
        payload = json.dumps(message_data)
        await asyncio.gather(*[client.send(payload) for client in CONNECTED_CLIENTS])

# --- Unified Message Handler ---
async def on_new_message(platform, author, message, color):
    print(f"[{platform}] {author}: {message}")
    await broadcast_message({ "platform": platform, "author": author, "message": message, "color": color })

# --- Twitch Bot ---
class TwitchBot(commands.Bot):
    def __init__(self):
        super().__init__(token=TWITCH_OAUTH_TOKEN, prefix='!', initial_channels=[TWITCH_CHANNEL])
    async def event_ready(self): print(f'Twitch bot ready as | {self.nick}')
    async def event_message(self, message):
        if message.echo: return
        await on_new_message("Twitch", message.author.name, message.content, "#9146FF")

# --- TikTok Client ---
tiktok_client = TikTokLiveClient(unique_id=TIKTOK_USERNAME)
@tiktok_client.on(CommentEvent)
async def on_tiktok_comment(event: CommentEvent):
    await on_new_message("TikTok", event.user.nickname, event.comment, "#00f2ea")

# --- YouTube Client ---
class YouTubeBot:
    # We now accept the asyncio 'loop' as an argument
    def __init__(self, video_id, loop):
        self.video_id = video_id
        self.loop = loop # Store the loop
        self.live_chat_id = None
        self.youtube_service = self._get_authenticated_service()
        self.processed_message_ids = set()

    def _get_authenticated_service(self):
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/youtube.readonly'])
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', ['https://www.googleapis.com/auth/youtube.readonly'])
                creds = flow.run_local_server(port=0)
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        return build('youtube', 'v3', credentials=creds)

    def _get_live_chat_id(self):
        try:
            request = self.youtube_service.videos().list(part="liveStreamingDetails", id=self.video_id)
            response = request.execute()
            if response['items']:
                self.live_chat_id = response['items'][0]['liveStreamingDetails']['activeLiveChatId']
            else:
                print("ERROR: Could not find YouTube video. Is the Video ID correct and is the stream live?")
        except Exception as e:
            print(f"ERROR getting YouTube chat ID: {e}")

    def poll_chat(self):
        if not self.live_chat_id: self._get_live_chat_id()
        if not self.live_chat_id: return
        
        while True:
            try:
                request = self.youtube_service.liveChatMessages().list(liveChatId=self.live_chat_id, part="snippet,authorDetails")
                response = request.execute()
                for item in response['items']:
                    if item['id'] not in self.processed_message_ids:
                        author = item['authorDetails']['displayName']
                        message = item['snippet']['displayMessage']
                        # Use the stored loop to safely call the async function from the thread
                        asyncio.run_coroutine_threadsafe(
                            on_new_message("YouTube", author, message, "#FF0000"), self.loop
                        )
                        self.processed_message_ids.add(item['id'])
                time.sleep(response.get('pollingIntervalMillis', 5000) / 1000)
            except Exception as e:
                print(f"An error occurred with YouTube polling: {e}")
                time.sleep(15)

# --- Main Application ---
async def main():
    server = await websockets.serve(client_handler, "localhost", 8765)
    print("WebSocket server started on ws://localhost:8765")
    
    twitch_bot = TwitchBot()
    
    # Get the current event loop before starting the thread
    loop = asyncio.get_running_loop()
    # Pass the loop to the YouTubeBot
    youtube_bot = YouTubeBot(YOUTUBE_VIDEO_ID, loop)
    youtube_thread = threading.Thread(target=youtube_bot.poll_chat, daemon=True)
    youtube_thread.start()
    
    await asyncio.gather(
        twitch_bot.start(),
        tiktok_client.start(),
        server.wait_closed()
    )

if __name__ == "__main__":
    print("Starting Headsup chat server...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server shutting down.")