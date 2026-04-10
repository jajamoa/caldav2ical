import os
import caldav
import threading
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
  .result { margin-top: 24px; display: none; }
  .result.show { display: block; }
  .result h2 { font-size: 15px; font-weight: 600; color: #1d1d1f; margin-bottom: 12px; }
  .url-box { display: flex; gap: 8px; }
  .url-box input { margin-bottom: 0; flex: 1; font-family: monospace; font-size: 12px; background: #f5f5f7; }
  .copy-btn { padding: 10px 16px; background: #34c759; color: white; border: none; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap; width: auto; }
  .copy-btn:hover { background: #30b350; }
  .hint { margin-top: 10px; font-size: 12px; color: #6e6e73; line-height: 1.5; }
  .preview-section { margin-top: 20px; padding: 16px; background: #f5f5f7; border-radius: 8px; display: none; }
  .preview-section.show { display: block; }
  .preview-section h3 { font-size: 13px; font-weight: 600; color: #6e6e73; margin-bottom: 10px; }
  .spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid #d2d2d7; border-top-color: #0071e3; border-radius: 50%; animation: spin 0.8s linear infinite; vertical-align: middle; margin-right: 6px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .cal-name { font-size: 12px; font-weight: 600; color: #6e6e73; text-transform: uppercase; letter-spacing: 0.5px; margin: 12px 0 6px; }
  .event-item { padding: 8px 10px; border-radius: 6px; background: white; margin-bottom: 4px; font-size: 13px; }
  .event-title { font-weight: 600; color: #1d1d1f; }
  .event-time { color: #6e6e73; font-size: 12px; margin-top: 1px; }
  .error { color: #ff3b30; font-size: 13px; margin-top: 12px; display: none; }
  .error.show { display: block; }
  .divider { border: none; border-top: 1.5px solid #f0f0f0; margin: 20px 0; }
</style>
</head>
<body>
<div class="card">
  <h1>CalDAV → iCal Bridge</h1>
  <p class="subtitle">Connect your CalDAV calendar (Lark, Nextcloud, etc.) and get a shareable iCal URL for Google Calendar and more.</p>

  <form id="form">
    <label>CalDAV Server URL</label>
    <input type="text" id="server" placeholder="e.g. https://caldav-jp.larksuite.com" required />
    <label>Username</label>
    <input type="text" id="username" placeholder="your CalDAV username" required />
    <label>Password / Token</label>
    <input type="password" id="password" placeholder="your CalDAV password or token" required />
    <button type="submit" id="connect-btn">Generate iCal URL</button>
  </form>

  <div class="error" id="error"></div>

  <div class="result" id="result">
    <hr class="divider">
    <h2>✅ Your iCal URL</h2>
    <div class="url-box">
      <input type="text" id="ical-url" readonly />
      <button class="copy-btn" onclick="copyUrl()">Copy</button>
    </div>
    <p class="hint">
      <strong>Google Calendar:</strong> Other calendars → + → From URL → paste above.<br>
      Works with Apple Calendar, Outlook, and any iCal-compatible app.
    </p>

    <div class="preview-section show" id="preview-section">
      <h3><span class="spinner"></span> Loading calendar preview...</h3>
      <div id="preview-content"></div>
    </div>
  </div>
</div>

<script>
let _token = null;

document.getElementById('form').onsubmit = async (e) => {
  e.preventDefault();
  const btn = document.getElementById('connect-btn');
  btn.textContent = 'Connecting...';
  btn.disabled = true;
  document.getElementById('error').classList.remove('show');
  document.getElementById('result').classList.remove('show');

  const payload = {
    server: document.getElementById('server').value.trim().replace(/\\/+$/, ''),
    username: document.getElementById('username').value.trim(),
    password: document.getElementById('password').value.trim(),
  };

  const res = await fetch('/generate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  btn.textContent = 'Generate iCal URL';
  btn.disabled = false;

  if (data.error) {
    document.getElementById('error').textContent = '❌ ' + data.error;
    document.getElementById('error').classList.add('show');
    return;
  }

  _token = data.token;
  document.getElementById('ical-url').value = data.url;
  document.getElementById('result').classList.add('show');
  document.getElementById('result').scrollIntoView({ behavior: 'smooth' });

  // Load preview async
  loadPreview(_token);
};

async function loadPreview(token) {
  const section = document.getElementById('preview-section');
  const content = document.getElementById('preview-content');

  try {
    const res = await fetch('/preview/' + token);
    const data = await res.json();

    if (data.error) {
      section.querySelector('h3').textContent = '⚠️ Preview unavailable';
      return;
    }

    let total = 0;
    let html = '';
    for (const cal of data.calendars) {
      html += `<div class="cal-name">📁 ${cal.name} (${cal.events.length} events)</div>`;
      for (const ev of cal.events.slice(0, 5)) {
        html += `<div class="event-item"><div class="event-title">${ev.title}</div><div class="event-time">${ev.time}</div></div>`;
      }
      if (cal.events.length > 5) {
        html += `<div class="event-item" style="color:#6e6e73;font-size:12px">+${cal.events.length - 5} more</div>`;
      }
      total += cal.events.length;
    }

    section.querySelector('h3').textContent = `📅 Found ${data.calendars.length} calendar(s), ${total} events`;
    content.innerHTML = html;
  } catch(e) {
    section.querySelector('h3').textContent = '⚠️ Preview unavailable';
  }
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

# In-memory store
_store = {}
_preview_cache = {}

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    server = data.get('server', '').strip().rstrip('/')
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not all([server, username, password]):
        return {'error': 'All fields are required.'}, 400

    # Quick auth check only (fast)
    try:
        client = caldav.DAVClient(url=server, username=username, password=password, timeout=10)
        principal = client.principal()
    except Exception as e:
        return {'error': f'Connection failed: {str(e)}'}, 400

    token = make_token(server, username, password)
    _store[token] = (server, username, password)

    # Trigger background preview load
    threading.Thread(target=_load_preview_bg, args=(token, server, username, password), daemon=True).start()

    host = request.host_url.rstrip('/')
    return {'token': token, 'url': f'{host}/ical/{token}'}

def _load_preview_bg(token, server, username, password):
    """Load calendar preview in background thread."""
    try:
        client = caldav.DAVClient(url=server, username=username, password=password, timeout=25)
        principal = client.principal()
        calendars = principal.calendars()

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=30)
        end = now + timedelta(days=90)

        cal_preview = []
        for cal in calendars:
            try:
                cal_name = str(cal.name) if cal.name else "Calendar"
                try:
                    events = cal.date_search(start=start, end=end)
                except Exception:
                    events = cal.events()
                parsed = [parse_event(ev.data) for ev in events[:50]]
                parsed = [p for p in parsed if p['title'] != 'Untitled' or p['time']]
                parsed.sort(key=lambda x: x['time'] or '')
                cal_preview.append({"name": cal_name, "events": parsed})
            except Exception:
                cal_preview.append({"name": "Calendar", "events": []})

        _preview_cache[token] = {"calendars": cal_preview}
    except Exception as e:
        _preview_cache[token] = {"error": str(e)}

@app.route('/preview/<token>')
def get_preview(token):
    if token not in _store:
        abort(404)

    # Poll up to 25s
    import time
    for _ in range(25):
        if token in _preview_cache:
            return _preview_cache[token]
        time.sleep(1)

    return {"error": "Preview timed out"}, 408

@app.route('/ical/<token>')
def serve_ical(token):
    if token not in _store:
        abort(404)

    server, username, password = _store[token]

    try:
        client = caldav.DAVClient(url=server, username=username, password=password, timeout=25)
        principal = client.principal()
        calendars = principal.calendars()

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=365)
        end = now + timedelta(days=365)

        lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//CalDAV2iCal Bridge//EN',
                 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH']

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
