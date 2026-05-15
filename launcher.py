#!/usr/bin/env python3
"""
Astro.bot Local Launcher — starts all 6 agent servers.

Ports:
    8000 — Orchestrator  (adk web — browser UI)
    8001 — data_science
    8002 — persona_aggregator
    8003 — economist
    8004 — project_manager
    8005 — scheduler
"""
import os, signal, subprocess, sys, time
from pathlib import Path

MESH_DIR = Path(__file__).parent
os.chdir(MESH_DIR)

# Load .env
env_file = MESH_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

SPECIALIST_AGENTS = [
    {"name": "data_science",       "port": 8001},
    {"name": "persona_aggregator", "port": 8002},
    {"name": "economist",          "port": 8003},
    {"name": "project_manager",    "port": 8004},
    {"name": "scheduler",          "port": 8005},
]
processes = []

def start_api_server(name, port):
    cmd = ["adk","api_server","--host","0.0.0.0",
           "--port", str(port),"--allow_origins","*", str(MESH_DIR)]
    log = open(f"/tmp/astrobot_{name}.log", "w")
    print(f"  {name:<22} → http://localhost:{port}  [/tmp/astrobot_{name}.log]")
    return subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=os.environ)

def start_orchestrator():
    cmd = ["adk","web","--host","0.0.0.0","--port","8000",
           "--allow_origins","*", str(MESH_DIR)]
    print(f"  orchestrator           → http://localhost:8000  [UI]")
    return subprocess.Popen(cmd, env=os.environ)

def shutdown(s=None, f=None):
    print("\nShutting down..."); [p.terminate() for p in processes]; sys.exit(0)

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

print("="*60)
print("  Astro.bot Multi-Agent Mesh — Local Launcher")
print("="*60)
print("\nStarting specialist agents...")
for a in SPECIALIST_AGENTS:
    processes.append(start_api_server(a["name"], a["port"]))

print("\nWaiting 6s for agents to boot...")
time.sleep(6)

print("\nStarting orchestrator UI...")
orch = start_orchestrator()
processes.append(orch)

print("\n" + "="*60)
print("  READY — Web Preview → Port 8000 → select 'orchestrator'")
print("  Ctrl+C to stop all")
print("="*60 + "\n")

try:
    orch.wait()
except KeyboardInterrupt:
    shutdown()
