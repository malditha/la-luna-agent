# La Luna Agent

Official Linux monitoring agent for **La Luna Ops**. It pushes a heartbeat every 30 seconds over outbound HTTPS and never opens an inbound port.

## What it reports (v1.2)
- **Identity & type**: hostname, distro (e.g. "Ubuntu 22.04.4 LTS"), kernel, architecture, virtualization, and server type: cloud VM, virtual machine, bare metal, Proxmox host or container/LXC (override with `LA_LUNA_SERVER_TYPE`).
- **Location**: cloud provider, region, zone and instance type from the provider's link-local metadata service (AWS, Google Cloud, Azure, DigitalOcean, Hetzner; others by hardware vendor), plus the timezone. For on-prem servers set `LA_LUNA_LOCATION` (e.g. "Manila office rack 2") or set it in La Luna Ops.
- **Hardware**: CPU model, cores and sockets, swap.
- **Metrics**: CPU (current, not since-boot), memory, root disk, network counters (La Luna Ops turns them into bandwidth), load averages, uptime.
- **Containers**: Docker (version, running/total containers, images, Compose, Swarm), Kubernetes (k8s/k3s/microk8s/RKE2: version, nodes ready, pods running), Podman, LXC, Proxmox VE (VMs and CTs).
- **Services**: nginx, Apache, Caddy, MySQL/MariaDB, PostgreSQL, Redis, MongoDB, PHP-FPM, Docker, containerd, SSH, fail2ban, ufw/firewalld, cron, node_exporter, including critical services that are stopped or failed.
- **Patch status**: pending and security updates and reboot-required, via apt or dnf/yum (re-checked every 6 hours, `LA_LUNA_PATCH_INTERVAL`).
- **Traffic & bots**: reads only lines appended to the nginx/apache access log since the last heartbeat. It splits requests into humans and known bots and counts attack probes (`/.env`, `/.git`, `wp-login.php`…). Only counts and bot names are sent, never IPs, URLs or log lines. Set `LA_LUNA_ACCESS_LOG` to override the path.

The inventory is cached and refreshed every 10 minutes (`LA_LUNA_INVENTORY_INTERVAL`).

## Install
Use **La Luna Ops → Infrastructure → Enroll server**, which prints the command and credentials. Never publish enrollment credentials.

    curl -fsSL https://raw.githubusercontent.com/malditha/la-luna-agent/main/install.sh -o /tmp/la-luna-install.sh
    sudo bash /tmp/la-luna-install.sh

## Update an installed agent
Keeps `/etc/la-luna-agent.env`:

    curl -fsSL https://raw.githubusercontent.com/malditha/la-luna-agent/main/update.sh -o /tmp/la-luna-update.sh
    sudo bash /tmp/la-luna-update.sh

## Service
    systemctl status la-luna-agent --no-pager
    journalctl -u la-luna-agent -n 100 --no-pager

Config is `/etc/la-luna-agent.env` (mode 0600). State (log offsets, patch and inventory cache) lives in `/var/lib/la-luna-agent`.

## Security
- The agent refuses to run unless `LA_LUNA_URL` is `https://` (localhost excepted), so the token is never sent in clear text.
- La Luna Ops stores only a SHA-256 hash of the token. Rotate it from the server page; the old token stops working immediately.
- The systemd unit runs with `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome` and a private `/tmp`.

## License
Public source, but licensed **only for La Luna Ops use**. This is source-available, not open source. See LICENSE.
