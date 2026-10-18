# Linux Migration Copilot

One-click bridge from Windows to Linux.

## How it works

1. **Scan** — Run the Windows scanner to inventory your apps, dotfiles, SSH keys, and configs
2. **Transfer** — Copy `profile.json` to your Linux machine (USB stick)
3. **Install** — Run the installer to map apps to Linux equivalents and port your setup

## Build & Run

### Windows scanner
```powershell
cd windows-scan
dotnet run -c Release -o profile.json
```

### Linux installer
```bash
cd linux-install
pip install -e .
lmc-install profile.json
```

## License

MIT