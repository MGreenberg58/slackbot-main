from slack_sdk import WebClient 
from slack_sdk.errors import SlackApiError
import json
import datetime
import requests
import os

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
	client = WebClient(token=os.getenv("SLACK_TOKEN"))

	try:
		ppl = client.conversations_members(channel=channel_id)
		people = {}
		for u in ppl["members"]:
			response = client.users_info(user=u)
			people[response['user']['id']] = response['user']['real_name']
			url = (response['user']['profile']['image_512'])
			r = requests.get(url)
			with open(f'profiles/{response["user"]["id"]}.png', 'wb') as file:
				file.write(r.content)
			fix(f'profiles/{response["user"]["id"]}.png')


		with open("people.json", "w") as f:
			json.dump(people, f)
		
	
	except SlackApiError as e:
		print(f"Error: {e}")


if __name__ == '__main__':
	get_people(os.getenv("TESTING"))
	reset_info()