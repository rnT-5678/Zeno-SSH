# Zeno-SSH

A powerful, cross-platform Python-based suite for managing and executing commands across multiple systems via SSH. Zeno-SSH provides a high-performance interactive GUI and a scriptable CLI, now synchronized with full feature parity across Linux and Windows.

## Key Features

- **Multi-Terminal GUI**: Manage multiple SSH sessions in a tabbed interface.
- **Broadcast Control**: Send commands to all active connections or specific host groups simultaneously.
- **Integrated File Transfer**: Support for both **SFTP** and **SCP** protocols within the GUI and CLI.
- **Command History**: Terminal-like up/down arrow navigation for both individual and broadcast entries.
- **Host Management**: Easy group-based host configuration with an integrated editor.
- **Windows Port**: Fully functional standalone `.exe` versions with ANSI color support and no Python dependency.

---

## 1. Linux (Debian/Ubuntu)

### Installation
1. **Install System Dependencies**:
   ```bash
   sudo apt update
   sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-vte-2.91 openssh-client
   ```
2. **Install Python Requirements**:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Application
- **GUI**: `python3 zeno_gui.py`
- **CLI**: `python3 src/zeno_admin.py --help`

---

## 2. Windows (Standalone Binaries)

For Windows users, pre-compiled standalone binaries are available in the [dist/](./dist/) directory. No Python installation is required.

### Quick Start
1. **Navigate to `dist/`**:
2. **Launch GUI**: Double-click `ZenoSSH-Windows.exe`.
3. **Launch CLI**: Run `ZenoSSH-CLI.exe` from PowerShell or CMD.

Refer to the [Detailed Windows Documentation](./dist/README.md) for examples and advanced usage.

---

## 3. Automation CLI Detailed Usage

The CLI is designed for rapid automation across your server clusters.

### Command Execution (`run`)
Execute a command across all hosts in `hosts.txt`:
```bash
python3 src/zeno_admin.py run "uptime" --user admin --ask-pass
```

Target a specific group (e.g., `[web-servers]`):
```bash
python3 src/zeno_admin.py run "df -h" --group web-servers --user admin
```

### File Transfer (`put` / `get`)
Upload a local file to all servers in a group:
```bash
python3 src/zeno_admin.py put "config.conf" "/etc/app/config.conf" --group staging --user root
```

Download a file from all servers (automatically appends hostname to local file):
```bash
python3 src/zeno_admin.py get "/var/log/syslog" "system.log" --user admin
```

---

## 4. Configuration (`hosts.txt`)
The application uses a simple INI-like format for managing systems.

```text
[web-servers]
192.168.1.10
web-01.example.com

[database]
10.0.0.5
```

---

## Technical Details
- **Backend**: Powered by `Paramiko` and `Fabric` for robust SSH/SFTP/SCP handling.
- **Linux Frontend**: Built with `GTK 3` and `VTE` for native performance.
- **Windows Frontend**: Built with `CustomTkinter` for a modern look and feel.
