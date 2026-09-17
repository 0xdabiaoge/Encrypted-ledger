#!/usr/bin/env bash
# ==============================================================================
# Encrypted Ledger - Ubuntu / Debian Docker Compose Automated Deployment Script
# 自动检测 Docker / Docker Compose 环境、依赖项、系统硬件资源与一键拉起容器栈
# ==============================================================================
set -e

# ANSI Color Codes
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
echo "   ENCRYPTED LEDGER - DOCKER COMPOSE 自动化智能部署中枢"
echo "========================================================================"
echo -e "${NC}"

# ------------------------------------------------------------------------------
# 1. 权限检测 (Root / Sudo)
# ------------------------------------------------------------------------------
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}⚠️  检测到当前非 root 用户运行，部分安装步骤可能需要 sudo 权限。${NC}"
    SUDO="sudo"
else
    SUDO=""
fi

# ------------------------------------------------------------------------------
# 2. 操作系统与硬件资源检测 (Ubuntu / Debian / RAM / Disk)
# ------------------------------------------------------------------------------
echo -e "${BLUE}🔍 [阶段 1/6] 检测操作系统与 VPS 硬件资源...${NC}"

if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_NAME=$NAME
    OS_VER=$VERSION_ID
    echo -e "   • 操作系统: ${GREEN}${OS_NAME} ${OS_VER}${NC}"
else
    OS_NAME=$(uname -s)
    echo -e "   • 操作系统: ${YELLOW}${OS_NAME}${NC}"
fi

# 内存检测 (建议 >= 1GB)
TOTAL_RAM_MB=$(free -m | awk '/^Mem:/{print $2}')
AVAIL_RAM_MB=$(free -m | awk '/^Mem:/{print $7}')
echo -e "   • 总物理内存: ${GREEN}${TOTAL_RAM_MB} MB${NC} (可用: ${AVAIL_RAM_MB} MB)"

if [ "$TOTAL_RAM_MB" -lt 900 ]; then
    echo -e "${YELLOW}⚠️  警告: VPS 物理内存低于 1GB (${TOTAL_RAM_MB}MB)。在 Docker 镜像构建时可能遭遇 OOM (内存溢出)。${NC}"
    SWAP_EXIST=$(free -m | awk '/^Swap:/{print $2}')
    if [ "$SWAP_EXIST" -lt 1024 ]; then
        echo -e "${CYAN}💡 正在为您自动配置 2GB Swap 虚拟内存以保障构建稳定...${NC}"
        $SUDO fallocate -l 2G /swapfile || $SUDO dd if=/dev/zero of=/swapfile bs=1M count=2048
        $SUDO chmod 600 /swapfile
        $SUDO mkswap /swapfile
        $SUDO swapon /swapfile
        echo -e "${GREEN}✅ 2GB Swap 虚拟内存激活成功！${NC}"
    fi
fi

# 磁盘空间检测 (建议 >= 5GB 可用)
FREE_DISK_GB=$(df -BG "$ROOT_DIR" | awk 'NR==2 {print $4}' | sed 's/G//')
echo -e "   • 磁盘剩余空间: ${GREEN}${FREE_DISK_GB} GB${NC}"
if [ "$FREE_DISK_GB" -lt 3 ]; then
    echo -e "${RED}❌ 磁盘剩余可用空间不足 3GB (${FREE_DISK_GB}GB)，请先清理磁盘空间！${NC}"
    exit 1
fi

# ------------------------------------------------------------------------------
# 3. 基础依赖包检测 (curl, git, ufw, ss)
# ------------------------------------------------------------------------------
echo -e "\n${BLUE}📦 [阶段 2/6] 检测基础系统命令依赖...${NC}"
MISSING_PKGS=()

for cmd in curl git awk sed; do
    if ! command -v $cmd &> /dev/null; then
        MISSING_PKGS+=($cmd)
    fi
done

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo -e "   • 正在安装缺失的系统依赖: ${YELLOW}${MISSING_PKGS[*]}${NC}..."
    $SUDO apt-get update -qq && $SUDO apt-get install -y -qq "${MISSING_PKGS[@]}"
fi
echo -e "   • 基础依赖包: ${GREEN}全部就绪${NC}"

