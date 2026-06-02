"""
福寿螺上报平台 — API + 前端一体化服务
同时提供：
  /             → 前端 HTML 页面（举报+处理双端）
  /api/records → API 接口
数据库：SQLite（/data/pomacea.db）
"""

import json, uuid, os, sqlite3, time, mimetypes, re
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

PORT = 9000
DB_FILE = "/data/pomacea.db"
UPLOAD_DIR = "/data/uploads"
ALLOWED_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_UPLOAD_SIZE = 8 * 1024 * 1024  # 8MB

os.makedirs(UPLOAD_DIR, exist_ok=True)

# ─── 内嵌前端页面 ───────────────────────────────────
FRONTEND_HTML = open(os.path.join(os.path.dirname(__file__), "frontend.html"), encoding="utf-8").read()


# ─── 数据库初始化 ───────────────────────────────────

def _init_db():
    """初始化数据库表结构。SQLite 不支持 ALTER TABLE ADD PRIMARY KEY，
    所以对老库（缺少 id 等关键列）只能 DROP 重创。"""
    with sqlite3.connect(DB_FILE) as conn:
        # 先确保 records 表存在
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
        # 检查 schema 完整性：缺关键列则 DROP 重创（兼容旧版本残留）
        cols = {row[1] for row in conn.execute("PRAGMA table_info(records)").fetchall()}
        required = {"id", "lat", "lng", "note", "createdAt", "status"}
        missing = required - cols
        if missing:
            print(f"⚠️  检测到 records 表缺少列: {missing}，DROP 重创（数据会清空）")
            conn.execute("DROP TABLE records")
            conn.execute("""
                CREATE TABLE records (
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
            print("✅ records 表已重建")
        conn.commit()


def _now():
    # 返回合法的 ISO 8601 UTC 时间戳（毫秒精度，Z 结尾）
    # 之前 .replace("+00:00", ".000Z") 会拼出 "...000Z.000Z" 这种双小数，JS Date 解析不了 → NaN
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _cors():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


def _json(data, status=200):
    return status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json"


def handle_upload(body, content_type):
    """处理 multipart/form-data 上传，保存到 UPLOAD_DIR，返回 {"url": "..."}"""
    # 简单 multipart 解析（仅支持单文件）
    m = re.search(rb'boundary=([^;\s]+)', content_type.encode())
    if not m:
        return _json({"error": "需要 multipart/form-data"}, 400)
    boundary = b"--" + m.group(1)
    if len(body) > MAX_UPLOAD_SIZE:
        return _json({"error": f"文件超过 {MAX_UPLOAD_SIZE//1024//1024}MB"}, 413)

    parts = body.split(boundary)
    for part in parts:
        if b'filename="' not in part:
            continue
        # 解析文件
        header_end = part.find(b"\r\n\r\n")
        if header_end < 0:
            continue
        header = part[:header_end].decode("utf-8", errors="replace")
        file_bytes = part[header_end+4:]
        # 去掉末尾 \r\n
        if file_bytes.endswith(b"\r\n"):
            file_bytes = file_bytes[:-2]

        # 提取 Content-Type
        ct_m = re.search(r'Content-Type:\s*([^\r\n]+)', header, re.I)
        ct = ct_m.group(1).strip() if ct_m else "application/octet-stream"

        # 推断扩展名
        ext = ".jpg"
        if "png" in ct:
            ext = ".png"
        elif "webp" in ct:
            ext = ".webp"
        elif "gif" in ct:
            ext = ".gif"
        elif "jpeg" in ct or "jpg" in ct:
            ext = ".jpg"
        # 验证扩展名
        if ext not in ALLOWED_IMG_EXT:
            return _json({"error": f"不支持的图片格式: {ext}"}, 400)

        # 生成文件名
        fname = f"{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}{ext}"
        fpath = os.path.join(UPLOAD_DIR, fname)

        with open(fpath, "wb") as f:
            f.write(file_bytes)

        # 拼 URL（用 HOST 头推断）
        return _json({"url": f"/uploads/{fname}", "filename": fname, "size": len(file_bytes)})

    return _json({"error": "没找到文件"}, 400)


def serve_static(path):
    """从 UPLOAD_DIR 提供静态文件"""
    # 安全：禁止 .. 路径穿越
    rel = path.lstrip("/")
    if ".." in rel or rel.startswith("/"):
        return None
    fpath = os.path.join(UPLOAD_DIR, rel)
    if not os.path.isfile(fpath):
        return None
    ctype, _ = mimetypes.guess_type(fpath)
    ctype = ctype or "application/octet-stream"
    with open(fpath, "rb") as f:
        return f.read(), ctype


def _load_all():
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id,lat,lng,note,address,photo,reporterId,createdAt,status,handler,handleTime,feedback "
            "FROM records ORDER BY createdAt DESC"
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

    if p.startswith("/uploads/"):
        result = serve_static(p[len("/uploads/"):])
        if result:
            data, ctype = result
            return 200, data, ctype
        return 404, b'{"error":"not found"}', "application/json"

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
        ct = self.headers.get("Content-Type", "")
        # 上传端点需要把 Content-Type 也带过去（multipart 解析要 boundary）
        if urlparse(self.path).path == "/api/upload":
            s, b, c = handle_upload(body, ct)
        else:
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