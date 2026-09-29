#!/usr/bin/env python3
import json,os,platform,re,socket,subprocess,time,urllib.request
VERSION="1.2.0"
API=os.environ.get("LA_LUNA_URL","").rstrip("/"); AGENT=os.environ.get("LA_LUNA_AGENT_ID",""); TOKEN=os.environ.get("LA_LUNA_AGENT_TOKEN","")
STATE_DIR=os.environ.get("LA_LUNA_STATE_DIR","/var/lib/la-luna-agent"); INTERVAL=int(os.environ.get("LA_LUNA_INTERVAL","30")); PATCH_INTERVAL=int(os.environ.get("LA_LUNA_PATCH_INTERVAL","21600")); INVENTORY_INTERVAL=int(os.environ.get("LA_LUNA_INVENTORY_INTERVAL","600"))
def cmd(x,timeout=3):
 try:return subprocess.check_output(x,shell=True,text=True,stderr=subprocess.DEVNULL,timeout=timeout).strip()
 except:return ""
def rc(x,timeout=60):
 try:return subprocess.run(x,shell=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=timeout).returncode
 except:return -1
def load_state(name):
 try:
  with open(os.path.join(STATE_DIR,name)) as f:return json.load(f)
 except:return {}
def save_state(name,data):
 try:
  os.makedirs(STATE_DIR,exist_ok=True)
  with open(os.path.join(STATE_DIR,name),"w") as f:json.dump(data,f)
 except Exception as e:print("state write failed:",e,flush=True)
def detect():
 provider="unknown"; virt=cmd("systemd-detect-virt") or "bare-metal"; containers=[]
 if os.path.exists("/usr/bin/pveversion") or os.path.exists("/etc/pve"): provider="proxmox"
 elif os.path.exists("/sys/hypervisor/uuid") and cmd("cat /sys/hypervisor/uuid").lower().startswith("ec2"): provider="aws"
 elif "microsoft" in cmd("cat /sys/class/dmi/id/sys_vendor").lower(): provider="azure"
 if cmd("command -v docker"): containers.append("docker")
 if cmd("command -v kubectl") or os.path.exists("/etc/kubernetes"): containers.append("kubernetes")
 if cmd("command -v k3s"): containers.append("k3s")
 caps=containers[:]
 for n,c in [("frappe","command -v bench"),("prometheus","command -v prometheus"),("grafana","command -v grafana-server"),("redis","command -v redis-server"),("postgresql","command -v postgres"),("mysql","command -v mysql"),("nginx","command -v nginx"),("apache","command -v apache2 || command -v httpd"),("nodejs","command -v node"),("pm2","command -v pm2")]:
  if cmd(c): caps.append(n)
 return provider,virt,containers,caps
_cpu_prev=None
def cpu_percent():
 # Busy share since the previous reading (not the since-boot average): /proc/stat "cpu" = user nice system idle iowait irq softirq steal.
 global _cpu_prev
 def read():
  f=[int(x) for x in open("/proc/stat").readline().split()[1:9]]; idle=f[3]+f[4]; return sum(f),idle
 try:
  if _cpu_prev is None: _cpu_prev=read(); time.sleep(0.5)
  cur=read(); dt=cur[0]-_cpu_prev[0]; di=cur[1]-_cpu_prev[1]; _cpu_prev=cur
  return round(100*(dt-di)/dt,2) if dt>0 else 0.0
 except Exception: return 0.0
