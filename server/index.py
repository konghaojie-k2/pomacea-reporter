"""
福寿螺上报平台 — 阿里云函数计算适配版
=======================================
支持标准 HTTP 触发器，无需任何第三方依赖
纯标准库编写，兼容阿里云/腾讯云/所有 Serverless 平台

部署方式：
  1. 压缩所有 .py 文件为 zip
  2. 上传到阿里云函数计算，创建 HTTP 触发器
  3. 拿到 URL 后替换 web/index.html 中的 API_BASE
"""

import json
import os
import uuid
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ─── 数据文件路径（函数计算的 /tmp 目录） ───────────────────────────────────
DATA_FILE = "/tmp/records.json"
PORT = 9000

# ─── 工具函数 ──────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", ".000Z")

def _load() -> list:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def _save(records: list) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Content-Type": "application/json; charset=utf-8",
    }

def _json_response(data: dict, status: int = 200) -> tuple:
    return (status, json.dumps(data, ensure_ascii=False))

# ─── 路由处理 ──────────────────────────────────────────────────────────────

def handle_get(path: str) -> tuple:
    """GET 请求处理"""
    parsed = urlparse(path)
    path = parsed.path.rstrip("/")

    if path == "/api/records" or path == "/api/records/":
        records = _load()
        records.sort(key=lambda r: r.get("createdAt", ""), reverse=True)
        return _json_response({"records": records, "total": len(records)})

    if path.startswith("/api/records/"):
        record_id = path.split("/")[-1]
        records = _load()
        for r in records:
            if r.get("id") == record_id:
                return _json_response(r)
        return _json_response({"error": "记录不存在"}, 404)

    if path == "/api/stats" or path == "/api/stats/":
        records = _load()
        total = len(records)
        pending = sum(1 for r in records if r.get("status") == "pending")
        processing = sum(1 for r in records if r.get("status") == "processing")
        resolved = sum(1 for r in records if r.get("status") == "resolved")
        return _json_response({
            "total": total, "pending": pending,
            "processing": processing, "resolved": resolved,
            "resolutionRate": round(resolved / total * 100, 1) if total > 0 else 0
        })

    if path == "/" or path == "":
        return _json_response({
            "status": "ok", "service": "pomacea-reporter",
            "version": "2.0.0", "features": ["上报", "查询", "处理反馈"]
        })

    return _json_response({"error": "Not Found"}, 404)


def handle_post(path: str, body: bytes) -> tuple:
    """POST 请求处理"""
    try:
        data = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return _json_response({"error": "无效的 JSON 格式"}, 400)

    parsed = urlparse(path)
    path = parsed.path.rstrip("/")

    # POST /api/records — 新增记录
    if path == "/api/records" or path == "/api/records/":
        lat = data.get("lat")
        lng = data.get("lng")
        note = data.get("note", "").strip()

        if lat is None or lng is None or not note:
            return _json_response({"error": "缺少必填字段：lat, lng, note"}, 400)

        try:
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError):
            return _json_response({"error": "lat 和 lng 必须为数字"}, 400)

        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return _json_response({"error": "坐标超出合法范围"}, 400)

        record = {
            "id": str(uuid.uuid4()),
            "lat": lat,
            "lng": lng,
            "note": note,
            "address": data.get("address", "").strip(),
            "photo": data.get("photo", ""),
            "reporterId": data.get("reporterId", ""),
            "createdAt": _now(),
            "status": "pending",
            "handler": None,
            "handleTime": None,
            "feedback": None,
        }
        records = _load()
        records.insert(0, record)
        _save(records)
        return _json_response(record, 201)

    # PATCH /api/records/:id — 更新状态
    if path.startswith("/api/records/") and "PATCH" not in path:
        # 实际 PATCH 走 POST + _method=PATCH
        pass

    return _json_response({"error": "Not Found"}, 404)


def handle_patch(path: str, body: bytes) -> tuple:
    """PATCH 请求处理"""
    try:
        data = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return _json_response({"error": "无效的 JSON"}, 400)

    if path.startswith("/api/records/"):
        record_id = path.split("/")[-1]
        records = _load()
        for r in records:
            if r.get("id") == record_id:
                valid_status = {"pending", "processing", "resolved"}
                new_status = data.get("status")
                if new_status and new_status not in valid_status:
                    return _json_response({"error": f"status 必须为 {valid_status} 之一"}, 400)
                if new_status:
                    r["status"] = new_status
                if data.get("handler"):
                    r["handler"] = data["handler"]
                if "feedback" in data:
                    r["feedback"] = data["feedback"]
                r["handleTime"] = _now()
                _save(records)
                return _json_response(r)
        return _json_response({"error": "记录不存在"}, 404)

    return _json_response({"error": "Not Found"}, 404)


def handle_delete(path: str) -> tuple:
    """DELETE 请求处理"""
    if path.startswith("/api/records/"):
        record_id = path.split("/")[-1]
        records = _load()
        before = len(records)
        records = [r for r in records if r.get("id") != record_id]
        if len(records) == before:
            return _json_response({"error": "记录不存在"}, 404)
        _save(records)
        return _json_response({"success": True, "deleted": record_id})
    return _json_response({"error": "Not Found"}, 404)


# ─── HTTP 处理 ──────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        status, body = handle_get(self.path)
        self.send_response(status)
        for k, v in _cors_headers().items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b""

        # 支持通过 POST _method=PATCH 做模拟 PATCH
        if self.path.startswith("/api/records/"):
            try:
                data = json.loads(body.decode("utf-8"))
                if data.get("_method") == "PATCH":
                    status, resp_body = handle_patch(self.path, body)
                    self.send_response(status)
                    for k, v in _cors_headers().items():
                        self.send_header(k, v)
                    self.end_headers()
                    self.wfile.write(resp_body.encode("utf-8"))
                    return
            except Exception:
                pass

        status, body = handle_post(self.path, body)
        self.send_response(status)
        for k, v in _cors_headers().items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_PATCH(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b""
        status, resp_body = handle_patch(self.path, body)
        self.send_response(status)
        for k, v in _cors_headers().items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(resp_body.encode("utf-8"))

    def do_DELETE(self):
        status, body = handle_delete(self.path)
        self.send_response(status)
        for k, v in _cors_headers().items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in _cors_headers().items():
            self.send_header(k, v)
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {args[0]}")


# ─── 入口 ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"🐌 Pomacea API 启动于 http://0.0.0.0:{PORT}")
    server.serve_forever()
