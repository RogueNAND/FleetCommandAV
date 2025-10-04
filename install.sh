#!/bin/bash

# Ensure bash
if [ -z "$BASH_VERSION" ]; then
  echo "Error: run with bash, not sh." >&2
  exit 1
fi

# Robust mode: exit on error, unset vars, pipeline failures; better word-splitting rules
set -Eeuo pipefail
IFS=$'\n\t'

START_TS=$(date +%s)

# ---- Traps -------------------------------------------------------------------
on_error() {
  local exit_code=$?
  local line_no=${BASH_LINENO[0]:-?}
  local cmd=${BASH_COMMAND:-?}
  echo -e "\e[31mError: command failed (exit=$exit_code) at line $line_no: $cmd\e[0m" >&2
  exit "$exit_code"
}
on_exit() {
  local end_ts
  end_ts=$(date +%s)
  local elapsed=$(( end_ts - START_TS ))
  echo -e "\e[90mDone. Elapsed: ${elapsed}s\e[0m"
}
trap on_error ERR
trap on_exit EXIT

# ---- UI helpers --------------------------------------------------------------
readonly COLOR1="\e[32m"
readonly COLOR_INPUT="\e[36m"
readonly ENDCOLOR="\e[0m"

msg()    { echo -e "${COLOR1}$1${ENDCOLOR}"; }
prompt() { echo -ne "${COLOR_INPUT}$1${ENDCOLOR}"; }
die()    { echo -e "\e[31m$*\e[0m" >&2; exit 1; }
have()   { command -v "$1" >/dev/null 2>&1; }

# ---- Steps -------------------------------------------------------------------

install_docker() {
  if ! have docker || ! docker version >/dev/null 2>&1; then
    msg "Installing Docker..."

    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
$(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Add current user to docker group (effective next login)
    sudo usermod -aG docker "$USER" || true
    msg "Docker installed. Log out/in for 'docker' group to apply."
  else
    msg "Docker already installed."
  fi
}

deploy() {
  local config_dir="./datastore/companion"
  mkdir -p "$config_dir"

  sudo chown -R "1000:1000" "$config_dir"
  chmod -R 755 "$config_dir"

  msg "Starting services..."

  docker compose down --remove-orphans || true
  docker compose pull
  docker compose up -d --build
}

check_tailscale() {
  local container="vpn"
  local state_dir="./datastore/tailscale"
  mkdir -p "$state_dir"
  sudo chown -R "1000:1000" "$state_dir"
  chmod 700 "$state_dir"

  # Wait briefly to ensure container is up
  sleep 2

  # Is container running?
  if ! docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
    echo -e "\e[33mTailscale container not running; skipping setup.\e[0m"
    return
  fi

  # Check if already logged in
  if docker exec "$container" tailscale status 2>&1 | grep -q "Logged in as"; then
#    echo -e "\e[32mTailscale already logged in.\e[0m"
    return
  fi

  echo -e "\e[34mInitializing Tailscale...\e[0m"
  # Run tailscale up and capture output
  local output
  output=$(docker exec "$container" tailscale up 2>&1 || true)

  if echo "$output" | grep -q "https://login.tailscale.com"; then
    local url
    url=$(echo "$output" | grep -Eo 'https://login\.tailscale\.com[^ ]+')
    echo -e "\e[33mAuthorize Tailscale for this device:\e[0m\n$url"
  else
    echo -e "\e[31mUnexpected output from tailscale up:\e[0m\n$output"
  fi
}


# ---- Main --------------------------------------------------------------------
msg "Run as a regular user (sudo will be used as needed)."
msg "Updating system packages..."
sudo apt-get update -y && sudo apt-get upgrade -y

git config --global core.autocrlf input

install_docker
deploy
check_tailscale

msg "Setup complete 👍"
