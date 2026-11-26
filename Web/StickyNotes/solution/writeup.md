# StickyNotes

Log in with any username other than `admin`. Add a note and open it. Its URL uses an integer note ID, and a new user's first note is ID 3. Try `/note/1` in the address bar to read the admin's flag note.

The route checks that a visitor is logged in but never checks whether the requested note belongs to that visitor. This is an insecure direct object reference (IDOR): the application uses a user-controlled object ID without enforcing authorization.

To fix it, compare `note["owner"]` with `session["user"]` in `view_note` and return 403 when they differ.

Optional hints to release in order:
1. Look closely at the URL when you open one of your notes.
2. Your notes are numbered. Who might own the notes numbered before yours?
