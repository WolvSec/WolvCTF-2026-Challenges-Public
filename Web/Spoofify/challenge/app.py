import os

from flask import Flask, request, make_response, render_template_string

app = Flask(__name__)


def load_flag():
    env = os.environ.get("FLAG")
    if env:
        return env
    for path in ("/flag", "/flag.txt"):
        try:
            with open(path, encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            pass
    return "wctf{placeholder_flag_change_me}"


FLAG = load_flag()

PAGE = """
<!doctype html>
<title>Spoofify</title>
<style>
  :root { color-scheme: dark; }
  body { font-family: 'Helvetica Neue', Arial, sans-serif; color:#fff; display:flex;
         justify-content:center; padding-top:8vh; min-height:100vh; margin:0;
         background:#121212; }
  .card { background:#181818; padding:2.2rem 2.5rem; border-radius:16px;
          box-shadow:0 8px 30px rgba(0,0,0,.6); width:400px; }
  .logo { display:flex; align-items:center; gap:.5rem; margin-bottom:1.4rem; }
  .logo .dot { width:28px; height:28px; border-radius:50%; background:#1db954;
               display:flex; align-items:center; justify-content:center; font-size:16px; }
  .logo b { font-size:1.3rem; letter-spacing:-.5px; }
  .badge { display:inline-block; padding:.25rem .7rem; border-radius:20px;
           font-size:.78rem; font-weight:700; letter-spacing:.3px; }
  .free    { background:#2a2a2a; color:#aaa; }
  .premium { background:#1db954; color:#042a12; }
  .track { display:flex; justify-content:space-between; align-items:center;
           padding:.6rem 0; border-bottom:1px solid #282828; font-size:.9rem; color:#b3b3b3; }
  code { background:#000; color:#1db954; padding:3px 6px; border-radius:4px; }
  .flagbox { margin-top:1.2rem; padding:.9rem 1rem; background:#0d1f14;
             border-left:3px solid #1db954; border-radius:8px; }
  .upsell { margin-top:1.2rem; padding:.9rem 1rem; background:#222; border-radius:8px;
            font-size:.85rem; color:#b3b3b3; }
</style>
<div class="card">
  <div class="logo"><div class="dot">♪</div><b>Spoofify</b></div>
  <p>Your plan: <span class="badge {{ 'premium' if plan == 'premium' else 'free' }}">{{ plan|capitalize }}</span></p>

  {% if plan == 'premium' %}
    <p>Welcome, Premium listener. No ads, offline downloads, and your
       exclusive unlock code for this week's unreleased drop:</p>
    <div class="flagbox"><code>{{ flag }}</code></div>
  {% else %}
    <div class="track"><span>🔈 Track skips after 30s</span><span>Free</span></div>
    <div class="track"><span>📢 Ads between songs</span><span>Free</span></div>
    <div class="track"><span>⬇️ Offline downloads</span><span>Premium</span></div>
    <div class="upsell">Upgrade to Premium for unlimited skips, no ads, and
      this week's exclusive unreleased-track unlock code.</div>
  {% endif %}
</div>
"""


@app.route("/")
def index():
    plan = request.cookies.get("sid", "free")

    resp = make_response()
    if "sid" not in request.cookies:
        # First visit: hand out a plain, unsigned session cookie.
        plan = "free"
        resp.set_cookie("sid", plan)

    resp.set_data(render_template_string(PAGE, plan=plan, flag=FLAG))
    return resp


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=1337)
