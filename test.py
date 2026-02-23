from datetime import datetime, timedelta

today = datetime.today()

# Tuesday = 1 (Monday=0)
days_ahead = 1 - today.weekday()

if days_ahead < 0:
    days_ahead += 7

next_tuesday = today + timedelta(days=days_ahead)

expiry = next_tuesday.strftime("%d%b%Y").upper()

print(expiry)