#!/usr/bin/env python3
"""Linux Migration Copilot - installer side: port your Windows profile to Linux."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

MAPPINGS_FILE = Path(__file__).parent.parent / "mappings" / "apps.json"


def load_mappings() -> dict[str, str]:
    if not MAPPINGS_FILE.exists():
        return {}
    data = json.loads(MAPPINGS_FILE.read_text())
    return data.get("mappings", {})


def map_app(windows_name: str, mappings: dict[str, str]) -> Optional[str]:
    """Best-effort mapping from Windows app to Linux package."""
    for win_pattern, linux_pkg in mappings.items():
        if win_pattern.lower() in windows_name.lower() or windows_name.lower() in win_pattern.lower():
            return linux_pkg
    # Partial match
    wl = windows_name.lower()
    for win_pattern, linux_pkg in mappings.items():
        if wl.replace(" ", "") in win_pattern.replace(" ", "").lower():
            return linux_pkg
    return None


def detect_package_manager() -> str:
    for pm in ("apt", "dnf", "pacman", "zypper", "nix"):
        if shutil.which(pm):
            return pm
    return "apt"


def install_package(pm: str, package: str) -> bool:
    """Install a single package using the detected package manager."""
    try:
        if pm == "apt":
            subprocess.run(["sudo", "apt", "install", "-y", package], check=True, timeout=120)
        elif pm == "dnf":
            subprocess.run(["sudo", "dnf", "install", "-y", package], check=True, timeout=120)
        elif pm == "pacman":
            subprocess.run(["sudo", "pacman", "-S", "--noconfirm", package], check=True, timeout=120)
        elif pm == "zypper":
            subprocess.run(["sudo", "zypper", "install", "-y", package], check=True, timeout=120)
        elif pm == "nix":
            subprocess.run(["nix-env", "-i", package], check=True, timeout=120)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"  FAILED: {package} ({e})", file=sys.stderr)
        return False


def install_flatpak(package: str) -> bool:
    """Install via flatpak if available."""
    if not shutil.which("flatpak"):
        return False
    try:
        subprocess.run(["flatpak", "install", "-y", package], check=True, timeout=120)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def port_dotfiles(profile: dict, home: Path) -> None:
    """Copy dotfiles from profile to home directory."""
    dotfiles = profile.get("dotfiles", {})
    files = dotfiles.get("files", {}) if isinstance(dotfiles, dict) else {}

    for name, content in files.items():
        if "/" in name:
            parts = name.split("/", 1)
            subdir = home / parts[0]
            subdir.mkdir(parents=True, exist_ok=True)
            (subdir / parts[1]).write_text(content)
        else:
            (home / name).write_text(content)
        print(f"  Ported: ~/{name}")


def port_ssh_config(profile: dict, home: Path) -> None:
    ssh_config = profile.get("ssh_config", {})
    if not ssh_config:
        return

    ssh_dir = home / ".ssh"
    ssh_dir.mkdir(exist_ok=True)

    config_text = ssh_config.get("configText", "")
    if config_text:
        (ssh_dir / "config").write_text(config_text)
        print("  Ported: ~/.ssh/config")

    for keyfile in ssh_config.get("keyFiles", []):
        print(f"  Note: manually copy ~/.ssh/{keyfile} from backup")


def port_terminal_config(profile: dict, home: Path) -> None:
    """Port terminal settings - best effort."""
    tc = profile.get("terminal_config", {})
    if tc.get("windowsTerminalSettings"):
        # Map to common Linux terminal configs
        lines = [
            "# Windows Terminal settings ported (review needed)",
            "# Consider using Alacritty, Kitty, or GNOME Terminal",
        ]
        config = json.loads(tc["windowsTerminalSettings"])
        schemes = config.get("schemes", [])
        if schemes:
            for scheme in schemes[:3]:
                name = scheme.get("name", "unknown")
                lines.append(f"# Color scheme: {name}")
        (home / ".terminal_schemes_migrated.txt").write_text("\n".join(lines))
        print("  Ported terminal color schemes (review and adapt)")


def generate_install_report(installed: list[str], skipped: list[str], home: Path) -> None:
    report = home / ".migration_report.txt"
    lines = [
        "# Linux Migration Report",
        f"Installed packages: {len(installed)}",
        f"Skipped (no mapping): {len(skipped)}",
        "",
        "## Installed",
    ]
    for p in installed:
        lines.append(f"  - {p}")
    lines.append("")
    lines.append("## Skipped (manual review needed)")
    for s in skipped:
        lines.append(f"  - {s}")
    report.write_text("\n".join(lines))
    print(f"\nReport written to {report}")


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print("Usage: lmc-install profile.json", file=sys.stderr)
        return 1

    profile_path = Path(argv[0])
    if not profile_path.exists():
        print(f"Error: profile not found at {profile_path}", file=sys.stderr)
        return 1

    print(f"Loading profile from {profile_path}...")
    profile = json.loads(profile_path.read_text())

    mappings = load_mappings()
    pm = detect_package_manager()
    print(f"Detected package manager: {pm}")

    installed: list[str] = []
    skipped: list[str] = []

    apps = profile.get("installed_apps", [])
    print(f"\nProcessing {len(apps)} Windows apps...")

    for app in apps:
        name = app.get("name", "")
        linux_pkg = map_app(name, mappings)
        if linux_pkg:
            print(f"  {name} -> {linux_pkg}")
            if install_package(pm, linux_pkg):
                installed.append(linux_pkg)
            elif install_flatpak(linux_pkg):
                installed.append(f"flatpak:{linux_pkg}")
            else:
                skipped.append(f"{name} (tried: {linux_pkg})")
        else:
            print(f"  {name} -> NO MAPPING")
            skipped.append(name)

    print("\nPorting dotfiles and configs...")
    home = Path.home()
    port_dotfiles(profile, home)
    port_ssh_config(profile, home)
    port_terminal_config(profile, home)

    # Port PATH entries
    win_path = profile.get("path", [])
    if win_path:
        bashrc = home / ".bashrc"
        existing = bashrc.read_text() if bashrc.exists() else ""
        additions = "\n".join(f'export PATH="$PATH:{p}"' for p in win_path if "/" in p)
        if additions and additions not in existing:
            with open(bashrc, "a") as f:
                f.write(f"\n# Ported from Windows\n{additions}\n")
            print("  Ported PATH entries to ~/.bashrc")

    generate_install_report(installed, skipped, home)
    print("\nMigration complete! Review ~/.migration_report.txt for details.")
    return 0


if __name__ == "__main__":
    sys.exit(main())