# 端口 8080 占用检测
if command -v ss &> /dev/null; then
    PORT_BUSY=$(ss -tulpn | grep ':8080 ' || true)
    if [ -n "$PORT_BUSY" ]; then
        echo -e "${YELLOW}⚠️  警告: 宿主机 8080 端口已被占用，请确认是否有已有进程:${NC}"
        echo -e "   $PORT_BUSY"
        echo -e "${CYAN}💡 如需更换端口，请在 .env 中设置 PORT=其他端口 (如 PORT=8888)${NC}"
    else
        echo -e "   • 服务端口 8080: ${GREEN}空闲可用${NC}"
    fi
fi

# ------------------------------------------------------------------------------
# 4. Docker 引擎检测与自动安装
# ------------------------------------------------------------------------------
echo -e "\n${BLUE}🐳 [阶段 3/6] 检测 Docker 容器运行环境...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}⚠️  系统未检测到 Docker，正在通过官方通道自动安装 Docker CE...${NC}"
    curl -fsSL https://get.docker.com | $SUDO sh
    $SUDO systemctl enable --now docker
    echo -e "${GREEN}✅ Docker 引擎安装完成！${NC}"
else
    DOCKER_VER=$(docker --version)
    echo -e "   • Docker: ${GREEN}${DOCKER_VER}${NC}"
fi

# 确保 Docker 服务处于运行状态
if ! $SUDO systemctl is-active --quiet docker; then
    echo -e "   • 启动 Docker 服务..."
    $SUDO systemctl start docker
fi

# ------------------------------------------------------------------------------
# 5. Docker Compose 检测与自动安装 (V2 插件 / V1 兼容)
# ------------------------------------------------------------------------------
echo -e "\n${BLUE}🐙 [阶段 4/6] 检测 Docker Compose 编排插件...${NC}"

COMPOSE_CMD=""
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
    COMPOSE_VER=$(docker compose version)
    echo -e "   • Docker Compose (V2 Plugin): ${GREEN}${COMPOSE_VER}${NC}"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
    COMPOSE_VER=$(docker-compose --version)
    echo -e "   • Docker Compose (Standalone): ${GREEN}${COMPOSE_VER}${NC}"
else
    echo -e "${YELLOW}⚠️  未检测到 Docker Compose，正在自动安装 docker-compose-plugin...${NC}"
    $SUDO apt-get update -qq && $SUDO apt-get install -y -qq docker-compose-plugin
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
        echo -e "${GREEN}✅ Docker Compose 插件安装成功！${NC}"
    else
        echo -e "${RED}❌ 安装失败，请手动执行 'sudo apt-get install docker-compose-plugin'${NC}"
        exit 1
    fi
fi

# ------------------------------------------------------------------------------
# 6. 配置与存储卷持久化目录准备
# ------------------------------------------------------------------------------
echo -e "\n${BLUE}⚙️  [阶段 5/6] 检查配置文件与持久化存储卷...${NC}"

# 1. 检查或生成 .env
if [ ! -f .env ]; then
    if [ -f env.example ]; then
        echo -e "   • 正在从 env.example 创建生产环境 .env 配置文件..."
        cp env.example .env
        $SUDO chmod 600 .env
        # 自动生成随机 64 位 ADMIN_SETUP_TOKEN
        RANDOM_TOKEN=$(head -c 32 /dev/urandom | xxd -p 2>/dev/null || openssl rand -hex 32 2>/dev/null || echo "token_$(date +%s)_rand")
        sed -i "s/ADMIN_SETUP_TOKEN=change_me_to_a_secure_random_token_64chars/ADMIN_SETUP_TOKEN=${RANDOM_TOKEN}/" .env 2>/dev/null || true
        echo -e "   • 已自动生成专属管理员安全凭据: ${GREEN}${RANDOM_TOKEN}${NC}"
    else
        echo -e "${RED}❌ 错误: 未找到 env.example 模板文件！${NC}"
        exit 1
    fi
else
    echo -e "   • 环境变量配置文件: ${GREEN}.env 已存在${NC}"
fi

# 2. 检查持久化目录与权限
mkdir -p data logs data/policy_archives
if [ ! -f data/universe.json ] && [ -f universe.json ]; then
    cp universe.json data/universe.json
fi
echo -e "   • 数据持久化卷 (data/, logs/): ${GREEN}就绪${NC}"

# ------------------------------------------------------------------------------
# 7. 构建镜像并启动 Docker Compose 服务栈
# ------------------------------------------------------------------------------
echo -e "\n${BLUE}🚀 [阶段 6/6] 构建并启动 Encrypted Ledger 容器服务...${NC}"

