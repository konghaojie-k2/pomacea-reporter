# 阿里云部署指南（无需信用卡）

## 方案一：阿里云 ECS 云服务器（推荐，有免费试用）

### 1. 领取免费试用
- 登录 [阿里云免费试用](https://free.aliyun.com/)
- 领取 **ECS 云服务器（轻量应用服务器）** 1~3 个月免费
- 或购买 **轻量应用服务器**（最便宜约 ¥24/月，带宽 1Mbps）

### 2. 连接服务器
```bash
ssh root@你的服务器IP
```

### 3. 上传代码（约 1 分钟）
在本地执行（先把 `server-deploy.tar.gz` 下载到电脑）：
```bash
scp server-deploy.tar.gz root@你的IP:/root/
```

### 4. 解压运行（服务器上执行）
```bash
# 解压
cd /root
tar -xzf server-deploy.tar.gz

# 运行（后台启动，端口 9000）
nohup python3 /root/server/index.py > api.log 2>&1 &

# 验证是否启动成功
curl http://localhost:9000/
# 返回 {"status": "ok", "service": "pomacea-reporter"...} 即成功
```

### 5. 配置防火墙
在阿里云控制台 → **安全组** → 添加规则：
- 端口：9000
- 协议：TCP
- 来源：0.0.0.0/0

### 6. 获取公网地址
```
http://你的服务器IP:9000/api
```

---

## 方案二：阿里云函数计算（完全免费，需免费试用额度）

### 1. 修改代码适配 HTTP 触发器

`index.py` 已适配函数计算入口，只需做以下处理：

**方式 A：直接用 HTTP 触发器**
- 在阿里云控制台创建函数
- 运行时选 **Python 3.9**
- 代码粘贴 `index.py` 的内容
- 配置环境变量 `FC_FUNCTION_INPUT_TYPE=http`
- 创建 HTTP 触发器，拿到公网 URL

**方式 B：容器镜像（推荐）**
```bash
# 本地构建镜像（如果有 Docker）
docker build -t pomacea-api -f Dockerfile .
docker tag pomacea-api registry.cn-hangzhou.aliyuncs.com/你的命名空间/pomacea-api:v1
docker push registry.cn-hangzhou.aliyuncs.com/你的命名空间/pomacea-api:v1
```
然后在函数计算控制台选择容器镜像部署。

---

## 方案三：Nginx 反向代理（推荐已有域名者）

如果你有域名和阿里云 CDN：
```
用户请求 → 你的域名:80 → Nginx → Python 后端 :9000
```

Nginx 配置：
```nginx
server {
    listen 80;
    server_name api.你的域名.com;

    location / {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 更新 SKILL.md 和前端

拿到 API URL 后（一站式部署完成后）：

```bash
# 替换 API 地址
sed -i 's|https://你的API地址|https://实际地址|g' SKILL.md
sed -i 's|https://你的API地址|https://实际地址|g' web/index.html
git add . && git commit -m "chore: 更新 API 地址" && git push
```

---

## 一句话总结

> 最简部署：**买台 ¥24/月的阿里云轻量服务器 → 上传 index.py → `python3 index.py &` → 完成**