def metrics():
 load=os.getloadavg(); mem=cmd("awk '/MemTotal/{t=$2*1024}/MemAvailable/{a=$2*1024}END{printf \"%.0f %.0f\",t-a,t}' /proc/meminfo").split(); disk=os.statvfs("/"); net=cmd("awk -F'[: ]+' 'NR>2 && $2!=\"lo\"{rx+=$3;tx+=$11}END{print rx,tx}' /proc/net/dev").split(); cpu=cpu_percent(); dr=cmd("docker ps -q 2>/dev/null | wc -l"); ds=cmd("docker ps -aq -f status=exited 2>/dev/null | wc -l")
 return {"cpuPercent":float(cpu or 0),"memoryUsedBytes":int(mem[0]) if mem else 0,"memoryTotalBytes":int(mem[1]) if len(mem)>1 else 0,"diskUsedBytes":(disk.f_blocks-disk.f_bfree)*disk.f_frsize,"diskTotalBytes":disk.f_blocks*disk.f_frsize,"networkRxBytes":int(net[0]) if net else 0,"networkTxBytes":int(net[1]) if len(net)>1 else 0,"load1m":load[0],"load5m":load[1],"load15m":load[2],"uptimeSeconds":int(float(cmd("cat /proc/uptime").split()[0])),"containersRunning":int(dr or 0),"containersStopped":int(ds or 0)}

# --- Patch status (cached; package managers are slow) ---
def check_patches():
 if cmd("command -v apt"):
  lines=[l for l in cmd("apt list --upgradable 2>/dev/null",120).splitlines() if "upgradable" in l]
  return {"manager":"apt","pending":len(lines),"security":sum(1 for l in lines if "-security" in l),"rebootRequired":os.path.exists("/var/run/reboot-required")}
 for pm in ("dnf","yum"):
  if cmd("command -v "+pm):
   out=cmd(pm+" -C -q check-update 2>/dev/null",120); pending=len([l for l in out.splitlines() if re.match(r"^\S+\.\S+\s+\S+\s+\S+",l)])
   sec=len([l for l in cmd(pm+" -C -q updateinfo list --security 2>/dev/null",120).splitlines() if l.strip()])
   return {"manager":pm,"pending":pending,"security":sec,"rebootRequired":bool(cmd("command -v needs-restarting")) and rc("needs-restarting -r")==1}
 return None
_patch_cache={}
def patches():
 global _patch_cache
 cached=_patch_cache or load_state("patches.json")
 if "ts" in cached and time.time()-cached["ts"]<PATCH_INTERVAL: return cached.get("data")
 data=check_patches()
 if data: data["checkedAt"]=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
 _patch_cache={"ts":time.time(),"data":data}; save_state("patches.json",_patch_cache); return data

# --- Access-log traffic: humans vs bots (reads only lines appended since the last heartbeat) ---
KNOWN_BOTS=["Googlebot","bingbot","YandexBot","Baiduspider","DuckDuckBot","Applebot","facebookexternalhit","AhrefsBot","SemrushBot","MJ12bot","DotBot","PetalBot","Bytespider","Amazonbot","GPTBot","ChatGPT-User","ClaudeBot","CCBot","PerplexityBot","python-requests","curl","Wget","Go-http-client","HeadlessChrome","zgrab","masscan","Nuclei"]
BOT_RE=re.compile(r"bot|crawl|spider|slurp|scrapy|headless|scan",re.I); UA_RE=re.compile(r'"([^"]*)"\s*$'); REQ_RE=re.compile(r'"[A-Z]+ ([^ "]+)')
PROBE_RE=re.compile(r"wp-login\.php|xmlrpc\.php|/\.env|/\.git|phpmyadmin|/cgi-bin/|\.\./|/etc/passwd|/vendor/phpunit|/boaform|/actuator",re.I)
def access_log():
 p=os.environ.get("LA_LUNA_ACCESS_LOG")
 for c in ([p] if p else [])+["/var/log/nginx/access.log","/var/log/apache2/access.log","/var/log/httpd/access_log"]:
  if c and os.path.isfile(c) and os.access(c,os.R_OK): return c
 return None
