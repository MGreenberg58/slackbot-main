from datetime import datetime, timedelta
from zoneinfo import ZoneInfo 

TEAM_TZ = ZoneInfo("America/New_York")

print(datetime.datetime.now())
print(datetime.datetime.now(TEAM_TZ))