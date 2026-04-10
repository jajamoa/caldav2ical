import os
import caldav
from flask import Flask, Response, render_template_string, request, abort
import hashlib
from datetime import datetime, timezone, timedelta

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CalDAV → iCal Bridge</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f7; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
  .card { background: white; border-radius: 16px; padding: 40px; max-width: 560px; width: 100%; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }
  h1 { font-size: 24px; font-weight: 700; margin-bottom: 8px; color: #1d1d1f; }
  .subtitle { color: #6e6e73; font-size: 14px; margin-bottom: 28px; line-height: 1.5; }
  label { display: block; font-size: 13px; font-weight: 600; color: #1d1d1f; margin-bottom: 6px; }
  input { width: 100%; padding: 10px 14px; border: 1.5px solid #d2d2d7; border-radius: 8px; font-size: 14px; outline: none; transition: border-color 0.2s; margin-bottom: 16px; }
  input:focus { border-color: #0071e3; }
  button { width: 100%; padding: 12px; background: #0071e3; color: white; border: none; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; transition: background 0.2s; }
  button:hover { background: #0077ed; }
  button:disabled { background: #a0c4f1; cursor: not-allowed; }

  /* Preview */
  .preview { margin-top: 24px; display: none; }
  .preview.show { display: block; }
  .preview h2 { font-size: 15px; font-weight: 600; color: #1d1d1f; margin-bottom: 12px; }
  .cal-name { font-size: 12px; font-weight: 600; color: #6e6e73; text-transform: uppercase; letter-spacing: 0.5px; margin: 16px 0 8px; }
  .event-list { list-style: none; }
  .event-item { padding: 10px 12px; border-radius: 8px; background: #f5f5f7; margin-bottom: 6px; font-size: 13px; }
  .event-title { font-weight: 600; color: #1d1d1f; }
  .event-time { color: #6e6e73; font-size: 12px; margin-top: 2px; }
  .no-events { font-size: 13px; color: #6e6e73; font-style: italic; }
  .confirm-btn { margin-top: 20px; background: #34c759; }
  .confirm-btn:hover { background: #30b350; }

  /* Result */
  .result { margin-top: 24px; display: none; }
  .result.show { display: block; }
  .result h2 { font-size: 15px; font-weight: 600; color: #1d1d1f; margin-bottom: 12px; }
  .url-box { display: flex; gap: 8px; }
  .url-box input { margin-bottom: 0; flex: 1; font-family: monospace; font-size: 12px; background: #f5f5f7; }
  .copy-btn { padding: 10px 16px; background: #34c759; color: white; border: none; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap; width: auto; }
  .copy-btn:hover { background: #30b350; }
  .hint { margin-top: 10px; font-size: 12px; color: #6e6e73; line-height: 1.5; }

  .error { color: #ff3b30; font-size: 13px; margin-top: 12px; display: none; }
  .error.show { display: block; }
  .divider { border: none; border-top: 1.5px solid #f0f0f0; margin: 24px 0; }
</style>
</head>
<body>
<div class="card">
  <h1>CalDAV → iCal Bridge</h1>
  <p class="subtitle">Connect your CalDAV calendar and get a shareable iCal URL for Google Calendar, Apple Calendar, and more.</p>

  <form id="form">
    <label>CalDAV Server URL</label>
    <input type="text" id="server" placeholder="e.g. https://caldav-jp.larksuite.com" required />
    <label>Username</label>
    <input type="text" id="username" placeholder="your CalDAV username" required />
    <label>Password / Token</label>
    <input type="password" id="password" placeholder="your CalDAV password or token" required />
    <button type="submit" id="connect-btn">Connect & Preview</button>
  </form>

  <div class="error" id="error"></div>

  <div class="preview" id="preview">
    <hr class="divider">
    <h2>📅 Found your calendars</h2>
    <div id="preview-content"></div>
    <button class="confirm-btn" onclick="generateUrl()">Generate iCal URL →</button>
  </div>

  <div class="result" id="result">
    <hr class="divider">
    <h2>✅ Your iCal URL</h2>
    <div class="url-box">
      <input type="text" id="ical-url" readonly />
      <button class="copy-btn" onclick="copyUrl()">Copy</button>
    </div>
    <p class="hint">
      <strong>Google Calendar:</strong> Other calendars → + → From URL → paste above.<br>
      Works with Apple Calendar, Outlook, and any app that supports iCal subscriptions.
    </p>
  </div>
</div>

<script>
let _previewToken = null;

document.getElementById('form').onsubmit = async (e) => {
  e.preventDefault();
  const btn = document.getElementById('connect-btn');
  btn.textContent = 'Connecting...';
  btn.disabled = true;
  document.getElementById('error').classList.remove('show');
  document.getElementById('preview').classList.remove('show');
  document.getElementById('result').classList.remove('show');

  const res = await fetch('/preview', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      server: document.getElementById('server').value.trim(),
      username: document.getElementById('username').value.trim(),
      password: document.getElementById('password').value.trim(),
    })
  });
  const data = await res.json();
  btn.textContent = 'Connect & Preview';
  btn.disabled = false;

  if (data.error) {
    document.getElementById('error').textContent = '❌ ' + data.error;
    document.getElementById('error').classList.add('show');
    return;
  }

  _previewToken = data.token;
  renderPreview(data.calendars);
  document.getElementById('preview').classList.add('show');
};

function renderPreview(calendars) {
  const container = document.getElementById('preview-content');
  let html = '';
  let total = 0;
  for (const cal of calendars) {
    html += `<div class="cal-name">📁 ${cal.name} (${cal.events.length} events)</div>`;
    if (cal.events.length === 0) {
      html += '<p class="no-events">No upcoming events</p>';
    } else {
      html += '<ul class="event-list">';
      for (const ev of cal.events.slice(0, 5)) {
        html += `<li class="event-item"><div class="event-title">${ev.title}</div><div class="event-time">${ev.time}</div></li>`;
      }
      if (cal.events.length > 5) {
        html += `<li class="event-item no-events">+ ${cal.events.length - 5} more events</li>`;
      }
      html += '</ul>';
      total += cal.events.length;
    }
  }
  html = `<p style="font-size:13px;color:#6e6e73;margin-bottom:12px;">Found <strong>${calendars.length}</strong> calendar(s) with <strong>${total}</strong> total events.</p>` + html;
  container.innerHTML = html;
}

async function generateUrl() {
  if (!_previewToken) return;
  const btn = document.querySelector('.confirm-btn');
  btn.textContent = 'Generating...';
  btn.disabled = true;

  const res = await fetch('/confirm', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ token: _previewToken })
  });
  const data = await res.json();
  btn.textContent = 'Generate iCal URL →';
  btn.disabled = false;

  if (data.error) {
    document.getElementById('error').textContent = '❌ ' + data.error;
    document.getElementById('error').classList.add('show');
    return;
  }

  document.getElementById('ical-url').value = data.url;
  document.getElementById('result').classList.add('show');
  document.getElementById('result').scrollIntoView({ behavior: 'smooth' });
}

function copyUrl() {
  const input = document.getElementById('ical-url');
  input.select();
  navigator.clipboard.writeText(input.value);
  const btn = document.querySelector('.copy-btn');
  btn.textContent = 'Copied!';
  setTimeout(() => btn.textContent = 'Copy', 2000);
}
</script>
</body>
</html>
"""

def make_token(server, username, password):
    raw = f"{server}|{username}|{password}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]

def parse_event(event_data):
    """Extract title and time from raw iCal event data."""
    title = "Untitled"
    time_str = ""
    dtstart = ""
    for line in event_data.splitlines():
        if line.startswith("SUMMARY:"):
            title = line[8:].strip()
        elif line.startswith("DTSTART"):
            dtstart = line.split(":")[-1].strip()
    if dtstart:
        try:
            if "T" in dtstart:
                dt = datetime.strptime(dtstart[:15], "%Y%m%dT%H%M%S")
                time_str = dt.strftime("%b %d, %Y %H:%M")
            else:
                dt = datetime.strptime(dtstart[:8], "%Y%m%d")
                time_str = dt.strftime("%b %d, %Y")
        except Exception:
            time_str = dtstart
    return {"title": title, "time": time_str}

# In-memory store: token -> (server, username, password)
_store = {}

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/preview', methods=['POST'])
def preview():
    data = request.json
    server = data.get('server', '').strip().rstrip('/')
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not all([server, username, password]):
        return {'error': 'All fields are required.'}, 400

    try:
        client = caldav.DAVClient(url=server, username=username, password=password, timeout=30)
        principal = client.principal()
        calendars = principal.calendars()
    except Exception as e:
        return {'error': f'Connection failed: {str(e)}'}, 400

    token = make_token(server, username, password)
    _store[token] = (server, username, password)

    # Fetch events from 1 year ago to 1 year ahead
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=30)
    end = now + timedelta(days=90)

    cal_preview = []
    for cal in calendars:
        try:
            cal_name = str(cal.name) if cal.name else "Calendar"
            # Try date-range search first, fall back to all events
            try:
                events = cal.date_search(start=start, end=end)
            except Exception:
                events = cal.events()
            parsed = [parse_event(ev.data) for ev in events[:50]]
            parsed = [p for p in parsed if p['title'] != 'Untitled' or p['time']]
            parsed.sort(key=lambda x: x['time'] or '')
            cal_preview.append({"name": cal_name, "events": parsed})
        except Exception as e:
            cal_preview.append({"name": "Calendar", "events": []})

    return {'token': token, 'calendars': cal_preview}

@app.route('/confirm', methods=['POST'])
def confirm():
    data = request.json
    token = data.get('token', '')
    if token not in _store:
        return {'error': 'Session expired, please reconnect.'}, 400
    host = request.host_url.rstrip('/')
    return {'url': f'{host}/ical/{token}'}

@app.route('/ical/<token>')
def serve_ical(token):
    if token not in _store:
        abort(404)

    server, username, password = _store[token]

    try:
        client = caldav.DAVClient(url=server, username=username, password=password, timeout=30)
        principal = client.principal()
        calendars = principal.calendars()

        lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//CalDAV2iCal Bridge//EN', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH']

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=365)
        end = now + timedelta(days=365)

        for cal in calendars:
            try:
                events = cal.date_search(start=start, end=end)
            except Exception:
                events = cal.events()
            for event in events:
                ical_data = event.data
                in_event = False
                for line in ical_data.splitlines():
                    if line.startswith('BEGIN:VEVENT'):
                        in_event = True
                    if in_event:
                        lines.append(line)
                    if line.startswith('END:VEVENT'):
                        in_event = False

        lines.append('END:VCALENDAR')
        ical_content = '\r\n'.join(lines)

        return Response(ical_content, mimetype='text/calendar', headers={
            'Content-Disposition': 'attachment; filename="calendar.ics"'
        })
    except Exception as e:
        abort(500)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
