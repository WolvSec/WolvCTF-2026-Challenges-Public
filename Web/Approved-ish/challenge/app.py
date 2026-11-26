"""Approved-ish web application and opaque workspace sessions."""

import hashlib
import os
import secrets
import sqlite3
import time
from pathlib import Path
from uuid import uuid4

from flask import Flask, abort, g, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from storage import database, initialize
from workflow import create_workflow


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        DATABASE=os.environ.get("DATABASE", str(Path(__file__).parent / "instance" / "approved.sqlite3")),
        FLAG="wctf{local_placeholder_only}", MAX_CONTENT_LENGTH=32768,
        COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
        WORKSPACE_TTL=21600, MAX_WORKSPACES=2000, MAX_WORKSPACES_PER_PEER=64,
    )
    if test_config:
        app.config.update(test_config)
    else:
        flag_file = os.environ.get("FLAG_FILE")
        if flag_file:
            app.config["FLAG"] = Path(flag_file).read_text().strip()
        if os.environ.get("REQUIRE_FLAG_FILE") == "1" and not flag_file:
            raise RuntimeError("FLAG_FILE must be configured.")
    if not app.config["FLAG"].startswith("wctf{") or not app.config["FLAG"].endswith("}"):
        raise RuntimeError("Expected a non-empty wctf flag.")
    initialize(app.config["DATABASE"])
    app.register_blueprint(create_workflow())

    @app.before_request
    def authenticate():
        if not request.path.startswith("/api/"):
            return
        db = database()
        db.execute("BEGIN IMMEDIATE" if request.method in {"POST", "PATCH", "PUT", "DELETE"} else "BEGIN")
        if request.path == "/api/session" and request.method == "POST":
            return
        token = request.cookies.get("workspace", "")
        if len(token) > 128:
            abort(401)
        digest = hashlib.sha256(token.encode()).hexdigest()
        g.workspace = db.execute("SELECT id,expires FROM workspaces WHERE token_hash=? AND expires>?",
                                 (digest, int(time.time()))).fetchone()
        if g.workspace is None:
            abort(401, description="Create a workspace to begin; reload if your previous one was reset or expired.")

    @app.after_request
    def finish(response):
        if "db" in g:
            if response.status_code < 400:
                g.db.commit()
            else:
                g.db.rollback()
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        return response

    @app.teardown_appcontext
    def close_db(_error):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.name.lower().replace(" ", "_"), message=error.description), error.code

    @app.errorhandler(sqlite3.OperationalError)
    def storage_error(error):
        app.logger.error("Storage operation failed: %s", error)
        return jsonify(error="storage_unavailable", message="Please retry shortly."), 503

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/healthz")
    def healthz():
        database().execute("SELECT 1 FROM workspaces LIMIT 1").fetchone()
        return jsonify(status="ok")

    @app.post("/api/session")
    def create_session():
        db = database()
        now = int(time.time())
        peer_addr = request.remote_addr or "unknown"
        db.execute("DELETE FROM workspaces WHERE expires<=?", (now,))
        peer_count = db.execute("SELECT count(*) FROM workspaces WHERE peer_addr=?", (peer_addr,)).fetchone()[0]
        if peer_count >= app.config["MAX_WORKSPACES_PER_PEER"]:
            removed = db.execute(
                "DELETE FROM workspaces WHERE id=(SELECT w.id FROM workspaces w "
                "WHERE w.peer_addr=? "
                "AND NOT EXISTS(SELECT 1 FROM aliases a WHERE a.workspace_id=w.id) "
                "AND NOT EXISTS(SELECT 1 FROM manifests m WHERE m.workspace_id=w.id) "
                "ORDER BY w.expires,w.rowid LIMIT 1)", (peer_addr,))
            if removed.rowcount == 0:
                abort(429, description="Workspace limit for this network address reached; try again later.")
        if db.execute("SELECT count(*) FROM workspaces").fetchone()[0] >= app.config["MAX_WORKSPACES"]:
            removed = db.execute(
                "DELETE FROM workspaces WHERE id=(SELECT w.id FROM workspaces w "
                "WHERE NOT EXISTS(SELECT 1 FROM aliases a WHERE a.workspace_id=w.id) "
                "AND NOT EXISTS(SELECT 1 FROM manifests m WHERE m.workspace_id=w.id) "
                "ORDER BY w.expires,w.rowid LIMIT 1)")
            if removed.rowcount == 0:
                abort(429, description="Workspace capacity reached; try again later.")
        token = secrets.token_urlsafe(32)
        workspace_id = uuid4().hex
        expires = now + app.config["WORKSPACE_TTL"]
        db.execute("INSERT INTO workspaces VALUES (?,?,?,?)",
                   (workspace_id, hashlib.sha256(token.encode()).hexdigest(), expires, peer_addr))
        response = jsonify(workspace_id=workspace_id, expires=expires)
        response.status_code = 201
        response.set_cookie("workspace", token, max_age=app.config["WORKSPACE_TTL"], httponly=True,
                            secure=app.config["COOKIE_SECURE"], samesite="Lax")
        return response

    @app.get("/api/me")
    def me():
        return jsonify(id="member", workspace_id=g.workspace["id"], expires=g.workspace["expires"])

    @app.delete("/api/session")
    def delete_session():
        database().execute("DELETE FROM workspaces WHERE id=?", (g.workspace["id"],))
        response = jsonify(deleted=True)
        response.delete_cookie("workspace")
        return response

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=8000, debug=False)
