#!/bin/bash
set -euo pipefail

# ---------------------------------------------------------------------------
# initial_setup.sh
#
# Provisions an EC2 instance and deploys the app.
#
# Prerequisites:
#   - INSTANCE_IP env variable must be set (e.g. export INSTANCE_IP=1.2.3.4)
#   - PEM key at ~/.ssh/isw-aws.pem
#   - rsync installed locally
#
# Usage:
#   export INSTANCE_IP=<your-ec2-public-ip>
#   bash initial_setup.sh
# ---------------------------------------------------------------------------

PEM_KEY="$HOME/.ssh/isw-aws.pem"
EC2_USER="ubuntu"          # Use ec2-user for Amazon Linux AMIs
APP_REMOTE_DIR="/home/${EC2_USER}/app"

# --- Validate ---
if [ -z "${INSTANCE_IP:-}" ]; then
  echo "ERROR: INSTANCE_IP is not set. Run: export INSTANCE_IP=<ec2-public-ip>"
  exit 1
fi

if [ ! -f "$PEM_KEY" ]; then
  echo "ERROR: PEM key not found at $PEM_KEY"
  exit 1
fi

chmod 400 "$PEM_KEY"

SSH="ssh -i $PEM_KEY -o StrictHostKeyChecking=no ${EC2_USER}@${INSTANCE_IP}"

echo "==> [1/3] Installing Docker on ${INSTANCE_IP}..."
$SSH << 'REMOTE'
set -e

# Install Docker on Ubuntu
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine, CLI, and plugins
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Enable and start Docker
sudo systemctl enable docker
sudo systemctl start docker

# Allow current user to run docker without sudo (takes effect on next login)
sudo usermod -aG docker "$USER"

echo "Docker $(docker --version) installed successfully."
echo "Docker Compose $(docker compose version) installed successfully."
echo "Docker Buildx $(docker buildx version) installed successfully."
REMOTE

echo "==> [2/3] Copying application files to ${INSTANCE_IP}:${APP_REMOTE_DIR}..."
rsync -az --progress \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache' \
  --exclude '.mypy_cache' \
  --exclude '.coverage' \
  -e "ssh -i $PEM_KEY -o StrictHostKeyChecking=no" \
  . "${EC2_USER}@${INSTANCE_IP}:${APP_REMOTE_DIR}"

echo "==> [3/3] Building and starting the API..."
$SSH << REMOTE
set -e
cd "${APP_REMOTE_DIR}"

# Shut down any running containers before redeploying
if sudo docker compose ps --quiet 2>/dev/null | grep -q .; then
  echo "Stopping running containers..."
  sudo docker compose down
fi

sudo docker compose up -d --build api
echo ""
echo "Container status:"
sudo docker compose ps api
REMOTE

echo ""
echo "Done. App is running at http://${INSTANCE_IP}:8000"
echo "Logs: ssh -i $PEM_KEY ${EC2_USER}@${INSTANCE_IP} 'cd ${APP_REMOTE_DIR} && sudo docker compose logs -f api'"
