import json, re
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
matplotlib.use('Agg')
from PIL import Image
import numpy as np
import time
import datetime
from zoneinfo import ZoneInfo 
import os
from reset import get_people
import logging

logging.basicConfig(
    filename="slack_bot.log",
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s'
)

# TOKEN = os.getenv("SLACK_TOKEN_25_26")
# # TOKEN = os.getenv("SLACK_TOKEN")
# WORKOUT_CHANNEL = os.getenv("WORKOUTS")
# # WORKOUT_CHANNEL = os.getenv("TESTING")
# CAPTAINS_CHANNEL = os.getenv("CAPTAINS")

# TEAM_TZ = ZoneInfo("America/New_York")

class Leaderboard:

	def __init__(self, bot_token, workout_channel, captains_channel, timezone):
		self.token = bot_token
		self.workout_channel = workout_channel
		self.captains_channel = captains_channel
		self.timezone = timezone

	def parse_message(self, msg, start_time, end_time=None):
		if end_time != None and end_time < float(msg['ts']):
			return [],0,0
		if start_time > float(msg['ts']):
			return [],0,0
		if 'user' not in msg.keys():
			return [],0,0
		txt = msg["text"]
		people = [msg['user']] + re.findall("<@([^>]+)>", txt)
		throw = sum([int(x) for x in re.findall("!throw ([0-9]+)", txt)])
		gym = len(re.findall("!gym", txt))+len(re.findall("!cardio", txt))+1.5*len(re.findall("!workout", txt))
		gym += .5*len(re.findall("!upper", txt))+.5*len(re.findall("!recovery", txt))
		lift = 1.5*len(re.findall("!lift", txt))
		return people, throw, gym, lift

	def get_progress(self, leaderboard, users, goal=4, metric=None, isWeekly=False, cap=False): # Weekly goal is 4 "points" if 60mins throwing is 2pts
		total = 0.0
		for u in leaderboard:
			gym_pts = leaderboard[u]["gym"]
			lift_pts = leaderboard[u]["lift"]
			throw_pts = leaderboard[u]["throw"] * 2 / 60  # normalize throwing

			if metric == "gym":
				contrib = gym_pts
				if cap:
					contrib = min(contrib, 2)
			elif metric == "throw":
				contrib = throw_pts
				if cap:
					contrib = min(contrib, 2)
			elif metric == "lift":
				contrib = lift_pts
				if cap:
					contrib = min(contrib, 1.5)
			else:  # combined metric
				contrib = gym_pts + throw_pts
				if cap:
					contrib = min(contrib, 6)

			total += contrib

		goal = len(users) * goal

		progress = total / goal if goal > 0 else 0

		MAX_PROG = 1
		if not isWeekly:
			MAX_PROG = 1.25

		cmap = mcolors.LinearSegmentedColormap.from_list(
		"progress_cmap",
			[(0.0, "red"),    
			(0.4, "red"),    
			(0.8, "yellow"), 
			(1.0, "green")])   # ends green
		norm = mcolors.Normalize(vmin=0, vmax=MAX_PROG)

		fig, ax = plt.subplots(figsize=(6, 2), dpi=200, layout='tight')
		grad = np.linspace(0, MAX_PROG, 256).reshape(1, -1)
		ax.imshow(
			grad,
			extent=[0, MAX_PROG, -0.2, 0.2], 
			aspect="auto",
			cmap=cmap,
			norm=norm
		)

		ax.barh([0], [MAX_PROG], color="none", edgecolor="black", height=0.4)
		ax.barh([0], [MAX_PROG - progress], left=progress, color="lightgray", height=0.4)

		ax.set_xlim(0, MAX_PROG)
		ax.set_yticks([])
		xticks = np.linspace(0, MAX_PROG, 6)  # 6 ticks between 0 and 1.25
		ax.set_xticks(xticks)
		ax.set_xticklabels([f"{int(x*100)}%" for x in xticks])

		title = ""
		if not isWeekly:
			title += "Semester"
		else:
			title += "Weekly"

		metric_title = ""
		if metric == 'gym' or metric == 'lift':
			metric_title = "Gym"
		elif metric == 'throw':
			metric_title = "Throwing"
		else:
			metric_title = "Throwing/Workout"
			
		ax.set_title(f"Team {title} {metric_title} Progress", fontsize=10)
		ax.text(0.5, 0.7, f"{total * 100 / goal} / 100", ha="center", va="bottom", fontsize=9)

		plt.tight_layout()
		fig.savefig("progress.jpg")
		plt.close(fig)

		return f"*Team {title} Progress:* {int(progress*100)}% of goal reached"

	def get_metrics(self, users, info=None, start_time=None, end_time=None, metrics=None, combine_gym=False):
		leaderboard = {x: {"throw": 0, "gym": 0, "lift": 0} for x in users.keys()}
		data = pd.read_csv("messages.csv").to_dict('records')

		if start_time == None:
			now = datetime.datetime.now(self.timezone)
			start_time = (now - datetime.timedelta(days=(now.weekday()))).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
			
		for m in data:
			try:
				if info:
					people,t,g,l = self.parse_message(m, info['start'])
				else:
					people,t,g,l = self.parse_message(m, start_time, end_time)

				for p in people:
					if metrics == 'throw' or metrics is None:
						leaderboard[p]['throw'] += t
						
					if metrics == 'gym' or metrics is None:
						leaderboard[p]['gym'] += g

					if metrics == 'lift' or metrics is None:
						leaderboard[p]['lift'] += l
					
					if combine_gym:
						leaderboard[p]['gym'] += l

			except Exception as e:
				logging.info(f"Invalid message {m} - {e}")

		return leaderboard

	def display(self, leaderboard, users, typ=0):
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
			get_people(self.workout_channel)

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

	def post_message(self, message, channel, thread=False, img=None):
		client = WebClient(token=self.bot_token)
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

	def post_throwers(self, leaderboard, users, channel):
		df = pd.DataFrame.from_dict(leaderboard, orient='index').reset_index().rename(columns={'index': 'id'})
		df['name'] = df.apply(lambda x: users[x['id']], axis=1)
		df = df.sort_values("throw", ascending=False)

		complete_throwers = len(df[df['throw']>=60].index)
		best = df.iloc[0]['id']
		best_mins = df.iloc[0]['throw']
		s1 = f"*Weekly Update!*\nOverall Progress: {complete_throwers}/{len(df.index)} reached 60 minutes\n{df['throw'].sum()} total minutes of throwing\n"
		s1 += f":star2: thrower: <@{best}> with {best_mins} minutes\n"
		s1 += self.get_progress(leaderboard, users, goal=2, metric='throw', isWeekly=True, cap=True) # 2 pts is 60 mins

		s2 = "*Under 60 minutes:*"
		for i,row in df[df['throw']<60].iterrows():
			s2 += f"\n<@{row['id']}> - {60-row['throw']} minutes left"

		time.sleep(4)
		self.post_message(s1, channel, False, "progress.jpg")
		time.sleep(4)
		self.post_message(s2, channel, True)

	def post_lifters(self, leaderboard, users, channel):
		df = pd.DataFrame.from_dict(leaderboard, orient='index').reset_index().rename(columns={'index': 'id'})
		df['name'] = df.apply(lambda x: users[x['id']], axis=1)
		df = df.sort_values("lift", ascending=False)

		complete_lifters = len(df[df['lift']>=1.5].index)
		s1 = f"*Weekly Update!*\nOverall Progress: {complete_lifters}/{len(df.index)} reached one lift\n{df['lift'].sum()} points of lifts\n"
		s1 += self.get_progress(leaderboard, users, goal=1.5, metric='lift', isWeekly=True, cap=True)

		s2 = "*Under one lift:*"
		for i,row in df[df['lift']<1.5].iterrows():
			s2 += f"\n<@{row['id']}>"

		time.sleep(4)
		self.post_message(s1, channel, False, "progress.jpg")
		time.sleep(4)
		self.post_message(s2, channel, True)

	def report_captains(self, channel):
		if not os.path.exists("people.json"):
			get_people(self.workout_channel)

		with open("people.json", "r") as f:
			users = json.load(f)
			
		now = datetime.datetime.now(self.timezone) - datetime.timedelta(days=4)
		start_time = (now - datetime.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
		end_time = (start_time + datetime.timedelta(days=7) - datetime.timedelta(microseconds=1))

		leaderboard = self.get_metrics(users, start_time=start_time.timestamp(), end_time=end_time.timestamp(), metrics='throw')
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

		self.post_message(s1, channel)
		time.sleep(4)
		self.post_message(s2, channel, True)
		time.sleep(4)

		leaderboard = self.get_metrics(users, start_time=start_time.timestamp(), end_time=end_time.timestamp(), metrics='lift')
		df = pd.DataFrame.from_dict(leaderboard, orient='index').reset_index().rename(columns={'index': 'id'})

		s1 = f"Throwers under one lift the week of {start_time.strftime('%m/%d')}-{end_time.strftime('%m/%d')}"
		if len(df[df['lift']<1.5].index) == 0:
			s2 = "None!"
		else:
			s2 = ""
			j = True
			for i,row in df[df['lift']<1.5].iterrows():
				if j:
					s2 += f"*{users[row['id']]}* - {row['lift']} lift points"
					j = False
				else:
					s2 += f"\n*{users[row['id']]}* - {row['lift']} lift points"

		self.post_message(s1, channel)
		time.sleep(4)
		self.post_message(s2, channel, True)

	def display_leaderboard(self, channel):
		if not os.path.exists("people.json"):
			get_people(self.workout_channel)
		with open("people.json", "r") as f:
			users = json.load(f)
		with open("info.json", "r") as f:
			info = json.load(f)

		l = self.get_metrics(users, info, combine_gym=True)
		s1 = self.display(l, users, 0)
		s2 = self.display(l, users, 1)
		self.post_message("*Leaderboard Update*", channel, False, "plot.jpg")
		time.sleep(4)
		self.post_message(s1, channel, True)
		self.post_message(s2, channel, True)
		time.sleep(4)
		self.post_message(self.get_progress(l, users, goal=13*4), channel, True, "progress.jpg") # 13 weeks of 4 pts as goal

	def remind_users(self, channel, metric):
		if not os.path.exists("people.json"):
			get_people(self.workout_channel)

		with open("people.json", "r") as f:
			users = json.load(f)
		
		now = datetime.datetime.now(self.timezone)
		start_time = (now - datetime.timedelta(days=(now.weekday()))).replace(hour=0, minute=0, second=0, microsecond=0)
		end_time = start_time + datetime.timedelta(days=7) - datetime.timedelta(microseconds=1)

		if metric == 'throw':
			l = self.get_metrics(users, start_time=start_time.timestamp(), end_time=end_time.timestamp(), metrics='throw')
			self.post_throwers(l, users, channel)
		elif metric =='lift':
			l = self.get_metrics(users, start_time=start_time.timestamp(), end_time=end_time.timestamp(), metrics='lift')
			self.post_lifters(l, users, channel)
