import os
import caldav
from flask import Flask, Response, render_template_string, request, abort
import hashlib

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
  .card { background: white; border-radius: 16px; padding: 40px; max-width: 520px; width: 100%; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }
  h1 { font-size: 24px; font-weight: 700; margin-bottom: 8px; color: #1d1d1f; }
  p { color: #6e6e73; font-size: 14px; margin-bottom: 28px; line-height: 1.5; }
  label { display: block; font-size: 13px; font-weight: 600; color: #1d1d1f; margin-bottom: 6px; }
  input { width: 100%; padding: 10px 14px; border: 1.5px solid #d2d2d7; border-radius: 8px; font-size: 14px; outline: none; transition: border-color 0.2s; margin-bottom: 16px; }
  input:focus { border-color: #0071e3; }
  button { width: 100%; padding: 12px; background: #0071e3; color: white; border: none; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; transition: background 0.2s; }
  button:hover { background: #0077ed; }
  .result { margin-top: 24px; padding: 16px; background: #f5f5f7; border-radius: 8px; display: none; }
  .result.show { display: block; }
  .result label { margin-bottom: 8px; }
  .url-box { display: flex; gap: 8px; }
  .url-box input { margin-bottom: 0; flex: 1; font-family: monospace; font-size: 12px; background: white; }
  .copy-btn { padding: 10px 16px; background: #34c759; color: white; border: none; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap; width: auto; }
  .copy-btn:hover { background: #30b350; }
  .hint { margin-top: 12px; font-size: 12px; color: #6e6e73; }
  .hint a { color: #0071e3; text-decoration: none; }
  .error { color: #ff3b30; font-size: 13px; margin-top: 12px; display: none; }
  .error.show { display: block; }
</style>
</head>
<body>
<div class="card">
  <h1>CalDAV → iCal Bridge</h1>
  <p>Convert your CalDAV calendar (Lark, Nextcloud, etc.) into a public iCal URL that Google Calendar can subscribe to.</p>
  <form id="form">
    <label>CalDAV Server URL</label>
    <input type="text" id="server" placeholder="e.g. https://caldav-jp.larksuite.com" required />
    <label>Username</label>
    <input type="text" id="username" placeholder="your CalDAV username" required />
    <label>Password / Token</label>
    <input type="password" id="password" placeholder="your CalDAV password or token" required />
    <button type="submit">Generate iCal URL</button>
  </form>
  <div class="error" id="error"></div>
  <div class="result" id="result">
    <label>Your iCal URL (paste into Google Calendar):</label>
    <div class="url-box">
      <input type="text" id="ical-url" readonly />
      <button class="copy-btn" onclick="copyUrl()">Copy</button>
    </div>
    <p class="hint">In Google Calendar: Other calendars → + → From URL → paste above.<br>
    Subscribe link also works with Apple Calendar, Outlook, etc.</p>
  </div>
</div>
<script>
document.getElementById('form').onsubmit = async (e) => {
  e.preventDefault();
  const btn = e.target.querySelector('button');
  btn.textContent = 'Generating...';
  btn.disabled = true;
  document.getElementById('error').classList.remove('show');
  document.getElementById('result').classList.remove('show');
  const res = await fetch('/generate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      server: document.getElementById('server').value,
      username: document.getElementById('username').value,
      password: document.getElementById('password').value,
    })
  });
  const data = await res.json();
  btn.textContent = 'Generate iCal URL';
  btn.disabled = false;
  if (data.error) {
    document.getElementById('error').textContent = '❌ ' + data.error;
    document.getElementById('error').classList.add('show');
  } else {
    document.getElementById('ical-url').value = data.url;
    document.getElementById('result').classList.add('show');
  }
};
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

# In-memory store: token -> (server, username, password)
_store = {}

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

    # Test connection
    try:
        client = caldav.DAVClient(url=server, username=username, password=password)
        principal = client.principal()
        calendars = principal.calendars()
        if not calendars:
            return {'error': 'Connected but no calendars found.'}, 400
    except Exception as e:
        return {'error': f'Connection failed: {str(e)}'}, 400

    token = make_token(server, username, password)
    _store[token] = (server, username, password)

    host = request.host_url.rstrip('/')
    return {'url': f'{host}/ical/{token}'}

@app.route('/ical/<token>')
def serve_ical(token):
    if token not in _store:
        abort(404)

    server, username, password = _store[token]

    try:
        client = caldav.DAVClient(url=server, username=username, password=password)
        principal = client.principal()
        calendars = principal.calendars()

        lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//CalDAV2iCal Bridge//EN', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH']

        for cal in calendars:
            for event in cal.events():
                ical_data = event.data
                # Extract VEVENT blocks
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
