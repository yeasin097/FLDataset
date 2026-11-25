#!/usr/bin/env bash
# Install everything the lab needs, inside the Ubuntu (WSL2) distro.
# Run once after cloning the repo:   bash scripts/setup.sh
set -e

echo "[1/5] Updating package lists and installing requirements..."
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    docker.io docker-compose-v2 python3-yaml nftables git unzip

echo "[2/5] Using the iptables-legacy backend (Docker 29 + WSL networking fix)..."
sudo update-alternatives --set iptables  /usr/sbin/iptables-legacy  || true
sudo update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy || true

echo "[3/5] Enabling systemd so Docker starts automatically..."
if ! grep -qs 'systemd=true' /etc/wsl.conf; then
    printf '[boot]\nsystemd=true\n' | sudo tee /etc/wsl.conf >/dev/null
fi

echo "[4/5] Enabling the Docker service..."
sudo systemctl enable docker 2>/dev/null || true

echo "[5/5] Letting you run Docker without sudo..."
sudo usermod -aG docker "$USER"

echo
echo "=================================================================="
echo " Requirements installed."
echo
echo " NOW DO THIS:"
echo "   1. In PowerShell (Windows) run:   wsl --shutdown"
echo "   2. Re-open the Ubuntu window."
echo "   3. Check it works:                docker ps      (no error)"
echo
echo " Then continue with STEP 1d in docs/STUDENT.md."
echo "=================================================================="
