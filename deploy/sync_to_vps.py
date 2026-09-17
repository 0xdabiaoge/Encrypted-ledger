#!/usr/bin/env python3
import os
import sys
import tarfile
import tempfile
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
    client.exec_command(f"mkdir -p {REMOTE_DIR}")
    remote_tar = f"{REMOTE_DIR}/deploy.tar.gz"
    sftp.put(tar_tmp.name, remote_tar)
    sftp.close()
    os.unlink(tar_tmp.name)

    # 3. Extract and set permissions
    print("Extracting on VPS...")
    client.exec_command(f"cd {REMOTE_DIR} && tar -xzf deploy.tar.gz && rm -f deploy.tar.gz && chmod +x deploy.sh deploy/*.sh")

    # 4. Check git status and remote
    cmd_git = f"""cd {REMOTE_DIR} && git init && git config user.name "0xdabiaoge" && git config user.email "dabiaoge@users.noreply.github.com" && git remote remove origin 2>/dev/null || true; git remote add origin git@github.com:0xdabiaoge/Encrypted-ledger.git; git status -s"""
    stdin, stdout, stderr = client.exec_command(cmd_git)
    print("Git status on VPS:\n" + stdout.read().decode("utf-8"))

    client.close()
    print("Code successfully synchronized to VPS /opt/encrypted-ledger!")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "key":
        print("VPS SSH PUBLIC KEY:")
        print(get_vps_ssh_key())
    else:
        deploy_code_to_vps()
        print("\nVPS SSH PUBLIC KEY FOR GITHUB:")
        print(get_vps_ssh_key())
