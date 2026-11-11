import http.server
import socketserver
import json
import sqlite3
import os
import re
import datetime
import urllib.parse

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(DIRECTORY, "contact_messages.db")
LOG_FILE = os.path.join(DIRECTORY, "contact_submissions.log")
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
ADMIN_DEMO_USER = "admin"
ADMIN_DEMO_PASS = "nitin2026"

DEFAULT_CONTACT_INFO = {
    "email": "nitinb0407@gmail.com",
    "phone": "+91 93535 12112",
    "location": "Bengaluru, Karnataka, India",
    "education": "Jain University · CSE (AI & ML) · CGPA 7.5",
    "availability": "Available for Opportunities",
    "linkedin_url": "https://www.linkedin.com/in/nitin-b-a023003ab?utm_source=share_via&utm_content=profile&utm_medium=member_android",
    "github_url": "https://github.com/nitinb0407",
}

def _now_str():
    """Return current local timestamp string formatted for SQLite records."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    """Initialize SQLite tables for contact inquiries and contact info profile."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            subject TEXT,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            ip_address TEXT,
            is_read INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contact_info (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            location TEXT NOT NULL,
            education TEXT NOT NULL,
            availability TEXT NOT NULL,
            linkedin_url TEXT NOT NULL,
            github_url TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO contact_info (
            id, email, phone, location, education, availability, linkedin_url, github_url, updated_at
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        DEFAULT_CONTACT_INFO["email"],
        DEFAULT_CONTACT_INFO["phone"],
        DEFAULT_CONTACT_INFO["location"],
        DEFAULT_CONTACT_INFO["education"],
        DEFAULT_CONTACT_INFO["availability"],
        DEFAULT_CONTACT_INFO["linkedin_url"],
        DEFAULT_CONTACT_INFO["github_url"],
        _now_str()
    ))
    conn.commit()
    conn.close()

def fetch_contact_info():
    """Fetch singleton Get in Touch profile row from SQLite."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT email, phone, location, education, availability, linkedin_url, github_url, updated_at
        FROM contact_info WHERE id = 1
    """)
    row = cursor.fetchone()
    conn.close()
    if not row:
        return dict(DEFAULT_CONTACT_INFO, updated_at=_now_str())
    return {
        "email": row[0],
        "phone": row[1],
        "location": row[2],
        "education": row[3],
        "availability": row[4],
        "linkedin_url": row[5],
        "github_url": row[6],
        "updated_at": row[7]
    }

def fetch_messages(limit=50):
    """Fetch stored Get in Touch inquiries ordered newest-first."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, email, subject, message, created_at, ip_address, is_read
        FROM messages
        ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "name": r[1],
            "email": r[2],
            "subject": r[3],
            "message": r[4],
            "created_at": r[5],
            "ip_address": r[6] or "unknown",
            "is_read": bool(r[7])
        }
        for r in rows
    ]

def fetch_stats():
    """Return total, unread, and read counts from messages table."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM messages")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM messages WHERE is_read = 0")
    unread = cursor.fetchone()[0]
    conn.close()
    return {
        "total_messages": total,
        "unread_messages": unread,
        "read_messages": total - unread
    }

init_db()

class ThreadedPortfolioServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

class PortfolioHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def _set_cors_headers(self, status=200, content_type="application/json", extra_headers=None):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Type", content_type)
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()

    def _send_json(self, status, data, indent=None, extra_headers=None):
        """Serialize data as JSON with CORS headers."""
        self._set_cors_headers(status, extra_headers=extra_headers)
        self.wfile.write(json.dumps(data, indent=indent).encode("utf-8"))

    def _read_json_body(self):
        """Read and parse JSON request body, sending a 400 response if invalid."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._send_json(400, {"success": False, "error": "Empty request body"})
            return None
        raw_body = self.rfile.read(content_length).decode("utf-8")
        try:
            return json.loads(raw_body)
        except json.JSONDecodeError:
            self._send_json(400, {"success": False, "error": "Invalid JSON payload"})
            return None

    def do_OPTIONS(self):
        self._set_cors_headers(204)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/health":
            self._send_json(200, {
                "status": "online",
                "service": "Nitin B Portfolio Contact API",
                "timestamp": datetime.datetime.now().isoformat(),
                "database": "connected" if os.path.exists(DB_FILE) else "not_found"
            }, indent=2)
            return

        elif path == "/api/contact/messages":
            try:
                messages = fetch_messages(limit=50)
                stats = fetch_stats()
                response = {
                    "success": True,
                    "count": len(messages),
                    "messages": messages,
                    "stats": stats
                }
            except Exception as e:
                response = {"success": False, "error": str(e)}

            self._send_json(200, response, indent=2)
            return

        elif path == "/api/contact/stats":
            try:
                stats = fetch_stats()
                data = {
                    "success": True,
                    **stats
                }
            except Exception as e:
                data = {"success": False, "error": str(e)}

            self._send_json(200, data)
            return

        elif path == "/api/contact/info":
            try:
                data = {"success": True, "info": fetch_contact_info()}
            except Exception as e:
                data = {"success": False, "error": str(e)}

            self._send_json(200, data)
            return

        elif path == "/api/admin/export":
            try:
                data = {
                    "success": True,
                    "exported_at": _now_str(),
                    "contact_info": fetch_contact_info(),
                    "stats": fetch_stats(),
                    "messages": fetch_messages(limit=500)
                }
                self._send_json(200, data, indent=2, extra_headers={
                    "Content-Disposition": 'attachment; filename="nitin_portfolio_admin_export.json"'
                })
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return

        # Default static file serving
        return super().do_GET()

    def _handle_contact_submit(self):
        """Validate and store a new Get in Touch visitor inquiry."""
        payload = self._read_json_body()
        if payload is None:
            return

        name = str(payload.get("name", "")).strip()
        email = str(payload.get("email", "")).strip()
        subject = str(payload.get("subject", "")).strip() or "Portfolio Inquiry"
        message = str(payload.get("message", "")).strip()

        if len(name) < 2:
            self._send_json(400, {"success": False, "error": "Name must be at least 2 characters."})
            return

        if not email or not re.match(EMAIL_REGEX, email):
            self._send_json(400, {"success": False, "error": "Please provide a valid email address."})
            return

        if len(message) < 3:
            self._send_json(400, {"success": False, "error": "Message must be at least 3 characters."})
            return

        now_str = _now_str()
        client_ip = self.client_address[0] if self.client_address else "unknown"

        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (name, email, subject, message, created_at, ip_address, is_read)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            """, (name, email, subject, message, now_str, client_ip))
            conn.commit()
            msg_id = cursor.lastrowid
            conn.close()

            with open(LOG_FILE, "a", encoding="utf-8") as lf:
                lf.write(f"[{now_str}] ID: #{msg_id} | From: {name} <{email}> (IP: {client_ip})\n")
                lf.write(f"  Subject: {subject}\n")
                lf.write(f"  Message: {message}\n")
                lf.write("-" * 60 + "\n")

            self._send_json(201, {
                "success": True,
                "message": f"Thank you {name}! Your message has been received successfully.",
                "submission_id": msg_id,
                "created_at": now_str
            })
            print(f"[CONTACT INBOX] New message from {name} <{email}> (ID: #{msg_id})")
        except Exception as e:
            self._send_json(500, {"success": False, "error": f"Database error: {str(e)}"})

    def _delete_message_by_id(self, msg_id):
        """Delete a single contact inquiry row by integer ID."""
        try:
            msg_id = int(msg_id)
        except (TypeError, ValueError):
            self._send_json(400, {"success": False, "error": "Invalid message ID."})
            return

        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
            conn.commit()
            deleted = cursor.rowcount
            conn.close()

            if deleted == 0:
                self._send_json(404, {"success": False, "error": f"Message #{msg_id} not found."})
                return

            self._send_json(200, {"success": True, "deleted_id": msg_id})
            print(f"[ADMIN] Deleted contact message #{msg_id}")
        except Exception as e:
            self._send_json(500, {"success": False, "error": f"Database error: {str(e)}"})

    def _handle_update_contact_info(self):
        """Validate and update singleton Get in Touch contact profile in SQLite."""
        payload = self._read_json_body()
        if payload is None:
            return

        current = fetch_contact_info()
        email = str(payload.get("email", current["email"])).strip()
        phone = str(payload.get("phone", current["phone"])).strip()
        location = str(payload.get("location", current["location"])).strip()
        education = str(payload.get("education", current["education"])).strip()
        availability = str(payload.get("availability", current["availability"])).strip()
        linkedin_url = str(payload.get("linkedin_url", current["linkedin_url"])).strip()
        github_url = str(payload.get("github_url", current["github_url"])).strip()

        if not email or not re.match(EMAIL_REGEX, email):
            self._send_json(400, {"success": False, "error": "Please enter a valid contact email."})
            return

        for field_label, value in [
            ("Phone", phone),
            ("Location", location),
            ("Education", education),
            ("Availability", availability),
        ]:
            if not value:
                self._send_json(400, {"success": False, "error": f"{field_label} cannot be empty."})
                return

        for url_label, url_val in [("LinkedIn URL", linkedin_url), ("GitHub URL", github_url)]:
            if not url_val.startswith(("http://", "https://")):
                self._send_json(400, {"success": False, "error": f"{url_label} must start with http:// or https://."})
                return

        updated_at = _now_str()
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE contact_info
                SET email = ?, phone = ?, location = ?, education = ?,
                    availability = ?, linkedin_url = ?, github_url = ?, updated_at = ?
                WHERE id = 1
            """, (email, phone, location, education, availability, linkedin_url, github_url, updated_at))
            conn.commit()
            conn.close()

            self._send_json(200, {
                "success": True,
                "message": "Get in Touch information updated successfully.",
                "info": fetch_contact_info()
            })
            print(f"[ADMIN] Updated Get in Touch profile ({email})")
        except Exception as e:
            self._send_json(500, {"success": False, "error": f"Database error: {str(e)}"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/contact" or path == "/api/contact/submit":
            self._handle_contact_submit()
            return

        elif path == "/api/admin/messages/read":
            payload = self._read_json_body()
            if payload is None:
                return
            try:
                msg_id = int(payload.get("id"))
            except (TypeError, ValueError):
                self._send_json(400, {"success": False, "error": "Valid integer message id is required."})
                return
            is_read = bool(payload.get("is_read", True))
            try:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("UPDATE messages SET is_read = ? WHERE id = ?", (1 if is_read else 0, msg_id))
                conn.commit()
                updated = cursor.rowcount
                conn.close()
                if updated == 0:
                    self._send_json(404, {"success": False, "error": f"Message #{msg_id} not found."})
                    return
                self._send_json(200, {"success": True, "id": msg_id, "is_read": is_read})
            except Exception as e:
                self._send_json(500, {"success": False, "error": f"Database error: {str(e)}"})
            return

        elif path == "/api/admin/messages/mark-all-read":
            try:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("UPDATE messages SET is_read = 1 WHERE is_read = 0")
                conn.commit()
                updated_count = cursor.rowcount
                conn.close()
                self._send_json(200, {"success": True, "updated_count": updated_count})
            except Exception as e:
                self._send_json(500, {"success": False, "error": f"Database error: {str(e)}"})
            return

        elif path == "/api/admin/messages/delete":
            payload = self._read_json_body()
            if payload is None:
                return
            self._delete_message_by_id(payload.get("id"))
            return

        elif path == "/api/admin/contact-info":
            self._handle_update_contact_info()
            return

        elif path == "/api/admin/login":
            payload = self._read_json_body()
            if payload is None:
                return
            username = str(payload.get("username", "")).strip()
            password = str(payload.get("password", "")).strip()
            if username == ADMIN_DEMO_USER and password == ADMIN_DEMO_PASS:
                self._send_json(200, {
                    "success": True,
                    "username": ADMIN_DEMO_USER,
                    "admin_details": {
                        "username": ADMIN_DEMO_USER,
                        "role": "Portfolio Owner & Administrator",
                        "owner": "Nitin B",
                        "database": os.path.basename(DB_FILE),
                        "authenticated_at": _now_str()
                    },
                    "message": "Demo admin credentials verified."
                })
                print(f"[ADMIN] Authenticated demo session for user '{username}'")
            else:
                self._send_json(401, {
                    "success": False,
                    "error": "Invalid demo credentials. Use Username: admin / Password: nitin2026."
                })
            return

        self._send_json(404, {"success": False, "error": "Endpoint not found"})

    def do_PUT(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/admin/contact-info":
            self._handle_update_contact_info()
            return
        self._send_json(404, {"success": False, "error": "Endpoint not found"})

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path
        prefix = "/api/admin/messages/"
        if path.startswith(prefix):
            msg_id_part = path[len(prefix):].strip("/")
            self._delete_message_by_id(msg_id_part)
            return
        self._send_json(404, {"success": False, "error": "Endpoint not found"})

def run_server():
    with ThreadedPortfolioServer(("", PORT), PortfolioHandler) as httpd:
        print(f"==================================================")
        print(f" Nitin B Portfolio Threaded Backend Server")
        print(f" Serving Static Files & API on http://localhost:{PORT}")
        print(f" Database: {DB_FILE}")
        print(f" Endpoints:")
        print(f"   - GET  /api/health")
        print(f"   - POST /api/contact")
        print(f"   - GET  /api/contact/messages")
        print(f"   - GET  /api/contact/stats")
        print(f"   - GET  /api/contact/info")
        print(f"   - GET  /api/admin/export")
        print(f"   - POST /api/admin/contact-info")
        print(f"   - POST /api/admin/messages/read")
        print(f"   - POST /api/admin/messages/mark-all-read")
        print(f"   - POST /api/admin/messages/delete")
        print(f"==================================================")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
