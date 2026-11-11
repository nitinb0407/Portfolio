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

def init_db():
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
    conn.commit()
    conn.close()

init_db()

class ThreadedPortfolioServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

class PortfolioHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def _set_cors_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Type", content_type)
        self.end_headers()

    def do_OPTIONS(self):
        self._set_cors_headers(204)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/health":
            self._set_cors_headers(200)
            data = {
                "status": "online",
                "service": "Nitin B Portfolio Contact API",
                "timestamp": datetime.datetime.now().isoformat(),
                "database": "connected" if os.path.exists(DB_FILE) else "not_found"
            }
            self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))
            return

        elif path == "/api/contact/messages":
            # Returns recent contact messages
            self._set_cors_headers(200)
            try:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, name, email, subject, message, created_at, is_read 
                    FROM messages 
                    ORDER BY id DESC LIMIT 50
                """)
                rows = cursor.fetchall()
                conn.close()

                messages = []
                for r in rows:
                    messages.append({
                        "id": r[0],
                        "name": r[1],
                        "email": r[2],
                        "subject": r[3],
                        "message": r[4],
                        "created_at": r[5],
                        "is_read": bool(r[6])
                    })
                response = {
                    "success": True,
                    "count": len(messages),
                    "messages": messages
                }
            except Exception as e:
                response = {"success": False, "error": str(e)}

            self.wfile.write(json.dumps(response, indent=2).encode("utf-8"))
            return

        elif path == "/api/contact/stats":
            self._set_cors_headers(200)
            try:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM messages")
                total = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM messages WHERE is_read = 0")
                unread = cursor.fetchone()[0]
                conn.close()

                data = {
                    "success": True,
                    "total_messages": total,
                    "unread_messages": unread
                }
            except Exception as e:
                data = {"success": False, "error": str(e)}

            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        # Default static file serving
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/contact" or path == "/api/contact/submit":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._set_cors_headers(400)
                self.wfile.write(json.dumps({"success": False, "error": "Empty request body"}).encode("utf-8"))
                return

            raw_body = self.rfile.read(content_length).decode("utf-8")
            try:
                payload = json.loads(raw_body)
            except json.JSONDecodeError:
                self._set_cors_headers(400)
                self.wfile.write(json.dumps({"success": False, "error": "Invalid JSON payload"}).encode("utf-8"))
                return

            name = payload.get("name", "").strip()
            email = payload.get("email", "").strip()
            subject = payload.get("subject", "").strip() or "Portfolio Inquiry"
            message = payload.get("message", "").strip()

            # Validation
            if not name or len(name) < 2:
                self._set_cors_headers(400)
                self.wfile.write(json.dumps({"success": False, "error": "Name must be at least 2 characters."}).encode("utf-8"))
                return

            email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
            if not email or not re.match(email_regex, email):
                self._set_cors_headers(400)
                self.wfile.write(json.dumps({"success": False, "error": "Please provide a valid email address."}).encode("utf-8"))
                return

            if not message or len(message) < 3:
                self._set_cors_headers(400)
                self.wfile.write(json.dumps({"success": False, "error": "Message must be at least 3 characters."}).encode("utf-8"))
                return

            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            client_ip = self.client_address[0] if self.client_address else "unknown"

            # Save to SQLite Database
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

                # Also append to log file for easy viewing
                with open(LOG_FILE, "a", encoding="utf-8") as lf:
                    lf.write(f"[{now_str}] ID: #{msg_id} | From: {name} <{email}> (IP: {client_ip})\n")
                    lf.write(f"  Subject: {subject}\n")
                    lf.write(f"  Message: {message}\n")
                    lf.write("-" * 60 + "\n")

                self._set_cors_headers(201)
                response = {
                    "success": True,
                    "message": f"Thank you {name}! Your message has been received successfully.",
                    "submission_id": msg_id,
                    "created_at": now_str
                }
                self.wfile.write(json.dumps(response).encode("utf-8"))
                print(f"[CONTACT INBOX] New message from {name} <{email}> (ID: #{msg_id})")

            except Exception as e:
                self._set_cors_headers(500)
                self.wfile.write(json.dumps({"success": False, "error": f"Database error: {str(e)}"}).encode("utf-8"))
            return

        self._set_cors_headers(404)
        self.wfile.write(json.dumps({"success": False, "error": "Endpoint not found"}).encode("utf-8"))

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
        print(f"==================================================")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
