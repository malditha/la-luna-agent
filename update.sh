#!/usr/bin/env bash
# Upgrade an installed La Luna Agent in place: new agent + systemd unit, keeps /etc/la-luna-agent.env (credentials).
set -euo pipefail
BASE="https://raw.githubusercontent.com/malditha/la-luna-agent/main"
if [ "$(id -u)" -ne 0 ];then echo "Run the updater with sudo.";exit 1;fi
[ -f /etc/la-luna-agent.env ]||{ echo "La Luna Agent is not installed (no /etc/la-luna-agent.env). Use install.sh.";exit 1; }
command -v curl >/dev/null||{ echo "curl is required";exit 1; }
tmp="$(mktemp)";trap 'rm -f "$tmp"' EXIT
curl -fsSL "$BASE/agent/la-luna-agent.py" -o "$tmp"
python3 -m py_compile "$tmp"
install -d -m 0755 /opt/la-luna-agent /var/lib/la-luna-agent
install -m 0755 "$tmp" /opt/la-luna-agent/la-luna-agent.py
curl -fsSL "$BASE/systemd/la-luna-agent.service" -o /etc/systemd/system/la-luna-agent.service
systemctl daemon-reload
systemctl restart la-luna-agent
echo "La Luna Agent updated to $(grep -oP 'VERSION="\K[^"]+' /opt/la-luna-agent/la-luna-agent.py)."
systemctl --no-pager --full status la-luna-agent||true
