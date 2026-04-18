# 🐌 Pomacea Reporter | 福寿螺智能举报系统

<div align="center">

![Pomacea Snail](https://img.shields.io/badge/福寿螺-举报系统-blue?style=for-the-badge)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/konghaojie-k2/pomacea-reporter?style=for-the-badge)](https://github.com/konghaojie-k2/pomacea-reporter)
[![Python](https://img.shields.io/badge/Python-3.11+-yellow?style=for-the-badge)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-支持快速接入-red?style=for-the-badge)](https://fastapi.tiangolo.com)

**让每一次福寿螺发现，都能成为生态守护的力量** 🌿

[English](README_EN.md) · [中文](README.md) · [快速开始](#-快速开始) · [为什么举报](#-为什么要举报福寿螺) · [API 文档](#-api-文档)

</div>

---

## 🌿 为什么要举报福寿螺？

<div align="center">

| 危害维度 | 具体危害 | 严重程度 |
|---------|---------|---------|
| 🌾 **农业** | 危害水稻、莲藕等粮食作物，造成大幅减产 | ⚠️⚠️⚠️⚠️⚠️ |
| 🌱 **生态** | 挤压本土螺类生存空间，破坏湿地生态平衡 | ⚠️⚠️⚠️⚠️ |
| 🏥 **健康** | 携带广州管圆线虫（ rat lungworm），引发脑膜炎 | ⚠️⚠️⚠️⚠️⚠️ |
| 💰 **经济** | 水产养殖损失，每年全球损失超数十亿美元 | ⚠️⚠️⚠️ |

</div>

### 什么是福寿螺？

福寿螺（*Pomacea canaliculata*）原产于南美洲淡水湿地，是 **世界自然基金会（WWF）认定的全球 100 种最具破坏力入侵物种之一**，也是我国 **《中国外来入侵物种名单》** 常驻物种。

福寿螺繁殖能力惊人：

> 🐌 一只成年雌螺 **每年可产卵 2,000~5,000 颗**，粉红色的卵块清晰可见于水面以上的植物茎秆上

### 举报的意义

福寿螺的扩散速度远超人工清理速度。**每一次举报，都是在帮助构建分布地图**，让管理部门和生态志愿者能够：

- 📍 **精准定位**：快速锁定福寿螺分布热点
- 📊 **趋势分析**：追踪扩散趋势，提前预警
- 🎯 **靶向治理**：将有限资源集中在高发区域
- 🌱 **生态修复**：评估修复效果，验证治理成果

---

## 🚀 快速开始

### 前置依赖

```bash
Python 3.11+
Node.js 18+
pnpm 8+
```

### 1. 克隆项目

```bash
git clone https://github.com/konghaojie-k2/pomacea-reporter.git
cd pomacea-reporter
```

### 2. 启动后端 API

```bash
cd server
pip install fastapi uvicorn
uvicorn main:app --reload --port 3001
```

### 3. 启动地图展示（前端）

```bash
cd ..
pnpm install
pnpm dev
```

> 或者用 Docker 一键启动：
> ```bash
> docker-compose up -d
> ```

---

## 🤖 接入 AI 助手（SKILL.md）

本项目提供标准化的 **SKILL.md**，任何支持 Skill 协议的消费级 AI 助手都可以直接接入：

```bash
# 复制技能文件到 AI 助手的 skills 目录
cp pomacea-reporter/SKILL.md /path/to/your/ai-assistant/skills/
```

接入后，用户只需对 AI 说：

```
"我在XX湖边发现了福寿螺"
"这里有好多粉色的螺卵" + 发送定位
```

AI 助手自动完成 **坐标提取 → 上报 → 确认回复** 全流程。

详细协议见 [SKILL.md](SKILL.md)。

---

## 🗺️ API 文档

### 基础信息

- **生产地址**：`https://ew35zvt7rey.space.minimaxi.com/api`
- **本地地址**：`http://localhost:3001/api`

### 上报记录

```
POST /records
Content-Type: application/json
```

```json
{
  "lat": 31.2989,
  "lng": 120.6853,
  "note": "苏州金鸡湖东岸草地，发现大量螺卵",
  "address": "苏州市苏州工业园区金鸡湖",
  "photo": "data:image/jpeg;base64,/9j/4AAQ..."
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `lat` | number | ✅ | 纬度，范围 [-90, 90] |
| `lng` | number | ✅ | 经度，范围 [-180, 180] |
| `note` | string | ✅ | 简单描述 |
| `photo` | string | ❌ | Base64 或公开图片 URL |
| `address` | string | ❌ | 地址描述 |

**响应示例：**

```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "lat": 31.2989,
  "lng": 120.6853,
  "note": "苏州金鸡湖东岸草地",
  "address": "苏州市苏州工业园区",
  "createdAt": "2026-04-18T12:00:00.000Z"
}
```

### 查询记录

```
GET /records
```

### 删除记录

```
DELETE /records/:id
```

---

## 🎨 地图展示

上报数据会在地图上实时可视化展示：

![Map Screenshot](https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&q=80)

**功能特性：**

- 🗺️ 交互式地图，查看所有举报点
- 📍 点击标记查看详情（照片+描述+时间）
- 🔴 热力图层，直观显示福寿螺高发区域
- 📱 支持移动端，随时随地举报

---

## 📂 项目结构

```
pomacea-reporter/
├── README.md              # 本文件
├── README_EN.md           # English version
├── LICENSE                # MIT License
├── SKILL.md              # AI 助手技能定义文件 ⭐
├── server/
│   ├── main.py           # FastAPI 后端服务
│   ├── models.py         # 数据模型
│   └── records.json      # 数据存储（SQLite 可选）
├── web/                  # 前端地图展示
│   ├── index.html
│   ├── map.js
│   └── style.css
├── docker-compose.yml     # Docker 一键部署
└── docs/
    ├── INSTALL.md        # 详细安装指南
    └── API.md            # API 完整文档
```

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

### 举报问题

- 🐛 发现 Bug → [提交 Issue](https://github.com/konghaojie-k2/pomacea-reporter/issues)
- ✨ 希望增加功能 → [提交 Feature Request](https://github.com/konghaojie-k2/pomacea-reporter/issues)
- 📖 完善文档 → 直接提交 PR

### 本地开发

```bash
# Fork 本仓库
# 克隆你的 Fork
git clone https://github.com/YOUR_USERNAME/pomacea-reporter.git

# 创建特性分支
git checkout -b feature/your-feature

# 开发完成后提交 PR
```

---

## 📜 开源许可

本项目基于 [MIT License](LICENSE) 开源。

---

## 🙏 致谢

- 项目灵感来自生态志愿者和环保工作者的实际需求
- 地图可视化基于 [高德地图](https://lbs.amap.com/) / [Leaflet](https://leafletjs.com/)
- AI 助手框架基于 [OpenClaw](https://github.com/openclaw/openclaw)
- 向所有在入侵物种治理一线工作的人们致敬

---

<div align="center">

**每一次发现，都值得被记录** 🌱

**Every sighting matters** 🐌

</div>
