# Zeno-Zeno-SSH

A Python-based suite to manage and execute commands across multiple systems via SSH. It includes both a scriptable CLI and a high-performance interactive GUI.

## Features

### Interactive GUI (`ssh_gui.py`)
*   **VTE Terminal Engine**: Powered by the same engine used by GNOME Terminal for full shell interactivity (supports `vim`, `htop`, tab completion).
*   **Master Broadcast Bar**: Inject commands or passwords into all active terminal sessions simultaneously.
*   **Integrated Host Editor**: Update your `hosts.txt` and reconnect without restarting the application.
*   **Native Linux Integration**: Built with GTK 3 and PyGObject.

### Automation CLI (`src/ssh_admin.py`)
*   **Scriptable Execution**: Parallel or serial command execution across multiple hosts.
*   **Logging & Sudo**: Built-in logging to `ssh_admin.log` and support for privilege escalation.

## Installation (Debian/Ubuntu)

1. **Install System Dependencies**:
   ```bash
   sudo apt update
   sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-vte-2.91 openssh-client
   ```

2. **Clone and Install Python Requirements**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### GUI
```bash
python3 zeno_gui.py
```

### CLI
```bash
python3 src/zeno_admin.py run "uptime" --hosts hosts.txt --user myuser
```

## Configuration
Add your target hosts to `hosts.txt`. You can group them using `[group_name]` syntax.
