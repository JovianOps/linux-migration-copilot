#!/usr/bin/env python3
"""Linux Migration Copilot - read profile and install Linux equivalents."""

import os
import sys
import json
import shutil
import subprocess
import argparse
from pathlib import Path


class LinuxInstaller:
    def __init__(self, profile_file):
        with open(profile_file) as f:
            self.profile = json.load(f)
        self.mappings = self._load_mappings()

    def _load_mappings(self):
        """Load Windows→Linux app mappings."""
        mapping_file = Path(__file__).parent / "mappings" / "apps.json"
        if mapping_file.exists():
            with open(mapping_file) as f:
                return json.load(f)
        return {}

    def install_apps(self):
        """Install Linux equivalents of Windows apps."""
        installed = []
        skipped = []
        for app in self.profile.get("profile_data", {}).get("apps", []):
            name = app.get("name", "")
            linux_equiv = self.mappings.get(name, {}).get("linux", None)
            if linux_equiv:
                result = subprocess.run(
                    ["sudo", "apt-get", "install", "-y", linux_equiv],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    installed.append(linux_equiv)
                else:
                    skipped.append(name)
            else:
                skipped.append(name)
        return installed, skipped

    def install_dotfiles(self):
        """Set up dotfile sync via lmc-sync."""
        dotfiles = self.profile.get("profile_data", {}).get("dotfiles", [])
        print(f"Found {len(dotfiles)} dotfiles to sync")
        print("Run 'lmc-sync' to start the sync daemon")

    def run(self):
        """Execute full migration install."""
        print(f"Installing profile from: {self.profile.get('hostname', 'unknown')}")
        apps, skipped = self.install_apps()
        self.install_dotfiles()
        print(f"\nInstalled: {len(apps)} apps")
        print(f"Skipped: {len(skipped)} apps (no Linux equivalent)")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Linux Migration Copilot - Installer")
    parser.add_argument("profile", nargs="?", default="profile.lmc", help="Profile file (default: profile.lmc)")
    args = parser.parse_args()

    if not Path(args.profile).exists():
        print(f"Error: {args.profile} not found")
        sys.exit(1)

    installer = LinuxInstaller(args.profile)
    installer.run()


if __name__ == "__main__":
    main()