_traffic_state={}
def traffic(window):
 global _traffic_state
 path=access_log()
 if not path: return None
 st=os.stat(path); state=_traffic_state or load_state("traffic.json")
 if state.get("path")!=path or state.get("inode")!=st.st_ino or st.st_size<state.get("offset",0): offset=st.st_size if state.get("path")!=path else 0
 else: offset=state.get("offset",0)
 total=bots=suspicious=0; top={}
 with open(path,"rb") as f:
  f.seek(offset); chunk=f.read(5*1024*1024); end=f.tell()
 for raw in chunk.decode("utf-8","replace").splitlines():
  if not raw.strip(): continue
  total+=1; m=UA_RE.search(raw); ua=m.group(1) if m else ""; r=REQ_RE.search(raw)
  if (r and PROBE_RE.search(r.group(1))) or ua in ("","-"): suspicious+=1
  name=next((b for b in KNOWN_BOTS if b.lower() in ua.lower()),None) or ("other-bot" if BOT_RE.search(ua) else None)
  if name: bots+=1; top[name]=top.get(name,0)+1
 _traffic_state={"path":path,"inode":st.st_ino,"offset":end}; save_state("traffic.json",_traffic_state)
 return {"source":"agent:"+os.path.basename(os.path.dirname(path)),"windowSeconds":window,"total":total,"bots":bots,"suspicious":suspicious,"topBots":[{"name":k,"count":v} for k,v in sorted(top.items(),key=lambda x:-x[1])[:10]]}

# --- Inventory (v1.2): distro, hardware, server type, location, services, container platforms. Cached; cheap to send. ---
def os_release():
 d={}
 try:
  for l in open("/etc/os-release"):
   k,_,v=l.strip().partition("=")
   if k: d[k]=v.strip('"')
 except Exception: pass
 return d
def dmi(n): return cmd("cat /sys/class/dmi/id/"+n).strip()
def http(url,headers=None,method="GET",timeout=1.0):
 # Cloud metadata services are link-local and answer in milliseconds; anything slower means "not this cloud".
 try:
  req=urllib.request.Request(url,headers=headers or {},method=method)
  return urllib.request.urlopen(req,timeout=timeout).read().decode().strip()
 except Exception: return ""
def cloud():
 vendor=(dmi("sys_vendor")+" "+dmi("product_name")+" "+dmi("bios_vendor")).lower()
 if "amazon" in vendor or cmd("cat /sys/hypervisor/uuid").lower().startswith("ec2"):
  t=http("http://169.254.169.254/latest/api/token",{"X-aws-ec2-metadata-token-ttl-seconds":"60"},"PUT"); h={"X-aws-ec2-metadata-token":t} if t else {}
  return "aws",http("http://169.254.169.254/latest/meta-data/placement/region",h),http("http://169.254.169.254/latest/meta-data/placement/availability-zone",h),http("http://169.254.169.254/latest/meta-data/instance-type",h)
 if "google" in vendor:
  z=http("http://metadata.google.internal/computeMetadata/v1/instance/zone",{"Metadata-Flavor":"Google"}).split("/")[-1]; m=http("http://metadata.google.internal/computeMetadata/v1/instance/machine-type",{"Metadata-Flavor":"Google"}).split("/")[-1]
  return "gcp",z.rsplit("-",1)[0] if z else "",z,m
 if "microsoft" in vendor:
  j=http("http://169.254.169.254/metadata/instance/compute?api-version=2021-02-01",{"Metadata":"true"})
  try: c=json.loads(j); return "azure",c.get("location",""),c.get("zone",""),c.get("vmSize","")
  except Exception: return "azure","","",""
 if "digitalocean" in vendor: return "digitalocean",http("http://169.254.169.254/metadata/v1/region"),"",""
 if "hetzner" in vendor:
  z=http("http://169.254.169.254/hetzner/v1/metadata/availability-zone"); return "hetzner",z.rsplit("-",1)[0] if z else "",z,""
 for key,name in (("linode","linode"),("akamai","linode"),("vultr","vultr"),("oraclecloud","oracle"),("alibaba","alibaba"),("ovh","ovh"),("scaleway","scaleway")):
  if key in vendor: return name,"","",""
 if os.path.exists("/etc/pve") or cmd("command -v pveversion"): return "proxmox","","",""
 if "vmware" in vendor: return "vmware","","",""
 return "","","",""
