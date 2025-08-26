import logging

logging.basicConfig(
    filename="slack_bot.log",
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s'
)
logging.info("Slack bot started")

import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import datetime, time
import pandas as pd
from leaderboard import display_leaderboard, remind_throwers, report_captains

TOKEN = os.getenv("SLACK_TOKEN")
CHANNEL = os.getenv("TESTING")

def get_selfies_messages(channel_id, days=7, limit=250, cursor=None):
    client = WebClient(token=TOKEN)
    try:
        start = (datetime.datetime.now()-datetime.timedelta(days=days)).timestamp()
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

def write(df2):
    file_path = os.path.join(os.getcwd(), "messages.csv")
    if os.path.exists(file_path):
        df1 = pd.read_csv(file_path, dtype=str)
    else:
        df1 = pd.DataFrame(columns=df2.columns)
    old_length = len(df1)
    df1 = df1[~df1['ts'].isin(df2['ts'])]
    df1 = pd.concat([df1, df2], ignore_index=True)
    df1 = df1.drop_duplicates(subset=["text","user","ts"])
    logging.info(f"{old_length} rows > {len(df1)} rows")
    df1.to_csv(file_path, index=False)

def paginate(channel_id, days=90, limit=200):
    df, response = get_selfies_messages(channel_id, days, limit)
    if response.get('has_more'):
        time.sleep(60)
    while response.get('has_more'):
        df2, response = get_selfies_messages(channel_id, days, limit, response['response_metadata']['next_cursor'])
        df = pd.concat([df, df2], ignore_index=True)
        if response.get('has_more'):
            time.sleep(60)
    return df

if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("SLACK_TOKEN is missing!")
    if not CHANNEL:
        raise ValueError("SLACK_CHANNEL_ID is missing!")

    try:
        df = paginate(CHANNEL, 7)
        write(df)
        weekday = datetime.datetime.today().weekday()
        # if weekday == 5:
        remind_throwers(CHANNEL)
        # if weekday == 0:
        display_leaderboard(CHANNEL)
        report_captains(CHANNEL)
        logging.info("Slack bot run completed successfully")
    except Exception as e:
        logging.error(f"Error running bot: {e}")
        raise
