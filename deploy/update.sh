#!/usr/bin/env bash
# ============================================================
# AI 一句话记账 · 更新脚本
#
# 用途：你在本地改完代码并 git push 之后，在服务器上执行这一条，
#      把线上版本更新成最新的。
#
# 用法：sudo bash /opt/ai-bookkeeping/deploy/update.sh
# ============================================================

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ai-bookkeeping}"
BRANCH="${BRANCH:-main}"
SERVICE_NAME="ai-bookkeeping"

C_GREEN='\033[0;32m'; C_BLUE='\033[0;36m'; C_RED='\033[0;31m'; C_OFF='\033[0m'
step() { echo -e "\n${C_BLUE}==== $* ====${C_OFF}"; }
ok()   { echo -e "${C_GREEN}✅ $*${C_OFF}"; }
die()  { echo -e "${C_RED}❌ $*${C_OFF}"; exit 1; }

[ "$(id -u)" -eq 0 ] || die "请用 root 运行：sudo bash update.sh"
[ -d "$APP_DIR/.git" ] || die "找不到 $APP_DIR，请先运行 deploy.sh 完成首次部署"

step "1/4 拉取最新代码"
BEFORE=$(git -C "$APP_DIR" log -1 --format='%h')
git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH" >/dev/null
git -C "$APP_DIR" reset --hard "origin/$BRANCH" >/dev/null
AFTER=$(git -C "$APP_DIR" log -1 --format='%h')
if [ "$BEFORE" = "$AFTER" ]; then
  echo "代码没有变化（当前 $AFTER），仍然继续重建一遍。"
else
  ok "代码已更新：$BEFORE → $AFTER"
fi
git -C "$APP_DIR" log -1 --format='   %h %s'

step "2/4 同步后端依赖"
cd "$APP_DIR/backend"
.venv/bin/pip install -q -r requirements.txt
ok "依赖已同步"

step "3/4 重新构建前端"
cd "$APP_DIR/frontend"
if [ -f package-lock.json ]; then
  npm ci --no-audit --no-fund --silent 2>/dev/null || npm install --no-audit --no-fund --silent
else
  npm install --no-audit --no-fund --silent
fi
npm run build --silent
[ -f dist/index.html ] || die "前端构建失败"
ok "前端构建完成"

step "4/4 重启后端"
systemctl restart "$SERVICE_NAME"
sleep 3
systemctl is-active --quiet "$SERVICE_NAME" || {
  journalctl -u "$SERVICE_NAME" -n 30 --no-pager
  die "后端启动失败，请把上面的日志发给 AI"
}
curl -s --max-time 5 "http://127.0.0.1:8000/api/ping" | grep -q pong || die "接口没有返回 pong"
ok "更新完成，接口正常"
