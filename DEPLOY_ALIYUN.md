# 阿里云部署指南

## 方案一：GitOps 自动部署（推荐，一劳永逸 ✅）

> 代码推送到 GitHub → 自动触发部署到阿里云服务器

### 第一步：服务器准备工作（只需做一次）

用任意 SSH 客户端连接服务器，执行：

```bash
# 创建工作目录
mkdir -p /root/pomacea-reporter

# 给部署脚本加执行权限
chmod +x /root/pomacea-reporter/server/deploy.sh
```

### 第二步：生成部署密钥（只需做一次）

在**本地电脑**（不是服务器）打开终端：

```bash
# 生成密钥对（不回车密码，一路回车）
ssh-keygen -t ed25519 -C "github-deploy" -f github_deploy_key

# 查看公钥
cat github_deploy_key.pub
```

复制公钥内容，加入服务器 `authorized_keys`：
```bash
# SSH 登录服务器后执行
echo "刚才复制的公钥内容" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### 第三步：在 GitHub 配置密钥（只需做一次）

1. 打开仓库：https://github.com/konghaojie-k2/pomacea-reporter/settings/secrets/actions
2. 点 **New repository secret**，添加以下 4 条：

| Secret 名称 | 值 | 说明 |
|------------|---|------|
| `SERVER_HOST` | 你的服务器公网 IP | 例：`47.92..xxx.xxx` |
| `SERVER_PORT` | `22` | SSH 端口，默认 22 |
| `SERVER_USER` | `root` | 用户名 |
| `SERVER_SSH_KEY` | `github_deploy_key` 的**私钥**内容 | 完整粘贴（包括 `-----BEGIN` 和 `-----END` 行） |

3. 点 **Add secret**

### 第四步：在服务器开放 SSH 密钥登录

在服务器执行：
```bash
# 编辑 SSH 配置禁用密码登录（更安全）
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd
```

### 第五步：验证自动部署

推送任意改动到 GitHub：
```bash
git add .
git commit -m "test: 验证自动部署"
git push origin master
```

打开 https://github.com/konghaojie-k2/pomacea-reporter/actions 查看部署状态。

---

## 方案二：手动部署（一次性使用）

### 1. 上传代码到服务器

在你电脑上下载 `server-deploy.tar.gz` 后：
```bash
scp server-deploy.tar.gz root@你的IP:/root/
```

### 2. 服务器上解压运行
```bash
ssh root@你的IP
# 输入密码登录后：

tar -xzf server-deploy.tar.gz
cd server
chmod +x deploy.sh
bash deploy.sh
```

### 3. 开放端口
在阿里云控制台 → **轻量应用服务器** → **防火墙**：
- 放行端口：**9000**（TCP）

---

## 验证部署成功

```bash
curl https://你的服务器IP:9000/
# 应返回：{"status":"ok","service":"pomacea-reporter"...}
```

## 常见问题

**Q: 部署时报 `Permission denied (publickey)`？**
→ 服务器未正确添加公钥，重新检查第二步

**Q: 部署成功但 API 无法访问？**
→ 阿里云安全组未开放 9000 端口，在控制台添加入站规则

**Q: 进程启动后又退出了？**
→ 查看日志：`tail -20 /root/pomacea-reporter/api.log`
