---
name: pomacea-reporter
description: >
  福寿螺（入侵物种）发现记录上报技能。
  当用户提供福寿螺/福寿螺卵的发现位置（文字描述、定位或照片）时，
  自动提取坐标并提交到福寿螺分布地图平台。
  Triggered when user reports a pomacea snail (apple snail) sighting with location and/or photo.
homepage: https://github.com/konghaojie-k2/pomacea-reporter
metadata:
  language: zh
  version: "1.0.0"
  tags:
    - 环保
    - 生态
    - 上报
    - 地图
    - 入侵物种
    - 福寿螺
    - 农业
  emoji: "🐌"
  license: MIT
---

# 🐌 pomacea-reporter | 福寿螺上报技能

接入福寿螺分布地图平台，供 AI 助手快速完成发现记录上报。

> ⚠️ **福寿螺是世界自然基金会认定的全球 100 种最具破坏力入侵物种之一**，繁殖能力极强，一只雌螺每年可产卵 2000~5000 颗。举报有助于构建分布地图，支撑精准治理。

---

## API 信息

> ⚠️ **后端需单独部署**（免费，推荐 Render）：
> 1. 登录 [render.com](https://render.com) → GitHub 登录
> 2. New → Web Service → 选 `konghaojie-k2/pomacea-reporter`
> 3. Build Command: `pip install -r server/requirements.txt`
> 4. Start Command: `gunicorn server.main:app --bind 0.0.0.0:$PORT`
> 5. 部署完成后将下方 `API_BASE` 替换为 `.onrender.com` 地址

| 环境 | 地址 |
|------|------|
| **生产 API** | `https://你的渲染地址.onrender.com/api`（部署后填入） |
| **本地开发** | `http://localhost:3001/api` |

**API_BASE 变量名：** 部署后把 `https://xxx.onrender.com/api` 填入 SKILL.md 和 web/index.html 的 API 常量中。

---

## 接口规范

### POST /records — 上报记录

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `lat` | number | ✅ | 纬度，范围 [-90, 90]，例：31.2989 |
| `lng` | number | ✅ | 经度，范围 [-180, 180]，例：120.6853 |
| `note` | string | ✅ | 简短描述，例："苏州金鸡湖边草地" |
| `address` | string | ❌ | 结构化地址，例："苏州市金鸡湖" |
| `photo` | string | ❌ | Base64 图片（`data:image/jpeg;base64,...`）或公开 URL |

**响应 200：**

```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "lat": 31.2989,
  "lng": 120.6853,
  "note": "苏州金鸡湖东岸",
  "address": "苏州工业园区",
  "createdAt": "2026-04-18T12:00:00.000Z"
}
```

**错误响应：**

```json
{ "error": "缺少必填字段：lat, lng, note" }
```

---

### GET /records — 查询记录

```
GET /records
```

**响应 200：**

```json
{
  "records": [
    {
      "id": "uuid",
      "lat": 31.2989,
      "lng": 120.6853,
      "note": "苏州金鸡湖",
      "address": "苏州",
      "createdAt": "2026-04-18T12:00:00Z"
    }
  ],
  "total": 1
}
```

---

### DELETE /records/:id — 删除记录

```
DELETE /records/:id
```

**响应 200：**

```json
{ "success": true }
```

---

## 接入流程（3步）

### Step 1 — 识别意图

当用户发送以下内容时激活本技能：

- 🖼️ **照片** + 文字含：福寿螺、螺、上报、发现
- 📍 **定位消息** + 文字含：福寿螺、螺
- ✏️ **纯文字**：发现福寿螺、这里有螺、新点上报

### Step 2 — 提取信息

| 信息 | 优先级 | 提取方式 |
|------|--------|---------|
| GPS 坐标 | 高 | 飞书 geo 字段 > 文本经纬度正则 > 高德逆地理编码 |
| 图片 | 中 | 消息图片 key → 下载 → Base64 |
| 描述文字 | 高 | 用户消息提取，无则询问 |
| 地址 | 低 | 用户提供或逆地理编码反推 |

**经纬度正则匹配：**

```regex
# 十进制格式
(\d+\.?\d*)[°]?\s*[，,]\s*(\d+\.?\d*)    # "31.23, 120.45" 或 "31.23，120.45"

# 方向格式
(\d+\.?\d*)[°]?\s*[NS]\s*[，,]\s*(\d+\.?\d*)[°]?\s*[EW]
```

**高德逆地理编码（如需）：**

```
GET https://restapi.amap.com/v3/geocode/regeo?key={AMAP_KEY}&location={lng},{lat}
```

### Step 3 — 调用 API 上报

```bash
curl -X POST https://ew35zvt7xrey.space.minimaxi.com/api/records \
  -H "Content-Type: application/json" \
  -d '{
    "lat": 31.2989,
    "lng": 120.6853,
    "note": "苏州金鸡湖东岸草地",
    "address": "苏州市苏州工业园区金鸡湖"
  }'
```

---

## 回复模板

### ✅ 上报成功

```
🐌 福寿螺发现点已记录！

📍 位置：{address}
📝 描述：{note}
📷 照片：已保存（如有）
🗓️ 时间：{createdAt}

🌐 地图查看：https://ew35zvt7xrey.space.minimaxi.com
```

### ⚠️ 缺少定位

```
📸 收到你的上报！

要完成记录，请提供定位信息：
• 发送飞书定位消息（推荐）
• 或直接描述位置（如：苏州金鸡湖边）
```

### ⚠️ 缺少描述

```
📍 定位已获取！

最后请补充一下简单描述（可选）：
• 发现地点的环境（如：湖边草地、水塘旁）
• 或直接发送"完成"跳过
```

---

## 注意事项

1. `lat` 必须为 `-90~90`，`lng` 必须为 `-180~180`
2. 优先使用 URL 而非 Base64 以节省体积
3. 无照片也可上报，照片非必填
4. 平台公开可写，建议回复用户时附带记录 `id` 以便撤回
5. 坐标优先使用 WGS84 坐标系（GPS 标准）

---

## 相关资源

- 🗺️ 地图展示：[https://ew35zvt7xrey.space.minimaxi.com](https://ew35zvt7xrey.space.minimaxi.com)
- 📦 前端源码：[https://github.com/konghaojie-k2/pomacea-tracker](https://github.com/konghaojie-k2/pomacea-tracker)
- 🐛 问题反馈：[GitHub Issues](https://github.com/konghaojie-k2/pomacea-reporter/issues)
