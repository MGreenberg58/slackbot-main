# app.py
import os
from zoneinfo import ZoneInfo
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from bot import Bot, Leaderboard 

SLACK_BOT_TOKEN = os.getenv("SLACK_TOKEN_25_26")      
SLACK_APP_TOKEN = os.getenv("APP_TOKEN")      
WORKOUT_CHANNEL = os.getenv("WORKOUT_CHANNEL")       
CAPTAINS_CHANNEL = os.getenv("CAPTAINS_CHANNEL")   
TEAM_TZ = ZoneInfo("America/New_York")


slack_app = App(token=SLACK_BOT_TOKEN)
bot = Bot(SLACK_BOT_TOKEN, TEAM_TZ)
leaderboard = Leaderboard(SLACK_BOT_TOKEN, WORKOUT_CHANNEL, CAPTAINS_CHANNEL, TEAM_TZ)

@slack_app.command("/getleaderboard")
def get_leaderboard(ack, body, say, client):
    ack() 

    user_id = body["user_id"]
    channel_id = body["channel_id"]

    if channel_id.startswith("D") or channel_id == CAPTAINS_CHANNEL:
        try:
            leaderboard.display_leaderboard(channel_id)
            say(f"<@{user_id}>, leaderboard displayed ✅")
        except Exception as e:
            say(f"⚠️ Error displaying leaderboard: `{e}`")
    else:
        say(f"⚠️ This command only works in DMs")

@slack_app.command("/getrequirements")
def get_leaderboard(ack, body, say, client):
    ack() 

    user_id = body["user_id"]
    channel_id = body["channel_id"]

    if channel_id.startswith("D") or channel_id == CAPTAINS_CHANNEL:
        try:
            leaderboard.remind_users(channel_id, 'throw')
            leaderboard.remind_users(channel_id, 'lift')
            say(f"<@{user_id}>, requirements displayed ✅")
        except Exception as e:
            say(f"⚠️ Error displaying leaderboard: `{e}`")
    else:
        say(f"⚠️ This command only works in DMs")

if __name__ == "__main__":
    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        raise RuntimeError("Missing Slack tokens. Set SLACK_BOT_TOKEN and SLACK_APP_TOKEN.")
    SocketModeHandler(slack_app, SLACK_APP_TOKEN).start()
