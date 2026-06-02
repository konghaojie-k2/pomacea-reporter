#!/bin/bash
# ============================================================
# 🐌 福寿螺平台 — 服务器运维脚本
# 在项目根目录（DEPLOY_PATH）运行：bash server/deploy.sh <命令>
#
# 支持的命令：
#   deploy    拉取代码 + 重建容器（默认）
#   status    查看容器/服务状态
#   logs      查看最近 50 行容器日志
#   restart   重启容器（不动代码）
#   reset-db  ⚠️  删除并重建 SQLite 数据库（数据清空）
#   fix-https 容器内 https→http 修复（兼容老的前端）
#   shell     进入容器 shell
# ============================================================

set +e  # 不用 -e，所有命令都跑完，方便诊断

API_PORT=9000
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# ─── 颜色输出 ───────────────────────────────────
red()    { echo -e "\033[31m$*\033[0m"; }
green()  { echo -e "\033[32m$*\033[0m"; }
yellow() { echo -e "\033[33m$*\033[0m"; }
blue()   { echo -e "\033[34m$*\033[0m"; }

# ─── 子命令 ─────────────────────────────────────

cmd_deploy() {
  blue "=== 🐌 开始部署 ($(date)) ==="

  # 1. 拉取最新代码
  if [ ! -d .git ]; then
    yellow "📦 目录不是 git 仓库，初始化..."
    git init -q
    git remote add origin https://github.com/konghaojie-k2/pomacea-reporter.git
  fi
  git fetch origin master
  git reset --hard origin/master
  green "✅ 代码已更新到 origin/master"

  # 2. 清掉所有同名容器和 compose 残留
  yellow "🧹 清理旧容器..."
  docker compose down --rmi local --remove-orphans 2>&1 | tail -5
  docker rm -f pomacea-reporter 2>/dev/null
  green "✅ 旧容器已清理"

  # 3. 强制无缓存重建（避免 frontend.html 改动被缓存）
  yellow "🔨 重建镜像（无缓存）..."
  docker compose build --no-cache 2>&1 | tail -10
  green "✅ 镜像构建完成"

  # 4. 启动
  yellow "🚀 启动容器..."
  docker compose up -d
  sleep 3
  green "✅ 容器已启动"

  # 5. 等应用就绪（重试 6 次共 30 秒）
  yellow "⏳ 等待应用就绪..."
  for i in 1 2 3 4 5 6; do
    sleep 5
    if curl -sf "http://localhost:${API_PORT}/api/records" > /dev/null 2>&1; then
      green "✅ 部署成功！第 $i 次（${i}x5s）"
      green "🌐 http://$(hostname -I | awk '{print $1}'):${API_PORT}"
      return 0
    fi
    yellow "   第 $i 次重试未就绪..."
  done

  # 失败诊断
  red "❌ 启动失败，输出诊断："
  echo "--- 📋 容器状态 ---"
  docker compose ps
  echo "--- 📋 容器日志（最近 30 行）---"
  docker compose logs --tail=30
  echo "--- 📋 端口监听 ---"
  ss -tlnp 2>/dev/null | grep ${API_PORT} || netstat -tlnp 2>/dev/null | grep ${API_PORT} || echo "  （无 ss/netstat）"
  return 1
}

cmd_status() {
  blue "=== 📊 服务状态 ==="
  echo "--- Docker 容器 ---"
  docker compose ps
  echo ""
  echo "--- 端口监听 ---"
  ss -tlnp 2>/dev/null | grep ${API_PORT} || netstat -tlnp 2>/dev/null | grep ${API_PORT} || echo "  端口 ${API_PORT} 未监听"
  echo ""
  echo "--- 健康检查 ---"
  if curl -sf "http://localhost:${API_PORT}/api/records" > /dev/null 2>&1; then
    green "✅ /api/records 200 OK"
  else
    red "❌ /api/records 不可达"
  fi
  echo ""
  echo "--- 数据库 ---"
  ls -lh data/ 2>/dev/null || echo "  data/ 目录不存在"
}

cmd_logs() {
  blue "=== 📋 容器日志（最近 50 行）==="
  docker compose logs --tail=50
}

cmd_restart() {
  yellow "🔄 重启容器..."
  docker compose restart
  sleep 3
  cmd_status
}

cmd_reset_db() {
  red "⚠️  即将删除数据库 $(ls data/pomacea.db 2>/dev/null)"
  read -p "确认要清空所有举报数据？[y/N] " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    yellow "已取消"
    return 0
  fi
  # 停服 → 删库 → 起服（让 _init_db 重建）
  docker compose stop
  rm -f data/pomacea.db
  docker compose start
  sleep 3
  green "✅ 数据库已重置（重启时 index.py 会自动建表）"
  cmd_status
}

cmd_fix_https() {
  yellow "🔧 容器内 https→http 修复..."
  # 仅当容器内还有老的前端残留才需要（保留兼容）
  if docker exec pomacea-reporter grep -q "https://47.85.36.226" /app/frontend.html 2>/dev/null; then
    docker exec pomacea-reporter sed -i "s|https://47.85.36.226|http://47.85.36.226|g" /app/frontend.html
    docker restart pomacea-reporter
    green "✅ 已修复并重启"
  else
    yellow "  容器内前端没发现 https://47.85.36.226，无需修复"
  fi
}

cmd_shell() {
  blue "🐚 进入容器 shell（输入 exit 退出）..."
  docker exec -it pomacea-reporter /bin/sh
}

# ─── 入口 ───────────────────────────────────────

CMD="${1:-deploy}"
case "$CMD" in
  deploy)    cmd_deploy ;;
  status)    cmd_status ;;
  logs)      cmd_logs ;;
  restart)   cmd_restart ;;
  reset-db)  cmd_reset_db ;;
  fix-https) cmd_fix_https ;;
  shell)     cmd_shell ;;
  *)
    red "未知命令: $CMD"
    echo "用法: bash server/deploy.sh {deploy|status|logs|restart|reset-db|fix-https|shell}"
    exit 1
    ;;
esac
