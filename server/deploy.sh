#!/bin/bash
# ============================================================
# 阿里云服务器部署脚本（手动运行版）
# 用法: bash deploy.sh
# ============================================================

set -e

API_PORT=${API_PORT:-9000}
DEPLOY_PATH="/root/pomacea-reporter"

echo "🐌 福寿螺上报平台部署脚本"
echo "================================"

# 检查 python3
if ! command -v python3 &> /dev/null; then
    echo "❌ python3 未安装"
    exit 1
fi

# 检查文件
if [ ! -f "server/index.py" ]; then
    echo "❌ index.py 不存在，请确认在项目根目录运行"
    exit 1
fi

# 创建目录
mkdir -p $DEPLOY_PATH

# 复制代码
echo "📁 复制代码到 $DEPLOY_PATH ..."
cp -r . $DEPLOY_PATH/

# 停止旧进程
OLD_PID=$(pgrep -f "python3.*server/index.py" 2>/dev/null || true)
if [ -n "$OLD_PID" ]; then
    echo "🛑 停止旧进程 PID=$OLD_PID"
    kill $OLD_PID 2>/dev/null || true
    sleep 2
    kill -9 $OLD_PID 2>/dev/null || true
fi

# 启动新进程
echo "🚀 启动服务 ..."
cd $DEPLOY_PATH/server
nohup python3 index.py >> $DEPLOY_PATH/api.log 2>&1 &
sleep 2

# 验证
if curl -sf http://localhost:$API_PORT/ > /dev/null; then
    echo "✅ 部署成功！"
    echo "📍 服务地址: http://localhost:$API_PORT"
    echo "📝 日志: $DEPLOY_PATH/api.log"
else
    echo "❌ 启动失败，查看日志:"
    tail -20 $DEPLOY_PATH/api.log
    exit 1
fi
