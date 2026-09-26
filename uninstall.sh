#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" -eq 0 ]||{ echo "Run with sudo.";exit 1; }
systemctl disable --now la-luna-agent 2>/dev/null||true
rm -f /etc/systemd/system/la-luna-agent.service
systemctl daemon-reload
rm -rf /opt/la-luna-agent /var/lib/la-luna-agent
rm -f /etc/la-luna-agent.env
echo "La Luna Agent removed. Delete its server record separately in La Luna Ops if desired."
