# Zeno-SSH Windows Distribution

This directory contains standalone Windows binaries for Zeno-SSH. These versions are portable, require no installation, and have been optimized for Windows using `CustomTkinter` and `Paramiko`.

## Included Binaries
- **`ZenoSSH-Windows.exe`**: Interactive GUI version.
- **`ZenoSSH-CLI.exe`**: Command-line automation version.

---

## 1. Interactive GUI (`ZenoSSH-Windows.exe`)

The GUI provides a powerful environment for managing multiple servers at once.

### Key Features
- **Server Browser**: Quickly switch between systems defined in your `hosts.txt`.
- **Dual Tabs**: Each connection has a **Terminal** tab for commands and a **File Transfer** tab for data.
- **Manual Connection**: Per-tab credentials (User/Password) with "Enter to Connect" support.
- **Broadcast Bar**: Execute a command across **all active tabs** simultaneously. Found at the bottom of the main window.
- **Command History**: Navigate previous commands using **Up/Down arrow keys** in both terminal and broadcast entries.
- **ANSI Color Support**: High-performance rendering of Linux terminal colors.
- **Integrated Editor**: Edit and reload `hosts.txt` directly from the "Config" tab.

### Examples
- **Broadcasting Updates**: Open 5 server tabs, type `sudo apt update` in the broadcast bar at the bottom, and hit Enter.
- **Quick File Upload**: Go to the "File Transfer" tab, click **Browse** to select a local script, type `/tmp/setup.sh` in remote path, select **SCP**, and click **Upload**.

---

## 2. Automation CLI (`ZenoSSH-CLI.exe`)

The CLI is perfect for PowerShell scripts or rapid one-off tasks.

### Command Execution (`run`)
- **Simple uptime check**:
  ```powershell
  .\ZenoSSH-CLI.exe run "uptime" --user admin --ask-pass
  ```
- **Run command on specific group**:
  ```powershell
  .\ZenoSSH-CLI.exe run "ls /var/www" --group web-servers --user root
  ```

### File Transfers (`put` / `get`)
- **Upload a file to all servers**:
  ```powershell
  .\ZenoSSH-CLI.exe put "C:\setup.ps1" "/tmp/setup.ps1" --user admin
  ```
- **Download logs from all servers**:
  ```powershell
  .\ZenoSSH-CLI.exe get "/var/log/nginx/access.log" "nginx_backup.log" --user root
  ```
  *Note: The CLI automatically prefixes the local filename with the server address (e.g., `192.168.1.10_nginx_backup.log`) to prevent overwriting.*

---

## Configuration (`hosts.txt`)
The apps automatically look for `hosts.txt` in the same folder as the `.exe`. If it doesn't exist, the GUI will create a template for you.

**Format Example:**
```text
[web]
10.0.0.1
10.0.0.2

[db]
db-master.local
```

---

## Troubleshooting
- **Black Screen**: Ensure your SSH server supports `xterm-256color`.
- **Connection Failed**: Verify your username and password. If using an SSH key, ensure it is in OpenSSH format.
- **No Text Output**: Check if your server sends non-standard control characters. The app filters common artifacts but might miss exotic ones.
