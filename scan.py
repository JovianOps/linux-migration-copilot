#!/usr/bin/env python3
"""Linux Migration Copilot - scan Windows, export portable profile bundle."""

import os
import sys
import json
import zipfile
import hashlib
import argparse
from pathlib import Path
from datetime import datetime

SAFE_EXPORT_KEYS = {"apps", "dotfiles", "bash_aliases", "packages", "settings"}


class WindowsScanner:
    def __init__(self):
        self.profile = {
            "version": "1.0",
            "created": datetime.utcnow().isoformat() + "Z",
            "hostname": os.environ.get("COMPUTERNAME", "unknown"),
            "platform": "windows",
            "apps": [],
            "dotfiles": [],
            "bash_aliases": [],
            "packages": [],
            "settings": {},
        }

    def scan_installed_apps(self):
        """Scan installed Windows applications from registry and known paths."""
        import winreg
        apps = []
        # Registry: Uninstall key
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall") as k:
                    i = 0
                    while True:
                        try:
                            name = winreg.EnumKey(k, i)
                            with winreg.OpenKey(k, name) as app_key:
                                try:
                                    display = winreg.QueryValueEx(app_key, "DisplayName")[0]
                                    apps.append({"name": display, "source": "registry"})
                                except FileNotFoundError:
                                    pass
                            i += 1
                        except OSError:
                            break
            except PermissionError:
                pass
        # Common paths
        program_files = [
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ]
        for pf in program_files:
            if os.path.isdir(pf):
                for entry in sorted(os.listdir(pf)):
                    apps.append({"name": entry, "source": "programfiles", "path": os.path.join(pf, entry)})
        self.profile["apps"] = apps

    def scan_dotfiles(self):
        """Collect list of dotfiles (bash configs, ssh configs, etc.) for sync planning."""
        dotfiles = []
        home_dir = Path.home()
        common_dotfiles = [".bashrc", ".bash_profile", ".vimrc", ".gitconfig", ".ssh/config"]
        for name in common_dotfiles:
            path = home_dir / name
            if path.exists():
                dotfiles.append({
                    "name": str(path),
                    "size": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:16] if path.is_file() else "dir",
                })
        self.profile["dotfiles"] = dotfiles

    def scan_environment(self):
        """Collect environment settings for migration."""
        self.profile["settings"] = {
            "user": os.getlogin(),
            "home": str(Path.home()),
            "temp": os.environ.get("TEMP", ""),
        }

    def sanitize(self):
        """Remove sensitive keys before export."""
        sanitized = {}
        for key in SAFE_EXPORT_KEYS:
            sanitized[key] = self.profile.get(key, [])
        return {
            "version": self.profile["version"],
            "created": self.profile["created"],
            "hostname": self.profile["hostname"],
            "platform": self.profile["platform"],
            "profile_data": sanitized,
        }

    def export(self, output_file):
        """Export profile as portable bundle."""
        data = self.sanitize()
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)
        return output_file


def main(argv=None):
    parser = argparse.ArgumentParser(description="Linux Migration Copilot - Windows Scanner")
    parser.add_argument("output", nargs="?", default="profile.lmc", help="Output profile file (default: profile.lmc)")
    args = parser.parse_args(argv)

    scanner = WindowsScanner()
    scanner.scan_installed_apps()
    scanner.scan_dotfiles()
    scanner.scan_environment()

    out = scanner.export(args.output)
    print(f"Profile exported: {out}")
    print(f"Apps: {len(scanner.profile['apps'])}")
    print(f"Dotfiles: {len(scanner.profile['dotfiles'])}")


if __name__ == "__main__":
    main()
