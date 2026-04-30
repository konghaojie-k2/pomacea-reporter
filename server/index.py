"""
福寿螺上报平台 — API + 前端一体化服务
同时提供：
  /             → 前端 HTML 页面（举报+处理双端）
  /api/records → API 接口
数据库：SQLite（/data/pomacea.db）
"""

import json, uuid, os, sqlite3
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

PORT = 9000
DB_FILE = "/data/pomacea.db"

# ─── 内嵌前端页面 ───────────────────────────────────
FRONTEND_HTML = open(os.path.join(os.path.dirname(__file__), "frontend.html"), encoding="utf-8").read()


# ─── 数据库初始化 ───────────────────────────────────

def _init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id          TEXT PRIMARY KEY,
                lat         REAL NOT NULL,
                lng         REAL NOT NULL,
                note        TEXT NOT NULL,
                address     TEXT DEFAULT '',
                photo       TEXT DEFAULT '',
                reporterId  TEXT DEFAULT '',
                createdAt   TEXT NOT NULL,
                status      TEXT DEFAULT 'pending',
                handler     TEXT DEFAULT NULL,
                handleTime  TEXT DEFAULT NULL,
                feedback    TEXT DEFAULT NULL
            )
        """)


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", ".000Z")


def _cors():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


def _json(data, status=200):
    return status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json"


def _load_all():
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id,lat,lng,note,address,photo,reporterId,createdAt,status,handler,handleTime,feedback "
            "ORDER BY createdAt DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ─── 路由处理 ──────────────────────────────────────

def handle(req, path, body=b""):
    p = urlparse(path).path.rstrip("/")

    if p in ("", "/", "/index.html"):
        return 200, FRONTEND_HTML.encode("utf-8"), "text/html; charset=utf-8"

    if p in ("/api/records", "/api/records/") and req == "GET":
        return _json({"records": _load_all(), "total": len(_load_all())})

    if p in ("/api/records", "/api/records/") and req == "POST":
        return handle_create(body)

    if p.startswith("/api/records/") and req == "GET":
        rid = p.split("/")[-1]
        if not rid:
            return 404, '{"error":"记录不存在"}', "application/json"
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            r = conn.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
        return _json(dict(r)) if r else (404, '{"error":"记录不存在"}', "application/json")

    if p.startswith("/api/records/") and req in ("PATCH", "POST"):
        rid = p.split("/")[-1]
        if not rid:
            return 404, '{"error":"记录不存在"}', "application/json"
        if req == "POST":
            try:
                data = json.loads(body.decode("utf-8"))
                if data.get("_method") != "PATCH":
                    return 404, b'{"error":"Not Found"}', "application/json"
            except:
                return 404, b'{"error":"Not Found"}', "application/json"
        return handle_update(rid, body)

    if p.startswith("/api/records/") and req == "DELETE":
        rid = p.split("/")[-1]
        if not rid:
            return 404, '{"error":"记录不存在"}', "application/json"
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.execute("DELETE FROM records WHERE id=?", (rid,))
            deleted = cur.rowcount > 0
        return (404, '{"error":"记录不存在"}', "application/json") if not deleted else _json({"success": True, "deleted": rid})

    if p == "/api/stats" and req == "GET":
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.execute("SELECT status, COUNT(*) FROM records GROUP BY status").fetchall()
        counts = {row[0]: row[1] for row in cur}
        total = sum(counts.values())
        return _json({
            "total": total,
            "pending": counts.get("pending", 0),
            "processing": counts.get("processing", 0),
            "resolved": counts.get("resolved", 0),
            "resolutionRate": round(counts.get("resolved", 0) / total * 100, 1) if total else 0
        })

    return 404, b'{"error":"Not Found"}', "application/json"


def handle_create(body):
    try:
        data = json.loads(body.decode("utf-8"))
    except:
        return _json({"error": "无效 JSON"}, 400)
    lat, lng, note = data.get("lat"), data.get("lng"), data.get("note", "").strip()
    if lat is None or lng is None or not note:
        return _json({"error": "缺少必填字段：lat, lng, note"}, 400)
    try:
        lat, lng = float(lat), float(lng)
    except:
        return _json({"error": "lat/lng 必须为数字"}, 400)
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return _json({"error": "坐标超出范围"}, 400)
    record = {
        "id": str(uuid.uuid4()), "lat": lat, "lng": lng, "note": note,
        "address": data.get("address", "").strip(),
        "photo": data.get("photo", ""),
        "reporterId": data.get("reporterId", ""),
        "createdAt": _now(), "status": "pending",
    }
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT INTO records (id,lat,lng,note,address,photo,reporterId,createdAt,status) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (record["id"], record["lat"], record["lng"], record["note"],
             record["address"], record["photo"], record["reporterId"],
             record["createdAt"], record["status"])
        )
    return _json(record, 201)


def handle_update(rid, body):
    try:
        data = json.loads(body.decode("utf-8"))
    except:
        return _json({"error": "无效 JSON"}, 400)
    with sqlite3.connect(DB_FILE) as conn:
        r = conn.execute("SELECT id FROM records WHERE id=?", (rid,)).fetchone()
        if not r:
            return 404, '{"error":"记录不存在"}', "application/json"
        updates, args = [], []
        if "status" in data:
            if data["status"] not in {"pending", "processing", "resolved"}:
                return _json({"error": "无效状态"}, 400)
            updates.append("status=?")
            args.append(data["status"])
        if data.get("handler"):
            updates.append("handler=?")
            args.append(data["handler"])
        if "feedback" in data:
            updates.append("feedback=?")
            args.append(data["feedback"])
        updates.append("handleTime=?")
        args.append(_now())
        args.append(rid)
        conn.execute(f"UPDATE records SET {', '.join(updates)} WHERE id=?", args)
        conn.row_factory = sqlite3.Row
        updated = conn.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
    return _json(dict(updated))


# ─── HTTP 服务 ───────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def _respond(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        for k, v in _cors().items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        s, b, c = handle("GET", self.path)
        self._respond(s, b, c)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b""
        s, b, c = handle("POST", self.path, body)
        self._respond(s, b, c)

    def do_PATCH(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b""
        s, b, c = handle("PATCH", self.path, body)
        self._respond(s, b, c)

    def do_DELETE(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b""
        s, b, c = handle("DELETE", self.path, body)
        self._respond(s, b, c)

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in _cors().items():
            self.send_header(k, v)
        self.end_headers()

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {args[0]}")


# ─── 启动 ───────────────────────────────────────────

if __name__ == "__main__":
    _init_db()
    print(f"🐌 福寿螺平台启动！")
    print(f"   前后端: http://0.0.0.0:{PORT}/")
    print(f"   数据库: {DB_FILE}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()