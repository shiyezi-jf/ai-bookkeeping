#!/usr/bin/env bash
# ============================================================
# AI 一句话记账 · 一键部署脚本（Ubuntu 22.04 / 24.04）
#
# 用法（在服务器上以 root 执行）：
#   sudo bash deploy.sh
#
# 换端口（比如买了香港节点想用 80）：
#   sudo PORT=80 bash deploy.sh
#
# 重复执行是安全的：会拉取最新代码、重装依赖、重建前端、重启服务。
# ============================================================

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/shiyezi-jf/ai-bookkeeping.git}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-/opt/ai-bookkeeping}"
SERVICE_NAME="ai-bookkeeping"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${PORT:-8080}"

C_GREEN='\033[0;32m'; C_YELLOW='\033[0;33m'; C_RED='\033[0;31m'; C_BLUE='\033[0;36m'; C_OFF='\033[0m'
step()  { echo -e "\n${C_BLUE}==== $* ====${C_OFF}"; }
ok()    { echo -e "${C_GREEN}✅ $*${C_OFF}"; }
warn()  { echo -e "${C_YELLOW}⚠️  $*${C_OFF}"; }
die()   { echo -e "${C_RED}❌ $*${C_OFF}"; exit 1; }

# ---------- 0. 基本检查 ----------
step "0/8 环境检查"
[ "$(id -u)" -eq 0 ] || die "请用 root 运行：sudo bash deploy.sh"

if ! command -v apt-get >/dev/null 2>&1; then
  die "这个脚本只支持 Ubuntu / Debian。你当前不是这类系统，请重装为 Ubuntu 22.04 后再试。"
fi

. /etc/os-release 2>/dev/null || true
echo "系统：${PRETTY_NAME:-未知}"
ok "检查通过"

# ---------- 1. 安装系统依赖 ----------
step "1/8 安装系统依赖（python3 / nginx / git / nodejs）"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y -qq
apt-get install -y -qq python3 python3-venv python3-pip git nginx curl ca-certificates >/dev/null
ok "基础包安装完成"

if ! command -v node >/dev/null 2>&1 || [ "$(node -v | sed 's/v\([0-9]*\).*/\1/')" -lt 20 ]; then
  echo "安装 Node.js 22（前端构建需要）..."
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash - >/dev/null 2>&1 \
    || die "Node.js 下载失败。可能是网络问题，稍后重跑本脚本即可。"
  apt-get install -y -qq nodejs >/dev/null
fi
ok "Node.js 版本：$(node -v)"

# ---------- 2. 拉取代码 ----------
step "2/8 拉取代码到 $APP_DIR"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH" >/dev/null 2>&1
  git -C "$APP_DIR" reset --hard "origin/$BRANCH" >/dev/null
  ok "已更新到最新代码"
else
  mkdir -p "$(dirname "$APP_DIR")"
  git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$APP_DIR" >/dev/null 2>&1 \
    || die "克隆失败。请确认仓库地址可访问：$REPO_URL"
  ok "代码已下载"
fi
echo "当前版本：$(git -C "$APP_DIR" log -1 --format='%h %s')"

# ---------- 3. 配置密钥 ----------
step "3/8 配置大模型密钥"
ENV_FILE="$APP_DIR/backend/.env"
if [ -f "$ENV_FILE" ] && grep -q '^LLM_API_KEY=sk-' "$ENV_FILE" 2>/dev/null; then
  ok "检测到已有 .env，保留原密钥（要换密钥请先删除 $ENV_FILE 再重跑）"
else
  echo "请粘贴你的 DeepSeek 密钥（sk- 开头，粘贴后按回车，屏幕上不会显示）："
  read -r LLM_KEY
  [ -n "${LLM_KEY:-}" ] || die "密钥不能为空"
  case "$LLM_KEY" in
    sk-*) ;;
    *) die "这不像一个密钥（应以 sk- 开头）。请到 platform.deepseek.com 重新复制。" ;;
  esac

  cat > "$ENV_FILE" <<EOF
# 由 deploy.sh 自动生成
DATABASE_URL=sqlite+aiosqlite:///./app.db
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:${WEB_PORT}
LLM_API_KEY=${LLM_KEY}
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
EOF
  chmod 600 "$ENV_FILE"
  ok "密钥已写入 $ENV_FILE（权限 600，只有 root 能读）"
