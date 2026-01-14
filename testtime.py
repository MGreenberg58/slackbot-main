from datetime import datetime, timedelta
from zoneinfo import ZoneInfo 

TEAM_TZ = ZoneInfo("America/New_York")

now = datetime.now()
start_time = (now - timedelta(days=(now.weekday()))).replace(hour=0, minute=0, second=0, microsecond=0)
end_time = start_time + timedelta(days=3) - timedelta(microseconds=1)
print(start_time.timestamp(), end_time.timestamp())

now = datetime.now(TEAM_TZ)
start_time = (now - timedelta(days=(now.weekday()))).replace(hour=0, minute=0, second=0, microsecond=0)
end_time = start_time - timedelta(days=3) - timedelta(microseconds=1)
print(start_time.timestamp(), end_time.timestamp())
