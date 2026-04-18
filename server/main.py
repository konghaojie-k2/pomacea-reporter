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


class RecordOut(Record):
    id: str
    createdAt: str

    class Config:
        json_schema_extra = {
            "example": {
                "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "lat": 31.2989,
                "lng": 120.6853,
                "note": "苏州金鸡湖东岸",
                "address": "苏州",
                "photo": None,
                "createdAt": "2026-04-18T12:00:00.000Z"
            }
        }


# ─── 工具函数 ──────────────────────────────────────────

def _load() -> list[dict]:
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(records: list[dict]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


# ─── FastAPI 应用 ───────────────────────────────────────

app = FastAPI(
    title="🐌 福寿螺上报 API",
    description="接收、存储和查询福寿螺发现记录",
    version="1.0.0",
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
    return {"status": "ok", "service": "pomacea-reporter", "version": "1.0.0"}


@app.get("/api/records", tags=["记录"], summary="查询所有记录")
def list_records():
    records = _load()
    return {"records": records, "total": len(records)}


@app.post("/api/records", response_model=RecordOut, tags=["记录"], summary="上报一条记录")
def create_record(record: Record):
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", ".000Z")
    entry = {
        "id": str(uuid.uuid4()),
        "lat": record.lat,
        "lng": record.lng,
        "note": record.note,
        "address": record.address,
        "photo": record.photo,
        "createdAt": now,
    }
    records = _load()
    records.append(entry)
    _save(records)
    return entry


@app.delete("/api/records/{record_id}", tags=["记录"], summary="删除记录")
def delete_record(record_id: str):
    records = _load()
    before = len(records)
    records = [r for r in records if r.get("id") != record_id]
    if len(records) == before:
        raise HTTPException(status_code=404, detail="记录不存在")
    _save(records)
    return {"success": True, "deleted": record_id}


# ─── 启动 ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=API_PORT, reload=True)
