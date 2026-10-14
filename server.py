import http.server
import socketserver
import socket
import sqlite3
import json
import urllib.parse
import urllib.request
import os
import sys
import base64
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "inquiries.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_DIR, exist_ok=True)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ignbfwluzxiykrvrcxvi.supabase.co")
SUPABASE_ANON_KEY = os.environ.get(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlnbmJmd2x1enhpeWtydnJjeHZpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTE5NDc5OTAsImV4cCI6MjEwNzUyMzk5MH0.sA4zVET2OjXp0PLgALAXGqzfGJEytiUCQSKYwBfKBKE"
)

def save_to_supabase(inquiry_data):
    """
    Saves inquiry to Supabase database via REST API.
    Returns the created record from Supabase or None if failed.
    """
    try:
        url = f"{SUPABASE_URL}/rest/v1/inquiries"
        payload = {
            "full_name": inquiry_data.get("full_name"),
            "email": inquiry_data.get("email"),
            "phone": inquiry_data.get("phone"),
            "company": inquiry_data.get("company"),
            "service": inquiry_data.get("service"),
            "plan": inquiry_data.get("plan"),
            "budget": inquiry_data.get("budget"),
            "deadline": inquiry_data.get("deadline"),
            "details": inquiry_data.get("details"),
            "reference_url": inquiry_data.get("reference_url"),
            "file_name": inquiry_data.get("file_name"),
            "status": "new"
        }
        
        req_data = json.dumps(payload).encode("utf-8")
        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_body = resp.read().decode("utf-8")
            records = json.loads(resp_body)
            if records and len(records) > 0:
                print(f"[SUPABASE SUCCESS]: Saved inquiry #{records[0].get('id')} to Supabase.", flush=True)
                return records[0]
    except Exception as e:
        print(f"[SUPABASE ERROR]: Failed to save to Supabase: {e}", flush=True)
    return None

