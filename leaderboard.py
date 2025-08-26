import json, re
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import time
import datetime
import os
from reset import get_people
import logging

logging.basicConfig(
    filename="slack_bot.log",
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s'
)

def parse_message(msg, start_time, end_time=None):
	if end_time != None and end_time < float(msg['ts']):
		return [],0,0
	if start_time > float(msg['ts']):
		return [],0,0
	if 'user' not in msg.keys():
		return [],0,0
	txt = msg["text"]
	people = [msg['user']] + re.findall("<@([^>]+)>", txt)
	throw = sum([int(x) for x in re.findall("!throw ([0-9]+)", txt)])
	workout = len(re.findall("!gym", txt))+len(re.findall("!cardio", txt))+1.5*len(re.findall("!workout", txt))
	workout += 1.5*len(re.findall("!lift", txt))+.5*len(re.findall("!upper", txt))+.5*len(re.findall("!recovery", txt))
	return people, throw, workout

def make_leaderboard(users, info):
	leaderboard = {x: {"throw": 0, "gym": 0} for x in users.keys()}
	data = pd.read_csv("messages.csv").to_dict('records')

	for m in data:
		try:
			people,t,w = parse_message(m, info['start'])
			for p in people:
				leaderboard[p]['throw'] += t
				leaderboard[p]['gym'] += w
		except:
			print(m)
			logging.info(f"Invalid message {m}")
	return leaderboard

def get_throwing(users, start_time=None, end_time=None):
	leaderboard = {x: {"throw": 0, "gym": 0} for x in users.keys()}
	data = pd.read_csv("messages.csv").to_dict('records')
	if start_time == None:
		now = datetime.datetime.now()
		start_time = (now - datetime.timedelta(days=(now.weekday()))).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
	for m in data:
		try:
			people,t,w = parse_message(m, start_time, end_time)
			for p in people:
				leaderboard[p]['throw'] += t
		except:
			print(m)
			logging.info(f"Invalid message {m}")
	return leaderboard

def display(leaderboard, users, typ=0):
	df = pd.DataFrame.from_dict(leaderboard, orient='index').reset_index().rename(columns={'index': 'id'})
	df['name'] = df.apply(lambda x: users[x['id']], axis=1)

	plt.style.use("fivethirtyeight")
	fig, ax = plt.subplots(dpi=400)

	ax.set_aspect('auto')
	ax.set_xlim(0-df['gym'].max()*.1, df['gym'].max()*1.1)
	ax.set_ylim(0-df['throw'].max()*.1, df['throw'].max()*1.1)
	ax.set_xlabel("Workout Points")
	ax.set_ylabel("Throwing Minutes")

	width = ax.get_xlim()[1]-ax.get_xlim()[0]
	height = ax.get_ylim()[1]-ax.get_ylim()[0]

	if not os.path.isdir("profiles"):
		get_people(os.getenv("TESTING"))

	for i,row in df.iterrows():
		x = row['gym']
		y = row['throw']
		try:
			path = os.path.join("profiles", f"{row['id']}.png")
			img = Image.open(path)
			size = .04
			ax.imshow(img, extent=[x - width*size, x + width*size, y - height*size, y + height*size], zorder=2)
		except:
			logging.info("Leaderboard Creation Failed")
			
	ax.set_aspect('auto')
	plt.tight_layout()
	fig.savefig("plot.jpg")

	text =f'*Full {["Throwing", "Workout"][typ]} Leaderboard*\n'
	
	i = 0
	key = ['throw','gym'][typ]
	df = df.sort_values(key,ascending=False)
	for ind,row in df.iterrows():
		if row[key] > 0:
			i += 1
			if typ == 0:
				text += f"*{i}. {row['name']}* with {row['throw']} minutes\n"
			else:
				text += f"*{i}. {row['name']}* with {row['gym']} points\n"

	return text

def post_message(message, channel, thread=False, img=None):
	client = WebClient(token=os.getenv("SLACK_TOKEN"))
	try:
		if thread:
			response = client.conversations_history(channel=channel,limit=1)
			client.chat_postMessage(channel=channel, text=message, thread_ts=response['messages'][0]['ts'])
		elif img!=None:
			client.files_upload_v2(
          	channel=channel,
			initial_comment=message,
	 	 	file="plot.jpg",
    	)
		else:
			client.chat_postMessage(channel=channel, text=message)
	except SlackApiError as e:
		print(f"Error: {e}")
		logging.info(f"Slack Error {e}")

def post_throwers(leaderboard, users, channel):

	df = pd.DataFrame.from_dict(leaderboard, orient='index').reset_index().rename(columns={'index': 'id'})
	df['name'] = df.apply(lambda x: users[x['id']], axis=1)
	df = df.sort_values("throw", ascending=False)

	a = len(df[df['throw']>=60].index)
	b = df.iloc[0]['id']
	c = df.iloc[0]['throw']
	s1 = f"*Weekly Throwing Update - 1 day left!*\nOverall Progress: {a}/{len(df.index)} reached 60 minutes\n{df['throw'].sum()} total minutes of throwing\n"
	s1 += f":star2: thrower: <@{b}> with {c} minutes"

	s2 = "*Under 60 minutes:*"
	for i,row in df[df['throw']<60].iterrows():
		s2 += f"\n<@{row['id']}> - {60-row['throw']} minutes left"

	post_message(s1, channel)
	time.sleep(4)
	post_message(s2, channel, True)

def report_captains(channel):
	if not os.path.exists("people.json"):
		get_people(os.getenv("TESTING"))

	with open("people.json", "r") as f:
		users = json.load(f)
	now = datetime.datetime.now()-datetime.timedelta(days=4)
	start_time = (now - datetime.timedelta(days=(now.weekday()))).replace(hour=0, minute=0, second=0, microsecond=0)
	end_time = (start_time+datetime.timedelta(days=7)-datetime.timedelta(microseconds=1))
	leaderboard = get_throwing(users, start_time.timestamp(), end_time.timestamp())

	df = pd.DataFrame.from_dict(leaderboard, orient='index').reset_index().rename(columns={'index': 'id'})

	s1 = f"Throwers under 60 minutes the week of {start_time.strftime('%m/%d')}-{end_time.strftime('%m/%d')}"
	if len(df[df['throw']<60].index) == 0:
		s2 = "None!"
	else:
		s2 = ""
		j = True
		for i,row in df[df['throw']<60].iterrows():
			if j:
				s2 += f"*{users[row['id']]}* - {row['throw']} minutes thrown"
				j = False
			else:
				s2 += f"\n*{users[row['id']]}* - {row['throw']} minutes thrown"
	post_message(s1, channel)
	time.sleep(4)
	post_message(s2, channel, True)

def display_leaderboard(channel):
	if not os.path.exists("people.json"):
		get_people(os.getenv("TESTING"))
	with open("people.json", "r") as f:
		users = json.load(f)

	with open("info.json", "r") as f:
		info = json.load(f)

	l = make_leaderboard(users, info)
	s1 = display(l, users, 0)
	s2 = display(l, users, 1)
	post_message("Leaderboard Update", channel, False, "plot.jpg")
	time.sleep(4)
	post_message(s1, channel, True)
	post_message(s2, channel, True)

def remind_throwers(channel):
	if not os.path.exists("people.json"):
		get_people(os.getenv("TESTING"))
	with open("people.json", "r") as f:
		users = json.load(f)
	l = get_throwing(users)
	post_throwers(l, users, channel)

if __name__ == '__main__':
	display_leaderboard(os.getenv("TESTING"))
	remind_throwers(os.getenv("TESTING"))
	report_captains(os.getenv("TESTING"))
	pass