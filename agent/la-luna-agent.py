#!/usr/bin/env python3
import json,os,platform,socket,subprocess,time,urllib.request
API=os.environ.get("LA_LUNA_URL","").rstrip("/");AGENT=os.environ.get("LA_LUNA_AGENT_ID","");TOKEN=os.environ.get("LA_LUNA_AGENT_TOKEN","")
def cmd(x):
 try:return subprocess.check_output(x,shell=True,text=True,stderr=subprocess.DEVNULL,timeout=3).strip()
 except:return ""
def osi():
 d={}
 try:
  for line in open("/etc/os-release"):
   if "=" in line:
    k,v=line.rstrip().split("=",1);d[k]=v.strip('"')
 except:pass
 return {"name":d.get("PRETTY_NAME") or d.get("NAME") or platform.system(),"version":d.get("VERSION_ID") or platform.release(),"kernel":platform.release(),"architecture":platform.machine()}
def detect():
 provider="unknown";virt=cmd("systemd-detect-virt") or "bare-metal";cs=[];vendor=cmd("cat /sys/class/dmi/id/sys_vendor").lower();product=cmd("cat /sys/class/dmi/id/product_name").lower()
 if os.path.exists("/usr/bin/pveversion") or os.path.exists("/etc/pve"):provider="proxmox"
 elif "amazon" in vendor or "ec2" in product:provider="aws"
 elif "microsoft" in vendor:provider="azure"
 elif "google" in vendor:provider="gcp"
 if cmd("command -v docker"):cs.append("docker")
 if cmd("command -v kubectl") or os.path.exists("/etc/kubernetes"):cs.append("kubernetes")
 if cmd("command -v k3s"):cs.append("k3s")
 caps=cs[:]
 for n,c in [("frappe","command -v bench"),("prometheus","command -v prometheus"),("grafana","command -v grafana-server"),("redis","command -v redis-server"),("postgresql","command -v postgres"),("mysql","command -v mysql"),("nginx","command -v nginx"),("apache","command -v apache2 || command -v httpd"),("nodejs","command -v node"),("pm2","command -v pm2")]:
  if cmd(c):caps.append(n)
 return provider,virt,cs,caps
def metrics():
 load=os.getloadavg();mem=cmd("awk '/MemTotal/{t=$2*1024}/MemAvailable/{a=$2*1024}END{printf \"%.0f %.0f\",t-a,t}' /proc/meminfo").split();disk=os.statvfs("/");net=cmd("awk -F'[: ]+' 'NR>2{rx+=$3;tx+=$11}END{print rx,tx}' /proc/net/dev").split();cpu=cmd("awk -v RS='' '{u=$2+$4; t=$2+$4+$5; if(t>0) printf \"%.2f\",100*u/t}' /proc/stat");dr=cmd("docker ps -q 2>/dev/null | wc -l");ds=cmd("docker ps -aq -f status=exited 2>/dev/null | wc -l")
 return {"cpuPercent":float(cpu or 0),"memoryUsedBytes":int(mem[0]) if mem else 0,"memoryTotalBytes":int(mem[1]) if len(mem)>1 else 0,"diskUsedBytes":(disk.f_blocks-disk.f_bfree)*disk.f_frsize,"diskTotalBytes":disk.f_blocks*disk.f_frsize,"networkRxBytes":int(net[0]) if net else 0,"networkTxBytes":int(net[1]) if len(net)>1 else 0,"load1m":load[0],"load5m":load[1],"load15m":load[2],"uptimeSeconds":int(float(cmd("cat /proc/uptime").split()[0])),"containersRunning":int(dr or 0),"containersStopped":int(ds or 0)}
def once():
 provider,virt,cs,caps=detect();payload={"agentId":AGENT,"hostname":socket.gethostname(),"os":osi(),"platform":{"provider":provider,"virtualization":virt,"containers":",".join(cs) or None},"capabilities":caps,"metrics":metrics(),"metadata":{"agentVersion":"0.1.0","schemaVersion":1}}
 data=json.dumps(payload).encode();req=urllib.request.Request(API+"/api/agent/v1/heartbeat",data=data,headers={"Content-Type":"application/json","Authorization":"Bearer "+TOKEN,"User-Agent":"La-Luna-Agent/0.1.0"},method="POST");urllib.request.urlopen(req,timeout=10).read()
if __name__=="__main__":
 if not API.startswith("https://") or not AGENT or not TOKEN:raise SystemExit("HTTPS LA_LUNA_URL, LA_LUNA_AGENT_ID and LA_LUNA_AGENT_TOKEN are required")
 while True:
  try:once()
  except Exception as e:print("heartbeat failed:",e,flush=True)
  time.sleep(int(os.environ.get("LA_LUNA_INTERVAL","30")))