def init_db():
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            company TEXT,
            service TEXT,
            budget TEXT,
            deadline TEXT,
            details TEXT,
            reference_url TEXT,
            file_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Add columns if migrating from previous schema
    cursor.execute("PRAGMA table_info(inquiries)")
    columns = [col[1] for col in cursor.fetchall()]
    new_cols = [
        ("phone", "TEXT"),
        ("company", "TEXT"),
        ("deadline", "TEXT"),
        ("details", "TEXT"),
        ("reference_url", "TEXT"),
        ("file_name", "TEXT"),
        ("plan", "TEXT")
    ]
    for col_name, col_type in new_cols:
        if col_name not in columns:
            try:
                cursor.execute(f"ALTER TABLE inquiries ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass
    conn.commit()
    conn.close()

init_db()

def send_email_notification(inquiry_data):
    """
    Sends email notification via Resend API (if RESEND_API_KEY is configured),
    or SMTP (if SMTP_HOST is configured), or logs formatted email dispatch.
    """
    owner_email = os.environ.get("OWNER_EMAIL", "contactwithpiyush.01@gmail.com")
    resend_api_key = os.environ.get("RESEND_API_KEY", "").strip()
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background: #0B0B0D; color: #ffffff; padding: 20px; }}
            .card {{ background: #131317; border: 1px solid #222; border-radius: 12px; padding: 30px; max-width: 600px; margin: auto; }}
            h2 {{ color: #B6FF6A; border-bottom: 1px solid #333; padding-bottom: 12px; }}
            .field {{ margin-bottom: 12px; }}
            .label {{ font-weight: bold; color: #A1A1AA; }}
            .value {{ color: #ffffff; }}
            .box {{ background: #1A1A20; padding: 15px; border-radius: 8px; border-left: 3px solid #B6FF6A; margin-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>New Project Inquiry #{inquiry_data.get('id', '')}</h2>
            <div class="field"><span class="label">Client Name:</span> <span class="value">{inquiry_data.get('full_name')}</span></div>
            <div class="field"><span class="label">Email:</span> <span class="value">{inquiry_data.get('email')}</span></div>
            <div class="field"><span class="label">Phone:</span> <span class="value">{inquiry_data.get('phone')}</span></div>
            <div class="field"><span class="label">Company:</span> <span class="value">{inquiry_data.get('company', 'N/A')}</span></div>
            <div class="field"><span class="label">Service Required:</span> <span class="value">{inquiry_data.get('service')}</span></div>
            <div class="field"><span class="label">Selected Package:</span> <span class="value" style="color: #B6FF6A; font-weight: 700;">{inquiry_data.get('plan', 'Custom / General')}</span></div>
            <div class="field"><span class="label">Project Budget:</span> <span class="value">{inquiry_data.get('budget')}</span></div>
            <div class="field"><span class="label">Target Deadline:</span> <span class="value">{inquiry_data.get('deadline')}</span></div>
            <div class="field"><span class="label">Reference Website:</span> <span class="value">{inquiry_data.get('reference_url', 'None')}</span></div>
            <div class="field"><span class="label">File Attachment:</span> <span class="value">{inquiry_data.get('file_name', 'None')}</span></div>
            <div class="box">
                <span class="label">Project Details / Scope:</span><br>
                <p style="white-space: pre-wrap; color: #ffffff;">{inquiry_data.get('details')}</p>
            </div>
            <p style="margin-top: 25px; font-size: 0.85rem; color: #71717A;">Sent automatically from PIYUSHH Portfolio Hire Me Page.</p>
        </div>
    </body>
    </html>
    """

    email_result = {
        "sent": False,
        "provider": "logged_local",
        "message": "Saved to database and recorded in email dispatch log."
    }

    # 1. Check for Resend API Key
    if resend_api_key:
        try:
            req_data = json.dumps({
                "from": "PIYUSHH Portfolio <onboarding@resend.dev>",
                "to": [owner_email],
                "subject": f"Project Inquiry from {inquiry_data.get('full_name')} ({inquiry_data.get('service')})",
                "html": html_content
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.resend.com/emails",
                data=req_data,
                headers={
                    "Authorization": f"Bearer {resend_api_key}",
                    "Content-Type": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_text = resp.read().decode("utf-8")
                print(f"[RESEND SUCCESS]: {resp_text}", flush=True)
                email_result["sent"] = True
                email_result["provider"] = "Resend"
                email_result["message"] = f"Delivered to {owner_email} via Resend."
                return email_result
        except Exception as e:
            print(f"[RESEND ERROR]: {e}", flush=True)
            email_result["error"] = str(e)

    # 2. Check for SMTP Host
    smtp_host = os.environ.get("SMTP_HOST", "").strip()
    if smtp_host:
        try:
            smtp_port = int(os.environ.get("SMTP_PORT", 587))
            smtp_user = os.environ.get("SMTP_USER", "").strip()
            smtp_pass = os.environ.get("SMTP_PASS", "").strip()

            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Project Inquiry from {inquiry_data.get('full_name')} - {inquiry_data.get('service')}"
            msg["From"] = smtp_user or owner_email
            msg["To"] = owner_email
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)

            print(f"[SMTP SUCCESS]: Delivered to {owner_email}", flush=True)
            email_result["sent"] = True
            email_result["provider"] = "SMTP"
            email_result["message"] = f"Delivered to {owner_email} via SMTP."
            return email_result
        except Exception as e:
            print(f"[SMTP ERROR]: {e}", flush=True)
            email_result["error"] = str(e)

    # 3. Always log full notification
    print("\n" + "="*60, flush=True)
    print(f"[NEW INQUIRY DISPATCHED TO: {owner_email}]", flush=True)
    print(f"Full Name:        {inquiry_data.get('full_name')}", flush=True)
    print(f"Email:            {inquiry_data.get('email')}", flush=True)
    print(f"Phone:            {inquiry_data.get('phone')}", flush=True)
    print(f"Company:          {inquiry_data.get('company', 'N/A')}", flush=True)
    print(f"Service:          {inquiry_data.get('service')}", flush=True)
    print(f"Selected Plan:    {inquiry_data.get('plan', 'Custom / General')}", flush=True)
    print(f"Budget:           {inquiry_data.get('budget')}", flush=True)
    print(f"Deadline:         {inquiry_data.get('deadline')}", flush=True)
    print(f"Reference URL:    {inquiry_data.get('reference_url', 'None')}", flush=True)
    print(f"File Attachment:  {inquiry_data.get('file_name', 'None')}", flush=True)
    print(f"Project Details:  {inquiry_data.get('details')}", flush=True)
    print("="*60 + "\n", flush=True)

    return email_result

class PortfolioHandler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def address_string(self):
        # Eliminate blocking reverse DNS lookups on every request
        return str(self.client_address[0])

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Range, Authorization")
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_HEAD(self):
        parsed_url = urllib.parse.urlparse(self.path)
        clean_routes = {
            "/hire-me": "/hire-me.html",
            "/hire": "/hire-me.html",
            "/pricing": "/pricing.html",
            "/services": "/services.html",
            "/projects": "/projects.html",
            "/contact": "/hire-me.html",
            "/contact.html": "/hire-me.html",
            "/about": "/about.html"
        }
        if parsed_url.path in clean_routes:
            self.path = clean_routes[parsed_url.path]
        super().do_HEAD()

    def send_range_response(self, file_path, range_header):
        """
        Implements HTTP 206 Partial Content for video streaming and asset seeking.
        Prevents full file streaming when browsers only request metadata/chunks.
        """
        try:
            file_size = os.path.getsize(file_path)
            range_val = range_header.split("=")[1].strip()
            ranges = range_val.split("-")
            
            start_str = ranges[0].strip()
            end_str = ranges[1].strip() if len(ranges) > 1 else ""

            if start_str and end_str:
                start = int(start_str)
                end = int(end_str)
            elif start_str:
                start = int(start_str)
                end = file_size - 1
            elif end_str:
                start = max(0, file_size - int(end_str))
                end = file_size - 1
            else:
                start = 0
                end = file_size - 1

            if start < 0 or start >= file_size or end < start or end >= file_size:
                self.send_response(416, "Range Not Satisfiable")
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.end_headers()
                return

            length = end - start + 1
            content_type = self.guess_type(file_path)

            self.send_response(206, "Partial Content")
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()

            with open(file_path, "rb") as f:
                f.seek(start)
                bytes_to_send = length
                buf_size = 64 * 1024
                while bytes_to_send > 0:
                    chunk_size = min(bytes_to_send, buf_size)
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    bytes_to_send -= len(chunk)

        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            try:
                self.send_error(500, str(e))
            except Exception:
                pass

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        if parsed_url.path in ["/api/contact", "/api/hire"]:
            content_length = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_length).decode("utf-8")
            
            try:
                content_type = self.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    data = json.loads(post_body)
                else:
                    parsed = urllib.parse.parse_qs(post_body)
                    data = {k: v[0] for k, v in parsed.items()}
                
                full_name = data.get("fullName", "").strip()
                email = data.get("email", "").strip()
                phone = data.get("phone", data.get("whatsapp", "")).strip()
                company = data.get("company", "").strip()
                service = data.get("service", "").strip() or "General Inquiry"
                plan = data.get("plan", "").strip()
                budget = data.get("budget", "").strip() or "Flexible"
                deadline = data.get("deadline", "").strip() or "Flexible"
                details = data.get("details", data.get("message", "")).strip()
                reference_url = data.get("referenceUrl", "").strip()
                file_name = data.get("fileName", "").strip()
                file_data = data.get("fileData", "")

                # Save file attachment if provided
                saved_file_name = None
                if file_name and file_data:
                    try:
                        # Extract base64 part
                        if "," in file_data:
                            file_data = file_data.split(",")[1]
                        file_bytes = base64.b64decode(file_data)
                        safe_filename = f"{int(time.time())}_{os.path.basename(file_name)}"
                        file_path = os.path.join(UPLOAD_DIR, safe_filename)
                        with open(file_path, "wb") as f:
                            f.write(file_bytes)
                        saved_file_name = safe_filename
                    except Exception as fe:
                        print(f"[FILE SAVE ERROR]: {fe}", flush=True)
                        saved_file_name = file_name
                elif file_name:
                    saved_file_name = file_name

                if not full_name or not email or not phone or not details:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "success": False,
                        "error": "Please provide Full Name, Email Address, Phone Number, and Project Details."
                    }).encode("utf-8"))
                    return

                # Insert into database with safe connection handling
                conn = sqlite3.connect(DB_FILE, timeout=30.0)
                try:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA table_info(inquiries)")
                    cols = [c[1] for c in cursor.fetchall()]

                    insert_fields = ["full_name", "email", "service", "budget", "deadline", "reference_url", "file_name"]
                    insert_vals = [full_name, email, service, budget, deadline, reference_url, saved_file_name]

                    if "phone" in cols:
                        insert_fields.append("phone")
                        insert_vals.append(phone)
                    if "whatsapp" in cols:
                        insert_fields.append("whatsapp")
                        insert_vals.append(phone)
                    if "company" in cols:
                        insert_fields.append("company")
                        insert_vals.append(company)
                    if "details" in cols:
                        insert_fields.append("details")
                        insert_vals.append(details)
                    if "message" in cols:
                        insert_fields.append("message")
                        insert_vals.append(details)
                    if "plan" in cols and plan:
                        insert_fields.append("plan")
                        insert_vals.append(plan)

                    placeholders = ", ".join(["?"] * len(insert_fields))
                    field_str = ", ".join(insert_fields)
                    cursor.execute(f"INSERT INTO inquiries ({field_str}) VALUES ({placeholders})", tuple(insert_vals))
                    inquiry_id = cursor.lastrowid
                    conn.commit()
                finally:
                    conn.close()

                inquiry_record = {
                    "id": inquiry_id,
                    "full_name": full_name,
                    "email": email,
                    "phone": phone,
                    "company": company,
                    "service": service,
                    "plan": plan,
                    "budget": budget,
                    "deadline": deadline,
                    "details": details,
                    "reference_url": reference_url,
                    "file_name": saved_file_name
                }

                # Save to Supabase backend
                supabase_record = save_to_supabase(inquiry_record)
                if supabase_record:
                    inquiry_record["supabase_id"] = supabase_record.get("id")

                # Send email notification
                email_status = send_email_notification(inquiry_record)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                response_payload = {
                    "success": True,
                    "inquiryId": inquiry_id,
                    "supabaseId": inquiry_record.get("supabase_id"),
                    "savedToSupabase": bool(supabase_record),
                    "message": "Your project inquiry has been successfully submitted and stored in our Supabase backend. I will reach out to you within 24 hours!",
                    "emailStatus": email_status
                }
                self.wfile.write(json.dumps(response_payload).encode("utf-8"))

            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
            return

        super().do_POST()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        clean_routes = {
            "/hire-me": "/hire-me.html",
            "/hire": "/hire-me.html",
            "/pricing": "/pricing.html",
            "/services": "/services.html",
            "/projects": "/projects.html",
            "/contact": "/hire-me.html",
            "/contact.html": "/hire-me.html",
            "/about": "/about.html"
        }
        if parsed_url.path in clean_routes:
            self.path = clean_routes[parsed_url.path]

        if parsed_url.path == "/api/supabase-config":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "supabaseUrl": SUPABASE_URL,
                "anonKey": SUPABASE_ANON_KEY
            }).encode("utf-8"))
            return

        if parsed_url.path == "/api/inquiries":
            # Attempt to fetch directly from Supabase first
            supabase_inquiries = None
            try:
                url = f"{SUPABASE_URL}/rest/v1/inquiries?select=*&order=id.desc"
                headers = {
                    "apikey": SUPABASE_ANON_KEY,
                    "Authorization": f"Bearer {SUPABASE_ANON_KEY}"
                }
                req = urllib.request.Request(url, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=6) as resp:
                    raw_data = json.loads(resp.read().decode("utf-8"))
                    supabase_inquiries = []
                    for d in raw_data:
                        supabase_inquiries.append({
                            "id": d.get("id"),
                            "fullName": d.get("full_name"),
                            "email": d.get("email"),
                            "phone": d.get("phone"),
                            "company": d.get("company"),
                            "service": d.get("service"),
                            "plan": d.get("plan"),
                            "budget": d.get("budget"),
                            "deadline": d.get("deadline"),
                            "details": d.get("details"),
                            "referenceUrl": d.get("reference_url"),
                            "fileName": d.get("file_name"),
                            "createdAt": d.get("created_at"),
                            "source": "supabase"
                        })
            except Exception as se:
                print(f"[SUPABASE FETCH WARNING]: {se}", flush=True)

            if supabase_inquiries is not None:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(supabase_inquiries).encode("utf-8"))
                return

            # Fallback to local SQLite if Supabase unreachable
            conn = sqlite3.connect(DB_FILE, timeout=30.0)
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM inquiries ORDER BY id DESC")
                rows = cursor.fetchall()
                inquiries = []
                for r in rows:
                    d = dict(r)
                    inquiries.append({
                        "id": d.get("id"),
                        "fullName": d.get("full_name"),
                        "email": d.get("email"),
                        "phone": d.get("phone") or d.get("whatsapp"),
                        "company": d.get("company"),
                        "service": d.get("service"),
                        "plan": d.get("plan"),
                        "budget": d.get("budget"),
                        "deadline": d.get("deadline"),
                        "details": d.get("details") or d.get("message"),
                        "referenceUrl": d.get("reference_url"),
                        "fileName": d.get("file_name"),
                        "createdAt": d.get("created_at"),
                        "source": "sqlite_local"
                    })
            finally:
                conn.close()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(inquiries).encode("utf-8"))
            return

        # Check for Range header on video or large static files
        file_path = self.translate_path(self.path)
        range_header = self.headers.get("Range")
        if os.path.isfile(file_path) and range_header and range_header.startswith("bytes="):
            self.send_range_response(file_path, range_header)
            return

        super().do_GET()


class DualStackThreadingServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    address_family = socket.AF_INET6

    def server_bind(self):
        try:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except Exception:
            pass
        super().server_bind()


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    server_started = False
    
    # Try IPv6 Dual-Stack first (eliminates Windows localhost 2.2s SYN delay)
    try:
        httpd = DualStackThreadingServer(("", PORT), PortfolioHandler)
        server_started = True
        print(f"Dual-stack Portfolio server running on http://localhost:{PORT} (IPv4 + IPv6)...", flush=True)
    except Exception as e:
        print(f"Dual-stack IPv6 bind unavailable ({e}), falling back to Threading IPv4...", flush=True)

    if not server_started:
        httpd = http.server.ThreadingHTTPServer(("", PORT), PortfolioHandler)
        print(f"Threading Portfolio server running on http://localhost:{PORT}...", flush=True)

    with httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
