#!/usr/bin/env python3
import os
import sys
import tarfile
import tempfile
import time
from pathlib import Path
import paramiko

VPS_HOST = "186.241.77.156"
VPS_PORT = 65522
VPS_USER = "root"
VPS_PASS = "DAyuge66..--++"
REMOTE_DIR = "/opt/encrypted-ledger"

LOCAL_DIR = Path(__file__).resolve().parents[1]


def get_vps_ssh_key():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(VPS_HOST, port=VPS_PORT, username=VPS_USER, password=VPS_PASS, timeout=15)
    
    cmd = 'if [ ! -f /root/.ssh/id_ed25519 ]; then ssh-keygen -t ed25519 -C "0xdabiaoge" -f /root/.ssh/id_ed25519 -N ""; fi; cat /root/.ssh/id_ed25519.pub'
    stdin, stdout, stderr = client.exec_command(cmd)
    pub_key = stdout.read().decode("utf-8").strip()
    client.close()
    return pub_key


def deploy_code_to_vps():
    print(f"Connecting to VPS {VPS_HOST}:{VPS_PORT} as {VPS_USER}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(VPS_HOST, port=VPS_PORT, username=VPS_USER, password=VPS_PASS, timeout=15)
    
    # 1. Package files into a tar.gz excluding ignored files
    print("Packaging project files...")
    tar_tmp = tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False)
    tar_tmp.close()

    ignored_dirs = {"r20-quantum-trader-main", ".venv", "venv", "__pycache__", "node_modules", ".git"}
    ignored_files = {".env", "encrypted_ledger.db", "encrypted_ledger.db-shm", "encrypted_ledger.db-wal"}

    with tarfile.open(tar_tmp.name, "w:gz") as tar:
        for item in LOCAL_DIR.iterdir():
            if item.name in ignored_dirs or item.name in ignored_files or item.name.endswith(".log"):
                continue
            tar.add(item, arcname=item.name)

    # 2. Upload via SFTP
    print(f"Uploading archive ({os.path.getsize(tar_tmp.name) / 1024:.1f} KB) to {REMOTE_DIR}...")
    sftp = client.open_sftp()
    stdin, stdout, stderr = client.exec_command(f"mkdir -p {REMOTE_DIR}")
    stdout.channel.recv_exit_status()
    remote_tar = f"{REMOTE_DIR}/deploy.tar.gz"
    sftp.put(tar_tmp.name, remote_tar)
    sftp.close()
    os.unlink(tar_tmp.name)

    # 3. Extract and set permissions
    print("Extracting on VPS...")
    stdin, stdout, stderr = client.exec_command(f"cd {REMOTE_DIR} && tar -xzf deploy.tar.gz && rm -f deploy.tar.gz && chmod +x deploy.sh update.sh deploy/*.sh")
    stdout.channel.recv_exit_status()

    # 4. Rebuild & Restart Docker container
    print("Rebuilding & Starting Docker Compose service on VPS...")
    stdin, stdout, stderr = client.exec_command(f"cd {REMOTE_DIR} && docker compose up -d --build")
    print(stdout.read().decode("utf-8", errors="replace"))
    print(stderr.read().decode("utf-8", errors="replace"))
    stdout.channel.recv_exit_status()

    # 5. Check Git and push to GitHub
    print("Committing and pushing to GitHub...")
    commit_msg = sys.argv[1] if len(sys.argv) > 1 else "feat: GitHub Actions CI/CD workflows, manual Docker build, update.sh and Nginx domain reverse proxy"
    cmd_git = f"""cd {REMOTE_DIR} && git add . && git commit -m "{commit_msg}" || true && git push origin main"""
    stdin, stdout, stderr = client.exec_command(cmd_git)
    print(stdout.read().decode("utf-8", errors="replace"))
    print(stderr.read().decode("utf-8", errors="replace"))
    stdout.channel.recv_exit_status()

    # 6. Verify Health, Council Presets, and HTML content
    print("Waiting 5s for application startup...")
    time.sleep(5)
    print("Verifying live deployment on VPS...")
    stdin, stdout, stderr = client.exec_command("curl -s http://127.0.0.1:8080/api/v1/system/health")
    print("Local Health response:", stdout.read().decode("utf-8", errors="replace"))

    stdin, stdout, stderr = client.exec_command("curl -s http://www.zhujiaofan.eu.cc/api/v1/system/health")
    print("Domain (www.zhujiaofan.eu.cc) Health response:", stdout.read().decode("utf-8", errors="replace"))

    stdin, stdout, stderr = client.exec_command("curl -s http://127.0.0.1:8080/api/v1/market/tickers")
    print("Market Tickers response:", stdout.read().decode("utf-8", errors="replace")[:120])

    stdin, stdout, stderr = client.exec_command("curl -s http://127.0.0.1:8080/api/v1/system/council/presets")
    print("Council presets response:", stdout.read().decode("utf-8", errors="replace")[:200])

    stdin, stdout, stderr = client.exec_command("curl -s http://127.0.0.1:8080/api/v1/market/klines?symbol=BTC&interval=5m&limit=5")
    print("Market K-Lines (5m) response:", stdout.read().decode("utf-8", errors="replace")[:140])

    stdin, stdout, stderr = client.exec_command("curl -s http://127.0.0.1:8080/api/v1/market/tickers?venue=smart_agg")
    print("Smart Agg Tickers response:", stdout.read().decode("utf-8", errors="replace")[:120])

    stdin, stdout, stderr = client.exec_command("curl -s http://127.0.0.1:8080/api/v1/market/tickers?venue=gate")
    print("Gate.io Tickers response:", stdout.read().decode("utf-8", errors="replace")[:120])

    stdin, stdout, stderr = client.exec_command("curl -s http://127.0.0.1:8080/api/v1/council/prompt-tokens")
    print("Prompt Studio Tokens response:", stdout.read().decode("utf-8", errors="replace")[:140])

    stdin, stdout, stderr = client.exec_command("curl -s http://127.0.0.1:8080/api/v1/trading/share/EL-SH66335DD1")
    print("Position Share response:", stdout.read().decode("utf-8", errors="replace")[:140])

    client.close()
    print("Sync, deployment, and push completed successfully!")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "key":
        print("VPS SSH PUBLIC KEY:")
        print(get_vps_ssh_key())
    else:
        deploy_code_to_vps()
