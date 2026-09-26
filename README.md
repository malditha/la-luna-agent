# La Luna Agent

Official Linux monitoring agent for **La Luna Ops**.

Discovers server OS, virtualization/cloud environment, container platforms and common services, then sends health and telemetry to an authorized La Luna Ops control plane over outbound HTTPS.

## V1 discovery
Linux OS/kernel/architecture; virtualization; Proxmox VE; AWS/Azure host hints; Docker; Kubernetes/k3s; Frappe; PostgreSQL; MySQL/MariaDB; Redis; Nginx; Prometheus; Grafana.

## Metrics
CPU, memory, root filesystem, network counters, load averages, uptime and Docker container counts.

## Install
Use **La Luna Ops → Infrastructure → Enroll server**. Never publish enrollment credentials.

    curl -fsSL https://raw.githubusercontent.com/malditha/la-luna-agent/main/install.sh -o /tmp/la-luna-install.sh
    sudo bash /tmp/la-luna-install.sh

## Service
    systemctl status la-luna-agent --no-pager
    journalctl -u la-luna-agent -n 100 --no-pager

Config is `/etc/la-luna-agent.env` mode 0600.

## License
Public source, but licensed **only for La Luna Ops use**. This is source-available, not open source. See LICENSE.
