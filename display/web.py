#!/usr/bin/env python3
"""Minimal Flask UI for editing messages.txt.

Accessible at http://<tailscale-ip>:5000
"""

import os
from flask import Flask, request, render_template_string

app = Flask(__name__)
MSG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'messages.txt')

_PAGE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LED Display</title>
<style>
* { box-sizing: border-box; }
body { font-family: monospace; background: #0d0d0b; color: #ff8800;
       max-width: 560px; margin: 40px auto; padding: 0 16px; }
h1 { font-size: 1.1rem; letter-spacing: 0.2em; margin-bottom: 20px; }
textarea { width: 100%; height: 280px; background: #050503; color: #ff8800;
           border: 1px solid #2a2a20; padding: 10px; font-family: monospace;
           font-size: 14px; resize: vertical; outline: none; }
textarea:focus { border-color: #ff8800; }
button { margin-top: 10px; background: #ff8800; color: #000; border: none;
         padding: 8px 24px; font-family: monospace; font-size: 14px;
         cursor: pointer; letter-spacing: 0.1em; }
button:hover { background: #ffaa33; }
.ok   { color: #44ff44; font-size: 0.85rem; margin: 10px 0 0; }
.hint { color: #444; font-size: 0.75rem; margin-top: 14px; line-height: 1.7; }
.hint b { color: #666; }
</style>
</head>
<body>
<h1>LED DISPLAY</h1>
{% if saved %}<p class="ok">&#x2714; Saved — display reloads within 2 seconds.</p>{% endif %}
<form method="post">
  <textarea name="content" spellcheck="false" autocorrect="off" autocapitalize="characters">{{ content }}</textarea>
  <br>
  <button type="submit">UPDATE DISPLAY</button>
</form>
<p class="hint">
  One message per line.<br>
  Short lines (&le;32 px wide) display static &mdash; long lines scroll.<br>
  Write <b>CLOCK</b> on a line to show a live HH:MM clock.
</p>
</body>
</html>
"""


@app.route('/', methods=['GET', 'POST'])
def index():
    saved = False
    if request.method == 'POST':
        content = request.form.get('content', '')
        with open(MSG_FILE, 'w') as f:
            f.write(content)
        saved = True
    try:
        with open(MSG_FILE) as f:
            content = f.read()
    except OSError:
        content = ''
    return render_template_string(_PAGE, content=content, saved=saved)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
