
from datetime import datetime, time, timezone
import pytz


ist = pytz.timezone("Asia/Kolkata")
current_time = datetime.now(ist).time()
print("current time: "+ str(current_time))