from slack_sdk import WebClient 
from slack_sdk.errors import SlackApiError
import json
import datetime
import requests
import os
import logging
from dotenv import load_dotenv

logging.basicConfig(
    filename="reset.log",
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s'
)

load_dotenv()
BOT_USER = "U09BZRB5LMQ"
TOKEN = os.getenv("SLACK_TOKEN_25_26")

def reset_info():
	info = {"start": datetime.datetime.now().timestamp()}
	with open("info.json","w") as f:
		json.dump(info,f)

def fix(img_path):
	from PIL import Image, ImageDraw

	# Load the PNG image
	input_image = Image.open(img_path)

	# Create a mask image for the circular crop
	mask = Image.new('L', input_image.size, 0)
	draw = ImageDraw.Draw(mask)
	width, height = input_image.size
	radius = min(width, height) // 2
	center = (width // 2, height // 2)
	draw.ellipse((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), fill=255)

	# Apply the circular mask to the input image
	output_image = Image.new('RGBA', input_image.size)
	output_image.paste(input_image, mask=mask)

	output_image.save(img_path, 'PNG')

def get_people(channel_id):
	client = WebClient(token=TOKEN)

	if not os.path.isdir("profiles"):
		os.makedirs("profiles")

	try:
		ppl = client.conversations_members(channel=channel_id)
		people = {}
		for u in ppl["members"]:
			if u == BOT_USER:
				continue

			response = client.users_info(user=u)
			people[response['user']['id']] = response['user']['real_name']
			url = (response['user']['profile']['image_512'])
			r = requests.get(url)
			path = os.path.join("profiles", f"{response["user"]["id"]}.png")
			with open(path, 'wb') as file:
				file.write(r.content)
			fix(path)

		with open("people.json", "w") as f:
			json.dump(people, f)
		
	except SlackApiError as e:
		print(f"Error: {e}")
		logging.error(f"Slack API error: {e}")

if __name__ == '__main__':
	get_people(os.getenv("WORKOUTS"))
	reset_info()