# 执行一键构建与拉起
$SUDO $COMPOSE_CMD up -d --build

echo -e "\n${CYAN}⏳ 正在等待容器初始化与健康检查 (最多 30 秒)...${NC}"

HEALTHY=false
for i in $(seq 1 30); do
    sleep 1
    STATUS=$(curl -s http://127.0.0.1:8080/api/v1/system/health 2>/dev/null || true)
    if echo "$STATUS" | grep -q '"status":"healthy"'; then
        HEALTHY=true
        break
    fi
    echo -n "."
done
echo ""

# ------------------------------------------------------------------------------
# 8. 配置 Nginx 域名反向代理 (www.zhujiaofan.eu.cc -> 127.0.0.1:8080)
# ------------------------------------------------------------------------------
echo -e "\n${BLUE}🌐 [阶段 7/7] 配置宿主机 Nginx 域名反向代理...${NC}"
if ! command -v nginx &> /dev/null; then
    echo -e "   • 正在安装 Nginx 反代服务..."
    $SUDO apt-get update -qq && $SUDO apt-get install -y -qq nginx
fi

# 确保 Nginx 服务运行
if ! $SUDO systemctl is-active --quiet nginx; then
    $SUDO systemctl enable --now nginx || true
fi

# 写入或更新反代配置
NGINX_CONF="/etc/nginx/sites-available/zhujiaofan.conf"
if [ -f "$ROOT_DIR/deploy/nginx_zhujiaofan.conf" ]; then
    $SUDO cp "$ROOT_DIR/deploy/nginx_zhujiaofan.conf" "$NGINX_CONF"
else
    cat << 'EOF' | $SUDO tee "$NGINX_CONF" > /dev/null
server {
    listen 80;
    listen [::]:80;
    server_name www.zhujiaofan.eu.cc zhujiaofan.eu.cc;
    client_max_body_size 50M;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}
EOF
fi

$SUDO ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/zhujiaofan.conf
if $SUDO nginx -t &> /dev/null; then
    $SUDO systemctl reload nginx
    echo -e "   • Nginx 反代已成功加载: ${GREEN}http://www.zhujiaofan.eu.cc/${NC}"
else
    echo -e "${YELLOW}⚠️  Nginx 语法检测异常，请手动检查 $NGINX_CONF${NC}"
fi

# ------------------------------------------------------------------------------
# 9. 输出部署结果与运维管理指南
# ------------------------------------------------------------------------------
SERVER_IP=$(curl -s -4 https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}' || echo "你的VPS公网IP")

if [ "$HEALTHY" = true ]; then
    echo -e "${GREEN}${BOLD}"
    echo "========================================================================"
    echo "🎉 恭喜！ENCRYPTED LEDGER 已成功通过 DOCKER COMPOSE 与 NG 反代部署上线！"
    echo "========================================================================"
    echo -e "${NC}"
    echo -e "🌐  ${BOLD}官方域名反代访问${NC} : ${CYAN}http://www.zhujiaofan.eu.cc/${NC}"
    echo -e "🖥️   ${BOLD}原生容器公网访问${NC} : ${CYAN}http://${SERVER_IP}:8080/${NC} (本地: http://127.0.0.1:8080/)"
    echo -e "📑  ${BOLD}交互式 API 接口文档${NC} : ${CYAN}http://www.zhujiaofan.eu.cc/docs${NC}"
    echo -e "🔑  ${BOLD}默认管理员账号${NC}     : ${GREEN}admin${NC}"
    echo -e "🛡️  ${BOLD}默认管理员初始密码${NC} : ${GREEN}Admin123!@#${NC} (首次进入请在控制面板修改)"
    echo ""
    echo -e "${BOLD}常用日常运维命令：${NC}"
    echo -e "  • 机器内一键更新镜像     : ${CYAN}./update.sh${NC}"
    echo -e "  • 查看实时交易与因果日志 : ${CYAN}$COMPOSE_CMD logs -f${NC}"
    echo -e "  • 重启交易中枢容器       : ${CYAN}$COMPOSE_CMD restart${NC}"
    echo -e "  • 重新加载 Nginx 反代    : ${CYAN}$SUDO systemctl reload nginx${NC}"
    echo "========================================================================"
else
    echo -e "${YELLOW}⚠️  服务已启动，但健康检查仍在同步中。${NC}"
    echo -e "请运行以下命令查看容器实时输出："
    echo -e "  ${CYAN}$COMPOSE_CMD logs -f${NC}"
fi
