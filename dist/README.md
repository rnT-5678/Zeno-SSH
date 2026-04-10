# Zeno-SSH Windows Distribution

This directory contains the standalone Windows binaries for Zeno-SSH. These versions have been optimized for Windows compatibility using `customtkinter` and `paramiko`.

## Contents
- `ZenoSSH-Windows.exe`: Interactive Graphical User Interface.
- `ZenoSSH-CLI.exe`: Automation Command Line Interface.

---

## 1. Interactive GUI (`ZenoSSH-Windows.exe`)
The GUI provides a tabbed environment for managing multiple SSH sessions simultaneously.

### Getting Started
1. **Launch**: Double-click `ZenoSSH-Windows.exe`.
2. **Host Configuration**: 
   - Click the **"Config"** tab to edit your `hosts.txt`.
   - Add hosts one per line. You can use groups like `[web-servers]`.
   - Click **"Save & Reload"** to update the Server Browser on the left.
3. **Connecting**: 
   - Enter your **User** and **Password** in the top bar.
   - Click a host in the **Server Browser** to open a new terminal tab and connect automatically.
4. **Broadcast**:
   - Type a command in the **"Broadcast command..."** box at the top and press Enter (or click "Broadcast") to send that command to **all** active terminal tabs at once.

---

## 2. Automation CLI (`ZenoSSH-CLI.exe`)
The CLI is designed for scripting and rapid command execution across groups of servers.

### Basic Usage
Open a terminal (Command Prompt or PowerShell) in this directory and run:

```
.\ZenoSSH-CLI.exe run "uptime" --user myusername --ask-pass
```

### Common Commands
- **Target a specific group**:
  ```
  .\ZenoSSH-CLI.exe run "df -h" --group web-servers --user admin
  ```

- **Use a specific identity key**:
  ```
  .\ZenoSSH-CLI.exe run "ls -la" --identity C:\Users\me\.ssh\id_rsa
  ```

- **Disable parallel execution (run one by one)**:
  ```
  .\ZenoSSH-CLI.exe run "reboot" --no-parallel
  ```

- **Enable logging to a file**:
  ```
  .\ZenoSSH-CLI.exe run "tail /var/log/syslog" --log
  ```
### CLI Options
- `command`: The shell command to execute (required).
- `--hosts`: Path to the host list file (default: `hosts.txt`).
- `--group`: Target group from the host file (default: `all`).
- `--user`: SSH username.
- `--ask-pass`: Prompt for the SSH password securely.
- `--identity`: Path to a private key file.
- `--parallel/--no-parallel`: Execute in parallel or serially (default: parallel).
- `--log`: Enable logging results to `ssh_admin.log`.

---

## Configuration (`hosts.txt`)
The application expects a `hosts.txt` file in the same directory. Example format:

```text
[web-servers]
192.168.1.10
192.168.1.11

[db-servers]
database.internal.local
```
