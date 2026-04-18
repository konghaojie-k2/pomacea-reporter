"""
福寿螺上报平台 — API + 前端一体化服务
同时提供：
  /             → 前端 HTML 页面（举报+处理双端）
  /api/records → API 接口
"""

import json, uuid, os
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

PORT = 9000
DATA_FILE = "/tmp/records.json"

# ─── 内嵌前端页面 ───────────────────────────────────
FRONTEND_HTML = open(os.path.join(os.path.dirname(__file__), "frontend.html"), encoding="utf-8").read()


# ─── 工具函数 ───────────────────────────────────────

def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", ".000Z")

def _load():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def _save(records):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

def _cors():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }

def _json(data, status=200):
    return status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json"


# ─── 路由处理 ──────────────────────────────────────

def handle(req, path, body=b""):
    p = urlparse(path).path.rstrip("/")

    # 前端页面
    if p in ("/", "/index.html"):
        return 200, FRONTEND_HTML.encode("utf-8"), "text/html; charset=utf-8"

    # GET /api/records
    if p in ("/api/records", "/api/records/") and req == "GET":
        records = _load()
        records.sort(key=lambda r: r.get("createdAt", ""), reverse=True)
        return _json({"records": records, "total": len(records)})

    # POST /api/records
    if p in ("/api/records", "/api/records/") and req == "POST":
        return handle_create(body)

    # GET /api/records/:id
    if p.startswith("/api/records/") and req == "GET":
        record_id = p.split("/")[-1]
        for r in _load():
            if r.get("id") == record_id:
                return _json(r)
        return 404, b'{"error":"记录不存在"}', "application/json"

    # PATCH /api/records/:id  或  POST /api/records/:id (_method=PATCH)
    if p.startswith("/api/records/") and req in ("PATCH", "POST"):
        record_id = p.split("/")[-1]
        if req == "POST":
            try:
                data = json.loads(body.decode("utf-8"))
                if data.get("_method") != "PATCH":
                    return 404, b'{"error":"Not Found"}', "application/json"
            except:
                return 404, b'{"error":"Not Found"}', "application/json"
        return handle_update(record_id, body)

    # DELETE /api/records/:id
    if p.startswith("/api/records/") and req == "DELETE":
        record_id = p.split("/")[-1]
        records = _load()
        before = len(records)
        records = [r for r in records if r.get("id") != record_id]
        if len(records) == before:
            return 404, b'{"error":"记录不存在"}', "application/json"
        _save(records)
        return _json({"success": True, "deleted": record_id})

    # GET /api/stats
    if p == "/api/stats" and req == "GET":
        records = _load()
        total = len(records)
        pending = sum(1 for r in records if r.get("status") == "pending")
        processing = sum(1 for r in records if r.get("status") == "processing")
        resolved = sum(1 for r in records if r.get("status") == "resolved")
        return _json({
            "total": total, "pending": pending,
            "processing": processing, "resolved": resolved,
            "resolutionRate": round(resolved / total * 100, 1) if total else 0
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
        "createdAt": _now(),
        "status": "pending", "handler": None,
        "handleTime": None, "feedback": None,
    }
    records = _load()
    records.insert(0, record)
    _save(records)
    return _json(record, 201)


def handle_update(record_id, body):
    try:
        data = json.loads(body.decode("utf-8"))
    except:
        return _json({"error": "无效 JSON"}, 400)
    records = _load()
    for r in records:
        if r.get("id") == record_id:
            if "status" in data:
                if data["status"] not in {"pending", "processing", "resolved"}:
                    return _json({"error": "无效状态"}, 400)
                r["status"] = data["status"]
            if data.get("handler"):
                r["handler"] = data["handler"]
            if "feedback" in data:
                r["feedback"] = data["feedback"]
            r["handleTime"] = _now()
            _save(records)
            return _json(r)
    return 404, b'{"error":"记录不存在"}', "application/json"


# ─── HTTP 服务 ───────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        s, b, c = handle("GET", self.path)
        self.send_response(s)
        self.send_header("Content-Type", c)
        [self.send_header(k, v) for k, v in _cors().items()]
        self.end_headers()
        if b:
            self.wfile.write(b)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b""
        s, b, c = handle("POST", self.path, body)
        self.send_response(s)
        self.send_header("Content-Type", c)
        [self.send_header(k, v) for k, v in _cors().items()]
        self.end_headers()
        if b:
            self.wfile.write(b)

    def do_PATCH(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b""
        s, b, c = handle("PATCH", self.path, body)
        self.send_response(s)
        self.send_header("Content-Type", c)
        [self.send_header(k, v) for k, v in _cors().items()]
        self.end_headers()
        if b:
            self.wfile.write(b)

    def do_DELETE(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b""
        s, b, c = handle("DELETE", self.path, body)
        self.send_response(s)
        self.send_header("Content-Type", c)
        [self.send_header(k, v) for k, v in _cors().items()]
        self.end_headers()
        if b:
            self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(204)
        [self.send_header(k, v) for k, v in _cors().items()]
        self.end_headers()

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {args[0]}")


# ─── 启动 ───────────────────────────────────────────

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"🐌 福寿螺平台启动！")
    print(f"   前后端一体: http://0.0.0.0:{PORT}/")
    print(f"   API 接口:    http://0.0.0.0:{PORT}/api/records")
    server.serve_forever()
