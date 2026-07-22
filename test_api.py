import urllib.request
import json
from urllib.error import HTTPError

data = {
    "date": "2026-07-23",
    "time": "11:00",
    "client_name": "Тест",
    "client_phone": "+7 (900) 000-00-00"
}

req = urllib.request.Request(
    'http://localhost:8001/api/public/book',
    data=json.dumps(data).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)

try:
    res = urllib.request.urlopen(req)
    print(res.read().decode())
except HTTPError as e:
    print(e.read().decode())
