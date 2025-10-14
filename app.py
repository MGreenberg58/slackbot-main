from flask import Flask, request, jsonify
import os
from zoneinfo import ZoneInfo
from bot import Bot, Leaderboard

app = Flask(__name__)

TOKEN = os.getenv("SLACK_TOKEN")
WORKOUT_CHANNEL = os.getenv("TESTING")
CAPTAINS_CHANNEL = os.getenv("CAPTAINS")
TEAM_TZ = ZoneInfo("America/New_York")

# Instantiate objects once when the Flask app starts
bot = Bot(TOKEN, TEAM_TZ)
leaderboard = Leaderboard(TOKEN, WORKOUT_CHANNEL, CAPTAINS_CHANNEL, TEAM_TZ)

@app.route('/getLeaderboard', methods=['POST'])
def handle_slash_command():
    leaderboard.display_leaderboard(WORKOUT_CHANNEL)

if __name__ == '__main__':
    app.run(port=5000)
