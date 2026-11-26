import os
from threading import Lock

from flask import Flask, abort, redirect, render_template_string, request, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
app.config["MAX_CONTENT_LENGTH"] = 4096
FLAG = os.environ.get("FLAG")
if FLAG is None:
    with open(os.environ.get("FLAG_FILE", "/app/flag.txt"), encoding="utf-8") as flag_file:
        FLAG = flag_file.read().strip()

notes = {
    1: {"owner": "admin", "title": "Flag", "body": FLAG},
    2: {"owner": "admin", "title": "Meeting", "body": "Standup at 10."},
}
next_id = 3
notes_lock = Lock()

LOGIN = """
<h1>StickyNotes</h1>
<form method="post">
  <input name="username" placeholder="pick a username" required>
  <button>Enter</button>
</form>
"""

LIST = """
<h1>{{ user }}'s notes</h1>
<ul>
{% for i, n in mine.items() %}
  <li><a href="/note/{{ i }}">{{ n.title }}</a></li>
{% else %}
  <li>No notes yet.</li>
{% endfor %}
</ul>
<form method="post">
  <input name="title" placeholder="title" required>
  <input name="body" placeholder="body" required>
  <button>Add note</button>
</form>
"""

VIEW = '<h1>{{ note.title }}</h1><p>{{ note.body }}</p><a href="/notes">back</a>'


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form.get("username", "").strip()
        if not name:
            return "Please choose a username.", 400
        if name.lower() == "admin":
            return "Nice try.", 403
        session["user"] = name
        return redirect("/notes")
    return render_template_string(LOGIN)


@app.route("/notes", methods=["GET", "POST"])
def my_notes():
    global next_id
    user = session.get("user")
    if not user:
        return redirect("/")
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        if not title or not body:
            return "A title and body are required.", 400
        with notes_lock:
            if len(notes) >= 5000:
                return "Note storage is full.", 503
            notes[next_id] = {"owner": user, "title": title, "body": body}
            next_id += 1
    with notes_lock:
        mine = {i: n for i, n in notes.items() if n["owner"] == user}
    return render_template_string(LIST, mine=mine, user=user)


@app.route("/note/<int:note_id>")
def view_note(note_id):
    if "user" not in session:
        return redirect("/")
    note = notes.get(note_id)
    if not note:
        abort(404)
    return render_template_string(VIEW, note=note)


if __name__ == "__main__":
    # In-memory notes require one process; do not enable a multi-worker server.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