def container_platforms():
 out={}
 if cmd("command -v docker"):
  v=cmd("docker version --format '{{.Server.Version}}' 2>/dev/null") or cmd("docker --version").replace("Docker version","").split(",")[0].strip()
  out["docker"]={"version":v or None,"running":int(cmd("docker ps -q 2>/dev/null | wc -l") or 0),"total":int(cmd("docker ps -aq 2>/dev/null | wc -l") or 0),"images":int(cmd("docker images -q 2>/dev/null | wc -l") or 0),"compose":bool(cmd("docker compose version 2>/dev/null") or cmd("command -v docker-compose")),"swarm":cmd("docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null")=="active"}
 if cmd("command -v podman"): out["podman"]={"version":cmd("podman --version").split()[-1] if cmd("podman --version") else None,"running":int(cmd("podman ps -q 2>/dev/null | wc -l") or 0)}
 flavor=("k3s" if cmd("command -v k3s") else "microk8s" if cmd("command -v microk8s") else "rke2" if os.path.exists("/etc/rancher/rke2") else "kubernetes" if (cmd("command -v kubelet") or os.path.exists("/etc/kubernetes")) else None)
 if flavor:
  # The systemd unit hides /root (ProtectHome), so point plain kubectl at the cluster admin config when present.
  kube_cfg=next((p for p in ("/etc/kubernetes/admin.conf","/etc/rancher/rke2/rke2.yaml") if os.path.exists(p)),None)
  kc="k3s kubectl" if flavor=="k3s" else "microk8s kubectl" if flavor=="microk8s" else "kubectl"+(" --kubeconfig "+kube_cfg if kube_cfg else "")
  nodes=cmd(kc+" get nodes --no-headers 2>/dev/null",5).splitlines(); pods=cmd(kc+" get pods -A --no-headers 2>/dev/null",5).splitlines()
  out["kubernetes"]={"flavor":flavor,"version":(cmd(kc+" version -o json 2>/dev/null",5) and (json.loads(cmd(kc+" version -o json 2>/dev/null",5) or "{}").get("serverVersion") or {}).get("gitVersion")) or None,"nodes":len(nodes) or None,"nodesReady":sum(1 for n in nodes if " Ready" in n) or None,"pods":len(pods) or None,"podsRunning":sum(1 for p in pods if " Running " in p) or None,"kubeletActive":cmd("systemctl is-active kubelet k3s k3s-agent snap.microk8s.daemon-kubelite 2>/dev/null").count("active")>0}
 if cmd("command -v lxc-ls") or cmd("command -v lxc"): out["lxc"]={"containers":len(cmd("lxc-ls 2>/dev/null").split()) or None}
 if cmd("command -v qm"): out["proxmox"]={"vms":max(0,len(cmd("qm list 2>/dev/null").splitlines())-1),"containers":max(0,len(cmd("pct list 2>/dev/null").splitlines())-1),"version":cmd("pveversion 2>/dev/null").split("/")[1] if "/" in cmd("pveversion 2>/dev/null") else None}
 return out
SERVICES=[("nginx","nginx"),("apache","apache2 httpd"),("caddy","caddy"),("mysql","mysql mariadb mysqld"),("postgresql","postgresql"),("redis","redis-server redis"),("mongodb","mongod"),("php-fpm","php-fpm php8.3-fpm php8.2-fpm php8.1-fpm php7.4-fpm"),("docker","docker"),("containerd","containerd"),("ssh","ssh sshd"),("fail2ban","fail2ban"),("ufw","ufw"),("firewalld","firewalld"),("cron","cron crond"),("node_exporter","node_exporter prometheus-node-exporter")]
def services():
 out=[]
 for name,units in SERVICES:
  states=cmd("systemctl is-active "+units+" 2>/dev/null").split()
  if "active" in states: out.append({"name":name,"active":True})
  elif any(s in ("inactive","failed","activating") for s in states) and name in ("nginx","apache","mysql","postgresql","redis","docker","fail2ban"): out.append({"name":name,"active":False,"state":"failed" if "failed" in states else "stopped"})
 return out
