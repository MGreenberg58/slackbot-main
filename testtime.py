from datetime import datetime, timedelta
from zoneinfo import ZoneInfo 

TEAM_TZ = ZoneInfo("America/New_York")

print(datetime.now().timestamp())
print(datetime.now(TEAM_TZ).timestamp())