fi

# ---------- 4. 后端依赖 ----------
step "4/8 安装后端依赖（第一次约 1–3 分钟）"
cd "$APP_DIR/backend"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
ok "后端依赖安装完成（Python $(.venv/bin/python -V 2>&1 | awk '{print $2}')）"

# ---------- 5. 注册为系统服务 ----------
step "5/8 配置开机自启（systemd）"
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=AI Bookkeeping API
After=network.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}/backend
ExecStart=${APP_DIR}/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT}
Restart=always
RestartSec=3
User=root

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null 2>&1
systemctl restart "$SERVICE_NAME"
sleep 3
systemctl is-active --quiet "$SERVICE_NAME" || {
  echo "--- 最近 30 行日志 ---"
  journalctl -u "$SERVICE_NAME" -n 30 --no-pager
  die "后端启动失败，请把上面的日志发给 AI"
}
ok "后端服务已启动并设为开机自启"

# ---------- 6. 构建前端 ----------
step "6/8 构建前端（约 1–3 分钟）"
cd "$APP_DIR/frontend"
if [ -f package-lock.json ]; then
  npm ci --no-audit --no-fund --silent 2>/dev/null || npm install --no-audit --no-fund --silent
else
  npm install --no-audit --no-fund --silent
fi
npm run build --silent
[ -f dist/index.html ] || die "前端构建失败，dist/index.html 不存在"
ok "前端构建完成"

# ---------- 7. 配置 nginx ----------
step "7/8 配置 nginx（对外端口 ${WEB_PORT}）"
cat > /etc/nginx/sites-available/ai-bookkeeping <<EOF
server {
    listen ${WEB_PORT};
    server_name _;

    root ${APP_DIR}/frontend/dist;
    index index.html;

    # 接口请求转发给后端，浏览器看到的是同一个域名，因此不存在跨域问题
    location /api/ {
        proxy_pass http://127.0.0.1:${API_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }

    # 单页应用：刷新子路径时也要返回 index.html
    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
ln -sf /etc/nginx/sites-available/ai-bookkeeping /etc/nginx/sites-enabled/ai-bookkeeping
rm -f /etc/nginx/sites-enabled/default
nginx -t >/dev/null 2>&1 || die "nginx 配置有语法错误，请运行 nginx -t 查看"
systemctl reload nginx
systemctl enable nginx >/dev/null 2>&1
ok "nginx 已启动"

# ---------- 8. 自检 ----------
step "8/8 自检"
sleep 1
BACKEND_PING=$(curl -s --max-time 5 "http://127.0.0.1:${API_PORT}/api/ping" || true)
WEB_PING=$(curl -s --max-time 5 "http://127.0.0.1:${WEB_PORT}/api/ping" || true)

echo "后端直连  : ${BACKEND_PING:-无响应}"
echo "nginx 转发: ${WEB_PING:-无响应}"

case "$BACKEND_PING" in
  *pong*) ok "后端正常" ;;
  *) die "后端没有返回 pong，请运行：journalctl -u ${SERVICE_NAME} -n 50" ;;
esac
case "$WEB_PING" in
  *pong*) ok "nginx 转发正常" ;;
  *) die "nginx 转发失败，请检查：systemctl status nginx" ;;
esac

PUBLIC_IP=$(curl -s --max-time 5 https://api.ipify.org || hostname -I | awk '{print $1}')

cat <<EOF

$(echo -e "${C_GREEN}")============================================================
🎉 部署完成
============================================================$(echo -e "${C_OFF}")

  网站地址：http://${PUBLIC_IP}:${WEB_PORT}
  接口文档：http://${PUBLIC_IP}:${WEB_PORT}/docs

如果打不开，99% 是云厂商的防火墙没放行 ${WEB_PORT} 端口：
  · 腾讯云轻量：控制台 → 服务器详情 → 防火墙 → 添加规则 → TCP ${WEB_PORT}
  · 阿里云轻量：控制台 → 服务器详情 → 防火墙 → 添加规则 → TCP ${WEB_PORT}

常用命令：
  查看日志    journalctl -u ${SERVICE_NAME} -f
  重启后端    systemctl restart ${SERVICE_NAME}
  更新代码    sudo bash ${APP_DIR}/deploy/update.sh

EOF