def server_type(provider,virt,conts):
 if virt in ("lxc","lxc-libvirt","openvz","systemd-nspawn","docker","podman","wsl"): return "container"
 if provider=="proxmox" and virt in ("none","bare-metal",""): return "proxmox-host"
 if provider in ("aws","gcp","azure","digitalocean","hetzner","linode","vultr","oracle","alibaba","ovh","scaleway"): return "cloud-vm"
 if virt in ("none","bare-metal",""): return "bare-metal"
 return "virtual-machine"
_inventory={}
def inventory(provider,virt):
 global _inventory
 cached=_inventory or load_state("inventory.json")
 if "ts" in cached and time.time()-cached["ts"]<INVENTORY_INTERVAL: return cached.get("data",{})
 r=os_release(); prov,region,zone,itype=cloud()
 cpu_model=cmd("awk -F': ' '/model name/{print $2; exit}' /proc/cpuinfo") or cmd("lscpu | awk -F': +' '/Model name/{print $2; exit}'")
 swap=cmd("awk '/SwapTotal/{t=$2*1024}/SwapFree/{f=$2*1024}END{printf \"%.0f %.0f\",t-f,t}' /proc/meminfo").split()
 conts=container_platforms()
 data={"os":{"name":r.get("NAME") or platform.system(),"version":r.get("VERSION_ID") or platform.release(),"pretty":r.get("PRETTY_NAME"),"id":r.get("ID")},
  "hardware":{"cpuModel":cpu_model or None,"cores":os.cpu_count(),"sockets":int(cmd("lscpu | awk -F': +' '/Socket\\(s\\)/{print $2; exit}'") or 0) or None,"swapUsedBytes":int(swap[0]) if swap else None,"swapTotalBytes":int(swap[1]) if len(swap)>1 else None,"vendor":dmi("sys_vendor") or None,"product":dmi("product_name") or None},
  "location":{"provider":prov or provider or None,"region":region or None,"zone":zone or None,"instanceType":itype or None,"timezone":cmd("timedatectl show -p Timezone --value 2>/dev/null") or time.tzname[0],"label":os.environ.get("LA_LUNA_LOCATION") or None},
  "serverType":os.environ.get("LA_LUNA_SERVER_TYPE") or server_type(prov or provider,virt,conts),
  "containers":conts,"services":services(),"inventoryAt":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}
 _inventory={"ts":time.time(),"data":data}; save_state("inventory.json",_inventory); return data

def once(window):
 provider,virt,containers,caps=detect()
 try: inv=inventory(provider,virt)
 except Exception as e: print("inventory failed:",e,flush=True); inv={}
 osi=inv.get("os") or {}
 payload={"agentId":AGENT,"agentVersion":VERSION,"hostname":socket.gethostname(),"os":{"name":osi.get("name") or platform.system(),"version":osi.get("version") or platform.release(),"kernel":platform.release(),"architecture":platform.machine()},"platform":{"provider":(inv.get("location") or {}).get("provider") or provider,"virtualization":virt,"containers":",".join(containers) or None},"capabilities":caps,"metrics":metrics(),"metadata":inv}
 for key,fn in (("patches",patches),("traffic",lambda:traffic(window))):
  try:
   v=fn()
   if v: payload[key]=v
  except Exception as e: print(key,"collection failed:",e,flush=True)
 data=json.dumps(payload).encode(); req=urllib.request.Request(API+"/api/agent/v1/heartbeat",data=data,headers={"Content-Type":"application/json","Authorization":"Bearer "+TOKEN,"User-Agent":"la-luna-agent/"+VERSION},method="POST"); urllib.request.urlopen(req,timeout=10).read()
if __name__=="__main__":
 if not API or not AGENT or not TOKEN: raise SystemExit("Set LA_LUNA_URL, LA_LUNA_AGENT_ID and LA_LUNA_AGENT_TOKEN")
 if not API.startswith("https://") and not API.startswith("http://localhost") and not API.startswith("http://127.0.0.1"): raise SystemExit("LA_LUNA_URL must use https:// so the agent token is never sent in clear text")
 last=time.time()
 while True:
  now=time.time()
  try: once(max(1,int(now-last)))
  except Exception as e: print("heartbeat failed:",e,flush=True)
  last=now; time.sleep(INTERVAL)
