import logging

logging.basicConfig(
    filename="slack_bot.log",
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s'
)
logging.info("Slack bot started")

import os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import time
import datetime
from zoneinfo import ZoneInfo 
import pandas as pd
from leaderboard import Leaderboard

load_dotenv()

class Bot:

    def __init__(self, bot_token, timezone):
        self.TOKEN = bot_token
        self.TZ = timezone

    def get_selfies_messages(self, channel_id, days=7, limit=250, cursor=None):
        client = WebClient(token=self.TOKEN)
        try:
            start = (datetime.datetime.now(self.TZ) - datetime.timedelta(days=days)).timestamp()
            all_msgs = []
            response = client.conversations_history(
                cursor=cursor,
                oldest=start,
                limit=limit,
                channel=channel_id
            )
            count = 0
            for message in response['messages']:
                if 'thread_ts' in message:
                    count += 1
                    thread_response = client.conversations_replies(channel=channel_id, ts=message['thread_ts'])
                    for old in thread_response["messages"]:
                        if "user" in old:
                            all_msgs.append({"text": old['text'], "user": old['user'], "ts": old['ts'], "thread_ts": old['thread_ts']})
                elif "user" in message:
                    all_msgs.append({"text": message['text'], "user": message['user'], "ts": message['ts']})
            logging.info(f"{count} threads processed, {len(all_msgs)} messages retrieved")
            return pd.DataFrame(all_msgs, dtype=str), response
        except SlackApiError as e:
            logging.error(f"Slack API error: {e}")
            return pd.DataFrame(), {}

    def write(self, df2):
        file_path = os.path.join(os.getcwd(), "messages.csv")
        if os.path.exists(file_path):
            df1 = pd.read_csv(file_path, dtype=str)
        else:
            df1 = pd.DataFrame(columns=df2.columns)

        if df2.empty:
            logging.info("No new messages to write")
            df1.to_csv(file_path, index=False)
            return
        
        old_length = len(df1)
        df1 = df1[~df1['ts'].isin(df2['ts'])]
        df1 = pd.concat([df1, df2], ignore_index=True)
        df1 = df1.drop_duplicates(subset=["text","user","ts"])
        logging.info(f"{old_length} rows > {len(df1)} rows")
        df1.to_csv(file_path, index=False)

    def paginate(self, channel_id, days=90, limit=200):
        df, response = self.get_selfies_messages(channel_id, days, limit)
        
        while response.get('has_more'):
            time.sleep(60)
            df2, response = self.get_selfies_messages(channel_id, days, limit, response['response_metadata']['next_cursor'])
            df = pd.concat([df, df2], ignore_index=True)
                
        return df

if __name__ == "__main__":

    TOKEN = os.getenv("SLACK_TOKEN_25_26")
    # TOKEN = os.getenv("SLACK_TOKEN")
    WORKOUT_CHANNEL = os.getenv("WORKOUTS")
    # WORKOUT_CHANNEL = os.getenv("TESTING")
    CAPTAINS_CHANNEL = os.getenv("CAPTAINS")
    TEAM_TZ = ZoneInfo("America/New_York")

    if not TOKEN:
        raise ValueError("SLACK_TOKEN is missing!")
    if not WORKOUT_CHANNEL:
        raise ValueError("SLACK_CHANNEL_ID is missing!")
    
    bot = Bot(TOKEN, TEAM_TZ)
    leaderboard = Leaderboard(TOKEN, WORKOUT_CHANNEL, CAPTAINS_CHANNEL, TEAM_TZ)

    try:
        df = bot.paginate(WORKOUT_CHANNEL, 7)
        bot.write(df)
        weekday = datetime.datetime.today().weekday()
        if weekday == 5: # Saturday
            leaderboard.remind_users(WORKOUT_CHANNEL, 'throw')
            leaderboard.remind_users(WORKOUT_CHANNEL, 'lift')
        if weekday == 0: # Monday
            leaderboard.display_leaderboard(WORKOUT_CHANNEL)
            leaderboard.report_captains(CAPTAINS_CHANNEL)
        logging.info("Slack bot run completed successfully")
    except Exception as e:
        logging.error(f"Error running bot: {e}")
        raise
