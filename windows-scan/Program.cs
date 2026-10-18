using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.Win32;

namespace WindowsScan;

public class Program
{
    public static int Main(string[] args)
    {
        try
        {
            var output = args.Length > 1 && args[0] == "-o" ? args[1] : "profile.json";
            Console.Error.WriteLine("Scanning Windows system...");

            var profile = ScanSystem();

            var json = JsonSerializer.Serialize(profile, new JsonSerializerOptions
            {
                WriteIndented = true,
                DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
            });

            if (output == "-")
            {
                Console.WriteLine(json);
            }
            else
            {
                File.WriteAllText(output, json);
                Console.Error.WriteLine($"Profile written to {output}");
            }

            return 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Error: {ex.Message}");
            return 1;
        }
    }

    static Profile ScanSystem()
    {
        return new Profile
        {
            Windows = new WindowsInfo
            {
                Version = Environment.OSVersion.VersionString,
                Edition = GetWindowsEdition(),
                Architecture = Environment.Is64BitOperatingSystem ? "x64" : "x86",
                UserName = Environment.UserName
            },
            InstalledApps = ScanInstalledApps(),
            Path = Environment.GetEnvironmentVariable("PATH", EnvironmentVariableTarget.Machine)
                ?.Split(';').Where(p => !string.IsNullOrWhiteSpace(p)).ToArray() ?? [],
            Dotfiles = ScanDotfiles(),
            Keybindings = ScanKeybindings(),
            ShellConfig = ScanShellConfig(),
            BrowserExtensions = ScanBrowserExtensions(),
            SshConfig = ScanSshConfig(),
            TerminalConfig = ScanTerminalConfig()
        };
    }

    static string GetWindowsEdition()
    {
        try
        {
            using var key = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Microsoft\Windows NT\CurrentVersion");
            return key?.GetValue("EditionID")?.ToString() ?? "Unknown";
        }
        catch { return "Unknown"; }
    }

