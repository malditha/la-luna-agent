# Troubleshooting

Status:

    systemctl status la-luna-agent --no-pager

Logs:

    journalctl -u la-luna-agent -n 100 --no-pager

Restart:

    sudo systemctl restart la-luna-agent

Config permissions:

    sudo stat -c '%a %U:%G %n' /etc/la-luna-agent.env

Expected: `600 root:root`. Do not print or paste this file publicly because it contains the agent credential.
