import json, re
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from PIL import Image
import numpy as np
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

def get_progress(leaderboard, users, weekly_goal=4, metric=None, start=None): # Weekly goal is 4 "points" if 60mins throwing is 2pts
	total = 0
	if metric == 'throw' or metric is None:
		total += sum([leaderboard[u]['throw'] for u in leaderboard]) * 2 / 60 # Normalizing so that gym and throwing are scored 50/50 in progress
	if metric == 'gym' or metric is None:
		total += sum([leaderboard[u]['gym'] for u in leaderboard])

	goal = len(users) * weekly_goal

	progress = total / goal if goal > 0 else 0
	progress_clamped = min(progress, 1.0)

	cmap = mcolors.LinearSegmentedColormap.from_list(
        "progress_cmap", ["red", "yellow", "green"]
    )

	fig, ax = plt.subplots(figsize=(6, 2), dpi=200, layout='tight')
	grad = np.linspace(0, 1, 256).reshape(1, -1)
	ax.imshow(
        grad,
        extent=[0, progress_clamped, -0.2, 0.2],  # only fill up to progress
        aspect="auto",
        cmap=cmap
    )

	ax.imshow(grad, extent=[0, progress_clamped, -0.2, 0.2], aspect="auto", cmap=cmap)
	ax.barh([0], [progress_clamped], color="none", edgecolor="black", height=0.4)
	ax.barh([0], [1], color="lightgray", alpha=0.3, height=0.4)

	ax.set_xlim(0, 1)
	ax.set_yticks([])
	ax.set_xticks([0.5, 0.75, 1.0, 1.25])
	ax.set_xticklabels([f"{int(x*100)}%" for x in [0.5, 0.75, 1.0, 1.25]])

	title = ""
	if start is None:
		title += "Semester"
	else:
		title += "Weekly"
		
	ax.set_title(f"Team {title} Throwing/Workout Progress", fontsize=10)
	ax.text(0.5, 0.7, f"{total * 100 / goal} / 100", ha="center", va="bottom", fontsize=9)

	plt.tight_layout()
	fig.savefig("progress.jpg")
	plt.close(fig)

	return f"*Team {title} Progress:* {int(progress*100)}% of goal reached"

def get_metrics(users, cap=False, info=None, start_time=None, end_time=None, metrics=None):
	leaderboard = {x: {"throw": 0, "gym": 0} for x in users.keys()}
	data = pd.read_csv("messages.csv").to_dict('records')

	if start_time == None:
		now = datetime.datetime.now()
		start_time = (now - datetime.timedelta(days=(now.weekday()))).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
		
	for m in data:
		try:
			if info:
				people,t,w = parse_message(m, info['start'])
			else:
				people,t,w = parse_message(m, start_time, end_time)

			for p in people:
				if metrics == 'throw' or metrics is None:
					leaderboard[p]['throw'] += min(t, 60) if cap else t
				if metrics == 'gym' or metrics is None:
					leaderboard[p]['gym'] += min(w, 4.5) if cap else w
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
		response = client.conversations_history(channel=channel,limit=1)
		if img is not None:
			if thread:
				client.files_upload_v2(
				channel=channel,
				initial_comment=message,
				file=img,
				thread_ts=response['messages'][0]['ts'])
			else:
				client.files_upload_v2(
				channel=channel,
				initial_comment=message,
				file=img)

		if img is None and thread:
			client.chat_postMessage(channel=channel, text=message, thread_ts=response['messages'][0]['ts'])
		
		if img is None and not thread:
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
	s1 += f":star2: thrower: <@{b}> with {c} minutes\n"
	s1 += get_progress(leaderboard, users)

	s2 = "*Under 60 minutes:*"
	for i,row in df[df['throw']<60].iterrows():
		s2 += f"\n<@{row['id']}> - {60-row['throw']} minutes left"

	time.sleep(4)
	post_message(s1, channel, False, "progress.jpg")
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

	leaderboard = get_metrics(users, start_time.timestamp(), end_time.timestamp(), metrics='throw')

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

	l = get_metrics(users, info)
	s1 = display(l, users, 0)
	s2 = display(l, users, 1)
	post_message("*Leaderboard Update*", channel, False, "plot.jpg")
	time.sleep(4)
	post_message(s1, channel, True)
	post_message(s2, channel, True)
	time.sleep(4)
	post_message(get_progress(l, users), channel, True, "progress.jpg")

def remind_throwers(channel):
	if not os.path.exists("people.json"):
		get_people(os.getenv("TESTING"))

	with open("people.json", "r") as f:
		users = json.load(f)
	
	now = datetime.datetime.now()-datetime.timedelta(days=4)
	start_time = (now - datetime.timedelta(days=(now.weekday()))).replace(hour=0, minute=0, second=0, microsecond=0)
	end_time = (start_time+datetime.timedelta(days=7)-datetime.timedelta(microseconds=1))

	l = get_metrics(users, cap=True, start_time=start_time.timestamp(), end_time=end_time.timestamp(), metrics='throw')
	post_throwers(l, users, channel)
	

if __name__ == '__main__':
	display_leaderboard(os.getenv("TESTING"))
	remind_throwers(os.getenv("TESTING"))
	report_captains(os.getenv("TESTING"))
	pass