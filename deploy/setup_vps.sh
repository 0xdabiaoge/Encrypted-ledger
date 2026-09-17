#!/usr/bin/env bash
# ==============================================================================
# Encrypted Ledger - VPS Ubuntu/Debian Production Setup Script
# ==============================================================================
set -e

if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run as root (sudo ./deploy/setup_vps.sh)"
  exit 1
fi

echo "🛡️ Configuring VPS environment for Encrypted Ledger..."

# 1. Update OS & Install Core Dependencies
apt-get update && apt-get install -y \
    curl wget git ufw htop logrotate \
    python3 python3-pip python3-venv python3-dev \
    build-essential libssl-dev

# 2. Firewall Optimization (Allow SSH + Dashboard)
ufw allow 22/tcp
ufw allow 8080/tcp
ufw --force enable

# 3. Kernel Tuning for High-Frequency Low-Latency Trading
cat << 'EOF' > /etc/sysctl.d/99-quant-desk.conf
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_tw_reuse = 1
net.ipv4.ip_local_port_range = 1024 65535
vm.swappiness = 10
EOF
sysctl --system

# 4. Deploy Systemd Service
INSTALL_DIR="/opt/encrypted-ledger"
mkdir -p "$INSTALL_DIR"
cp -r . "$INSTALL_DIR/"
cp "$INSTALL_DIR/deploy/encrypted-ledger.service" /etc/systemd/system/

systemctl daemon-reload
echo "✅ VPS system optimized! Run 'systemctl enable --now encrypted-ledger' to start."
