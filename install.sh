#!/usr/bin/env bash
set -euo pipefail
BASE="https://raw.githubusercontent.com/malditha/la-luna-agent/main"
if [ "$(id -u)" -ne 0 ];then echo "Run installer with sudo.";exit 1;fi
command -v curl >/dev/null||{ echo "curl is required";exit 1; }
command -v python3 >/dev/null||{ echo "python3 is required";exit 1; }
ask(){ local n="$1" p="$2" s="$3" v="${!n:-}";if [ -z "$v" ];then if [ "$s" = yes ];then read -r -s -p "$p: " v;echo;else read -r -p "$p: " v;fi;fi;printf -v "$n" '%s' "$v"; }
ask LA_LUNA_URL "La Luna Ops URL (https://...)" no
ask LA_LUNA_AGENT_ID "Agent ID" no
ask LA_LUNA_AGENT_TOKEN "Enrollment credential" yes
case "$LA_LUNA_URL" in https://*) ;; *) echo "La Luna Ops URL must use HTTPS";exit 1;;esac
install -d -m 0755 /opt/la-luna-agent /var/lib/la-luna-agent
curl -fsSL "$BASE/agent/la-luna-agent.py" -o /opt/la-luna-agent/la-luna-agent.py
chmod 0755 /opt/la-luna-agent/la-luna-agent.py
umask 077
printf 'LA_LUNA_URL=%s\nLA_LUNA_AGENT_ID=%s\nLA_LUNA_AGENT_TOKEN=%s\nLA_LUNA_INTERVAL=30\n' "$LA_LUNA_URL" "$LA_LUNA_AGENT_ID" "$LA_LUNA_AGENT_TOKEN" >/etc/la-luna-agent.env
chmod 0600 /etc/la-luna-agent.env
curl -fsSL "$BASE/systemd/la-luna-agent.service" -o /etc/systemd/system/la-luna-agent.service
systemctl daemon-reload
systemctl enable --now la-luna-agent
echo "La Luna Agent installed."
systemctl --no-pager --full status la-luna-agent||true
