"""
福寿螺上报平台 — API 服务端
FastAPI + JSON 文件存储（无需数据库）
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import uuid
import json
import os
from datetime import datetime, timezone

# ─── 配置 ────────────────────────────────────────────
DATA_FILE = os.getenv("DATA_FILE", "records.json")
API_PORT = int(os.getenv("API_PORT", "3001"))

# ─── 数据模型 ──────────────────────────────────────────

class Record(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="纬度")
    lng: float = Field(..., ge=-180, le=180, description="经度")
    note: str = Field(..., min_length=1, description="描述")
    photo: Optional[str] = Field(None, description="Base64 图片或 URL")
    address: Optional[str] = Field(None, description="地址描述")
    reporterId: Optional[str] = Field(None, description="举报人 ID（飞书 open_id）")


class RecordOut(Record):
    id: str
    createdAt: str
    status: str = "pending"
    handler: Optional[str] = Field(None, description="处理人名称")
    handleTime: Optional[str] = Field(None, description="处理时间")
    feedback: Optional[str] = Field(None, description="处理反馈说明")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "lat": 31.2989,
                "lng": 120.6853,
                "note": "苏州金鸡湖东岸",
                "address": "苏州",
                "photo": None,
                "reporterId": "ou_xxx",
                "status": "pending",
                "handler": None,
                "handleTime": None,
                "feedback": None,
                "createdAt": "2026-04-18T12:00:00.000Z"
            }
        }


class HandleUpdate(BaseModel):
    """处理状态更新"""
    status: str = Field(..., description="状态: pending → processing → resolved")
    handler: Optional[str] = Field(None, description="处理人名称")
    feedback: Optional[str] = Field(None, description="处理说明")


# ─── 工具函数 ──────────────────────────────────────────

def _load() -> list[dict]:
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(records: list[dict]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", ".000Z")


# ─── FastAPI 应用 ───────────────────────────────────────

app = FastAPI(
    title="🐌 福寿螺上报 API",
    description="接收、存储、查询和处理福寿螺发现记录",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["健康检查"])
def root():
    return {
        "status": "ok",
        "service": "pomacea-reporter",
        "version": "2.0.0",
        "features": ["上报", "查询", "处理反馈"]
    }


# ─── 记录接口 ──────────────────────────────────────────

@app.get("/api/records", tags=["记录"], summary="查询所有记录（可按状态过滤）")
def list_records(status: Optional[str] = None):
    """
    查询记录，支持按 status 过滤：
    - pending：待处理
    - processing：处理中
    - resolved：已处理
    """
    records = _load()
    if status:
        records = [r for r in records if r.get("status") == status]
    # 按时间倒序
    records.sort(key=lambda r: r.get("createdAt", ""), reverse=True)
    return {" records": records, "total": len(records)}


@app.get("/api/records/{record_id}", response_model=RecordOut, tags=["记录"], summary="查询单条记录")
def get_record(record_id: str):
    records = _load()
    for r in records:
        if r.get("id") == record_id:
            return r
    raise HTTPException(status_code=404, detail="记录不存在")


@app.post("/api/records", response_model=RecordOut, tags=["记录"], summary="上报一条记录")
def create_record(record: Record):
    entry = {
        "id": str(uuid.uuid4()),
        "lat": record.lat,
        "lng": record.lng,
        "note": record.note,
        "address": record.address,
        "photo": record.photo,
        "reporterId": record.reporterId,
        "createdAt": _now(),
        "status": "pending",
        "handler": None,
        "handleTime": None,
        "feedback": None,
    }
    records = _load()
    records.insert(0, entry)
    _save(records)
    return entry


@app.patch("/api/records/{record_id}", response_model=RecordOut, tags=["处理"], summary="更新处理状态")
def update_record(record_id: str, update: HandleUpdate):
    """
    处理一条记录（政府/志愿者操作）：
    - status: pending → processing → resolved
    - handler: 处理人名称
    - feedback: 处理说明（如：已清理、已撒药等）
    """
    valid_status = {"pending", "processing", "resolved"}
    if update.status not in valid_status:
        raise HTTPException(status_code=400, detail=f"status 必须为 {valid_status} 之一")

    records = _load()
    for r in records:
        if r.get("id") == record_id:
            r["status"] = update.status
            if update.handler:
                r["handler"] = update.handler
            if update.feedback:
                r["feedback"] = update.feedback
            r["handleTime"] = _now()
            _save(records)
            return r

    raise HTTPException(status_code=404, detail="记录不存在")


@app.delete("/api/records/{record_id}", tags=["记录"], summary="删除记录")
def delete_record(record_id: str):
    records = _load()
    before = len(records)
    records = [r for r in records if r.get("id") != record_id]
    if len(records) == before:
        raise HTTPException(status_code=404, detail="记录不存在")
    _save(records)
    return {"success": True, "deleted": record_id}


# ─── 统计接口 ──────────────────────────────────────────

@app.get("/api/stats", tags=["统计"], summary="汇总统计")
def stats():
    records = _load()
    total = len(records)
    pending = sum(1 for r in records if r.get("status") == "pending")
    processing = sum(1 for r in records if r.get("status") == "processing")
    resolved = sum(1 for r in records if r.get("status") == "resolved")
    return {
        "total": total,
        "pending": pending,
        "processing": processing,
        "resolved": resolved,
        "resolutionRate": round(resolved / total * 100, 1) if total > 0 else 0
    }


# ─── 启动 ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=API_PORT, reload=True)
