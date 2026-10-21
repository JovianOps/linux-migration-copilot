# Linux Migration Copilot

**Your Windows desktop, now on Linux. In one command.**

Point `lmc-scan` at your Windows PC. Point `lmc-install` at your Linux box. Your entire desktop is rebuilt.

## How It Works

1. **Scan Windows** → exports `profile.lmc` (apps, dotfiles, settings)
2. **Transfer** → USB stick or network share
3. **Install Linux** → reads profile and installs equivalents
4. **Sync** → `lmc-sync` daemon keeps both envs consistent

## Installation

```bash
pip install -e .
```

## Usage

### Windows (scan)
```bash
lmc-scan profile.lmc
```

### Linux (install)
```bash
lmc-install profile.lmc
```

### Sync daemon (any machine)
```bash
lmc-sync
lmc-sync --once   # single cycle
lmc-sync --status # show current state
```

## App Mapping

Over 45 Windows apps mapped to Linux equivalents:
- Photoshop → Krita
- Office → LibreOffice
- Steam → Steam (native Linux)
- Discord → Discord
- Git → Git

See `mappings/apps.json` for the full list.

## Security

Export is sanitized — SSH keys and credentials are never included in the profile bundle.

## Requirements

- **Windows scanner:** Python 3.8+ (winreg for app scan)
- **Linux installer:** Python 3.8+ (apt-get)
- **Sync daemon:** Python 3.8+, rsync (optional)

## License

MIT
