#!/usr/bin/env bash
# ==============================================================================
# Encrypted Ledger - One-Click Image Update & Restart Script
# 机器内一键拉取最新 GitHub 构建镜像并热重构容器
# ==============================================================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo -e "${CYAN}${BOLD}"
echo "========================================================================"
echo "   ENCRYPTED LEDGER - 镜像更新与无缝热重构"
echo "========================================================================"
echo -e "${NC}"

# 1. 确定 Docker Compose 命令
COMPOSE_CMD=""
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}❌ 错误: 未检测到 Docker Compose 命令！${NC}"
    exit 1
fi

# 2. 拉取最新 GitHub 构建的容器镜像
echo -e "${BLUE}📦 [1/3] 正在从 GitHub Registry (ghcr.io) 拉取最新镜像...${NC}"
$COMPOSE_CMD pull || {
    echo -e "${YELLOW}⚠️  从 Registry 拉取镜像失败，自动回退至本地快速增量构建...${NC}"
    $COMPOSE_CMD build
}

# 3. 原地热更新并拉起容器
echo -e "\n${BLUE}🚀 [2/3] 重构并热启动服务容器...${NC}"
$COMPOSE_CMD up -d

# 4. 健康检查与状态验证
echo -e "\n${BLUE}🔍 [3/3] 正在验证容器健康状态...${NC}"
HEALTHY=false
for i in $(seq 1 15); do
    sleep 1
    STATUS=$(curl -s http://127.0.0.1:8080/api/v1/system/health 2>/dev/null || true)
    if echo "$STATUS" | grep -q '"status":"healthy"'; then
        HEALTHY=true
        break
    fi
    echo -n "."
done
echo ""

# 5. 清理悬空/无用历史镜像
echo -e "${CYAN}🧹 自动清理历史废弃镜像...${NC}"
docker image prune -f >/dev/null 2>&1 || true

if [ "$HEALTHY" = true ]; then
    echo -e "${GREEN}${BOLD}"
    echo "========================================================================"
    echo "🎉 恭喜！系统已成功完成更新并无缝上线！"
    echo "========================================================================"
    echo -e "${NC}"
    echo -e "🌐 官方反代域名 : ${CYAN}http://www.zhujiaofan.eu.cc/${NC}"
    echo -e "🖥️  原生容器端口 : ${CYAN}http://127.0.0.1:8080/${NC}"
    echo -e "📑 交互文档地址 : ${CYAN}http://www.zhujiaofan.eu.cc/docs${NC}"
    echo "========================================================================"
else
    echo -e "${RED}❌ 容器已启动，但健康检查暂未就绪，请查看实时日志：${NC}"
    echo -e "  $COMPOSE_CMD logs -f"
fi
