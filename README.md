# Zeno-SSH

A Python-based suite to manage and execute commands across multiple systems via SSH. It includes both a scriptable CLI and a high-performance interactive GUI.

## Features

### Interactive GUI (`ssh_gui.py`)
*   **VTE Terminal Engine**: Powered by the same engine used by GNOME Terminal for full shell interactivity (supports `vim`, `htop`, tab completion).
*   **Master Broadcast Bar**: Inject commands or passwords into all active terminal sessions simultaneously.
*   **Integrated Host Editor**: Update your `hosts.txt` and reconnect without restarting the application.
*   **Native Linux Integration**: Built with GTK 3 and PyGObject.

### Automation CLI (`src/zeno_admin.py`)
*   **Scriptable Execution**: Parallel or serial command execution across multiple hosts.
*   **Logging & Sudo**: Built-in logging to `ssh_admin.log` and support for privilege escalation.

## Installation & Usage

### Linux (Debian/Ubuntu)

1. **Install System Dependencies**:
   ```bash
   sudo apt update
   sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-vte-2.91 openssh-client
   ```

2. **Install Python Requirements**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run**:
   - GUI: `python3 zeno_gui.py`
   - CLI: `python3 src/zeno_admin.py run "uptime"`

### Windows (Standalone Binaries)

For Windows users, pre-compiled standalone binaries are available in the [dist/](./dist/) directory. No Python installation is required.

1. **Download**: Navigate to the `dist/` folder.
2. **Run GUI**: Double-click `ZenoSSH-Windows.exe`.
3. **Run CLI**: Use `ZenoSSH-CLI.exe` from PowerShell or Command Prompt.

Refer to the [Windows Documentation](./dist/README.md) for detailed Windows usage instructions.

## Configuration
Add your target hosts to `hosts.txt`. You can group them using `[group_name]` syntax.
