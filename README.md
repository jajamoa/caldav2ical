# CalDAV → iCal Bridge

Convert any CalDAV calendar (Lark, Nextcloud, etc.) into a public iCal URL for Google Calendar, Apple Calendar, Outlook, and more.

## How it works

1. Enter your CalDAV server URL, username, and password
2. Get a unique iCal URL
3. Subscribe in Google Calendar (Other calendars → + → From URL)

## Deploy on Render

1. Fork this repo
2. Create a new Web Service on [render.com](https://render.com)
3. Connect your GitHub repo
4. Set build command: `pip install -r requirements.txt`
5. Set start command: `gunicorn app:app`
6. Deploy!

## Local development

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000