    static List<AppInfo> ScanInstalledApps()
    {
        var apps = new List<AppInfo>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        // Check common registry locations
        foreach (var hiveInfo in new[]
        {
            (Registry.CurrentUser, @"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (Registry.LocalMachine, @"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (Registry.LocalMachine, @"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")
        })
        {
            try
            {
                using var key = hiveInfo.Item1.OpenSubKey(hiveInfo.Item2);
                if (key == null) continue;

                foreach (var subKeyName in key.GetSubKeyNames())
                {
                    using var appKey = key.OpenSubKey(subKeyName);
                    if (appKey == null) continue;

                    var displayName = appKey.GetValue("DisplayName")?.ToString();
                    if (string.IsNullOrEmpty(displayName) || !seen.Add(displayName))
                        continue;

                    var displayNameKey = appKey.GetValue("DisplayName")?.ToString() ?? "";
                    apps.Add(new AppInfo
                    {
                        Name = displayNameKey,
                        Version = appKey.GetValue("DisplayVersion")?.ToString(),
                        Publisher = appKey.GetValue("Publisher")?.ToString(),
                        InstallLocation = appKey.GetValue("InstallLocation")?.ToString(),
                        UninstallString = appKey.GetValue("UninstallString")?.ToString(),
                        DisplayName = true
                    });
                }
            }
            catch { /* ignore */ }
        }

        // Also check winget if available
        try
        {
            var psi = new System.Diagnostics.ProcessStartInfo
            {
                FileName = "winget",
                Arguments = "list --accept-source-agreements",
                RedirectStandardOutput = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            var proc = System.Diagnostics.Process.Start(psi);
            if (proc != null)
            {
                var output = proc.StandardOutput.ReadToEnd();
                proc.WaitForExit(5000);

                foreach (var line in output.Split('\n'))
                {
                    var parts = line.Split('\t');
                    if (parts.Length >= 2 && !string.IsNullOrWhiteSpace(parts[0]))
                    {
                        var name = parts[0].Trim();
                        if (!seen.Add(name)) continue;
                        apps.Add(new AppInfo
                        {
                            Name = name,
                            Version = parts[1].Trim(),
                            WingetId = parts.Length >= 3 ? parts[2].Trim() : null
                        });
                    }
                }
            }
        }
        catch { /* winget not available */ }

        return apps;
    }

    static Dotfiles ScanDotfiles()
    {
        var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        var dotfiles = new Dotfiles();

        var shellDirs = new[]
        {
            (".bashrc", Path.Combine(home, ".bashrc")),
            (".bash_profile", Path.Combine(home, ".bash_profile")),
            (".vimrc", Path.Combine(home, ".vimrc")),
            (".gitconfig", Path.Combine(home, ".gitconfig")),
            (".ssh", Path.Combine(home, ".ssh")),
            (".npmrc", Path.Combine(home, ".npmrc")),
            (".git-credentials", Path.Combine(home, ".git-credentials")),
        };

        foreach (var (name, path) in shellDirs)
        {
            if (File.Exists(path))
                dotfiles.Files[name] = File.ReadAllText(path);
            else if (Directory.Exists(path))
            {
                foreach (var f in Directory.GetFiles(path))
                {
                    var fname = Path.GetFileName(f);
                    dotfiles.Files[$"{name}/{fname}"] = File.ReadAllText(f);
                }
            }
        }

        return dotfiles;
    }

    static Keybindings ScanKeybindings()
    {
        // Check for popular keybinding tools
        var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        var kb = new Keybindings();

        var vimrc = Path.Combine(home, ".vimrc");
        if (File.Exists(vimrc))
            kb.Vimrc = File.ReadAllText(vimrc);

        var vscodeKeybindings = Path.Combine(home, ".vscode", "keybindings.json");
        if (File.Exists(vscodeKeybindings))
            kb.VscodeKeybindings = File.ReadAllText(vscodeKeybindings);

        return kb;
    }

    static ShellConfig ScanShellConfig()
    {
        var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        var shell = new ShellConfig();

        var powershellProfile = Path.Combine(home, ".config", "powershell", "Microsoft.PowerShell_profile.ps1");
        if (!File.Exists(powershellProfile))
            powershellProfile = Path.Combine(home, "Documents", "WindowsPowerShell", "profile.ps1");
        if (File.Exists(powershellProfile))
            shell.PowerShellProfile = File.ReadAllText(powershellProfile);

        return shell;
    }

    static List<BrowserExt> ScanBrowserExtensions()
    {
        var exts = new List<BrowserExt>();
        var appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);

        // Chrome/Edge extensions
        foreach (var browser in new[] { "Google\\Chrome\\User Data\\Default\\Extensions", "Microsoft\\Edge\\User Data\\Default\\Extensions" })
        {
            var extPath = Path.Combine(appData, browser);
            if (Directory.Exists(extPath))
            {
                foreach (var dir in Directory.GetDirectories(extPath))
                {
                    var manifestPath = Path.Combine(dir, "manifest.json");
                    if (File.Exists(manifestPath))
                    {
                        try
                        {
                            var manifest = JsonDocument.Parse(File.ReadAllText(manifestPath));
                            var root = manifest.RootElement;
                            exts.Add(new BrowserExt
                            {
                                Name = root.GetProperty("name").GetString() ?? Path.GetFileName(dir),
                                Browser = Path.GetFileName(Path.GetDirectoryName(extPath) ?? "")
                            });
                        }
                        catch { }
                    }
                }
            }
        }

        return exts;
    }

    static SshConfig ScanSshConfig()
    {
        var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        var sshDir = Path.Combine(home, ".ssh");
        var config = new SshConfig();

        var configFile = Path.Combine(sshDir, "config");
        if (File.Exists(configFile))
            config.ConfigText = File.ReadAllText(configFile);

        if (Directory.Exists(sshDir))
        {
            foreach (var f in Directory.GetFiles(sshDir))
            {
                var fname = Path.GetFileName(f);
                if (fname == "config" || fname == "known_hosts") continue;
                if (fname.EndsWith(".pub") || fname.EndsWith(".pem"))
                    config.KeyFiles.Add(fname);
            }
        }

        return config;
    }

    static TerminalConfig ScanTerminalConfig()
    {
        var appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
        var localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);

        var config = new TerminalConfig();

        // Windows Terminal settings
        var wtPath = Path.Combine(localAppData, "Packages", "Microsoft.WindowsTerminal_8wekyb3d8bbwe", "LocalState", "settings.json");
        if (File.Exists(wtPath))
            config.WindowsTerminalSettings = File.ReadAllText(wtPath);

        // PowerShell profile path detection happens in ScanShellConfig

        return config;
    }
}

// ---- Models ----

public class Profile
{
    public WindowsInfo? Windows { get; set; }
    public List<AppInfo>? InstalledApps { get; set; }
    public string[]? Path { get; set; }
    public Dotfiles? Dotfiles { get; set; }
    public Keybindings? Keybindings { get; set; }
    public ShellConfig? ShellConfig { get; set; }
    public List<BrowserExt>? BrowserExtensions { get; set; }
    public SshConfig? SshConfig { get; set; }
    public TerminalConfig? TerminalConfig { get; set; }
}

public class WindowsInfo
{
    public string? Version { get; set; }
    public string? Edition { get; set; }
    public string? Architecture { get; set; }
    public string? UserName { get; set; }
}

public class AppInfo
{
    public string? Name { get; set; }
    public string? Version { get; set; }
    public string? Publisher { get; set; }
    public string? InstallLocation { get; set; }
    public string? UninstallString { get; set; }
    public string? WingetId { get; set; }
    public bool? DisplayName { get; set; }
}

public class Dotfiles
{
    public Dictionary<string, string> Files { get; set; } = new();
}

public class Keybindings
{
    public string? Vimrc { get; set; }
    public string? VscodeKeybindings { get; set; }
}

public class ShellConfig
{
    public string? PowerShellProfile { get; set; }
}

public class BrowserExt
{
    public string? Name { get; set; }
    public string? Browser { get; set; }
}

public class SshConfig
{
    public string? ConfigText { get; set; }
    public List<string> KeyFiles { get; set; } = new();
}

public class TerminalConfig
{
    public string? WindowsTerminalSettings { get; set; }
}