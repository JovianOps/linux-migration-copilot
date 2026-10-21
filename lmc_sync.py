#!/usr/bin/env python3
"""Linux Migration Copilot - sync daemon: keep envs in sync post-migration."""

import json
import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

SYNC_DIR = Path.home() / ".lmc" / "sync"
INTERVAL = int(os.environ.get("LMC_SYNC_INTERVAL", "300"))


def get_hostname():
    return platform.node()


def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return socket.gethostbyname(socket.gethostname())


def scan_local_state():
    """Scan current machine's state for sync comparison."""
    state = {
        "hostname": get_hostname(),
        "ip": get_ip(),
        "platform": platform.system(),
        "timestamp": time.time(),
        "dotfiles": {},
        "apps": [],
        "bash_aliases": [],
    }
    if SYNC_DIR.exists():
        for f in SYNC_DIR.iterdir():
            if f.is_file() and not f.name.endswith(".json"):
                try:
                    state["dotfiles"][f.name] = f.read_text()[:10000]
                except Exception:
                    pass
    bashrc = Path.home() / ".bashrc"
    if bashrc.exists():
        for line in bashrc.read_text().splitlines():
            if line.strip().startswith("alias "):
                state["bash_aliases"].append(line.strip())
    return state


def load_peer_state(peer_file):
    if not peer_file.exists():
        return None
    try:
        return json.loads(peer_file.read_text())
    except Exception:
        return None


def load_config():
    config_file = SYNC_DIR / "sync_config.json"
    if config_file.exists():
        try:
            return json.loads(config_file.read_text())
        except Exception:
            pass
    return {"peers": [], "auto_sync": True, "interval": INTERVAL}


def save_local_state(state):
    SYNC_DIR.mkdir(parents=True, exist_ok=True)
    state_file = SYNC_DIR / f"state_{get_hostname()}.json"
    state_file.write_text(json.dumps(state, indent=2, default=str))


def run_sync_cycle():
    """One sync cycle: scan, exchange states, sync differences."""
    config = load_config()
    local_state = scan_local_state()
    save_local_state(local_state)
    results = {"scanned": len(local_state["dotfiles"]) + len(local_state["bash_aliases"]), "synced_to": [], "errors": []}
    for peer in config.get("peers", []):
        peer_host = peer.get("host", "")
        peer_file = SYNC_DIR / f"state_{peer.get('name', '')}.json"
        peer_state = load_peer_state(peer_file)
        if peer_state:
            synced = sync_dotfiles_to_peer(peer_state, local_state, peer_host)
            results["synced_to"].append(f"{peer.get('name', '')}: {synced}")
        else:
            results["synced_to"].append(f"{peer.get('name', '')}: no peer state found")
    return results


def sync_dotfiles_to_peer(peer_state, local_state, peer_host):
    """Sync local dotfiles to peer machine."""
    synced = []
    peer_dotfiles = peer_state.get("dotfiles", {})
    for name, content in local_state["dotfiles"].items():
        if name not in peer_dotfiles or peer_dotfiles[name] != content:
            local_file = SYNC_DIR / name
            if local_file.exists():
                dst = f"{peer_host}:{SYNC_DIR}/{name}"
                try:
                    subprocess.run(["rsync", "-avz", str(local_file), dst], timeout=60, check=False)
                    synced.append(name)
                except FileNotFoundError:
                    pass
    return synced


def watch_loop():
    """Continuous sync loop."""
    config = load_config()
    if not config.get("auto_sync", True):
        print("Auto-sync disabled. Run manually.")
        return
    interval = config.get("interval", INTERVAL)
    print(f"LMC sync daemon started (interval: {interval}s)")
    print(f"Hostname: {get_hostname()}, IP: {get_ip()}")
    print(f"Sync dir: {SYNC_DIR}")
    print("Press Ctrl+C to stop.\n")
    while True:
        try:
            results = run_sync_cycle()
            print(f"[{time.strftime('%H:%M:%S')}] Scanned: {results['scanned']} items")
            for line in results["synced_to"]:
                print(f"  -> {line}")
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\nSync daemon stopped.")
            break
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] ERROR: {e}")
            time.sleep(interval)


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) > 0 and argv[0] == "--once":
        results = run_sync_cycle()
        print(json.dumps(results, indent=2, default=str))
        return 0
    if len(argv) > 0 and argv[0] == "--config":
        config = load_config()
        print(json.dumps(config, indent=2))
        return 0
    if len(argv) > 0 and argv[0] == "--status":
        state = scan_local_state()
        print(json.dumps(state, indent=2, default=str))
        return 0
    watch_loop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
