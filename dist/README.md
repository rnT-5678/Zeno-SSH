# Zeno-SSH Windows Distribution

This directory contains standalone Windows binaries for Zeno-SSH. These versions are portable, require no installation, and have been optimized for Windows using `CustomTkinter` and `Paramiko`.

## Included Binaries
- **`ZenoSSH-Windows.exe`**: Interactive GUI version with a modern split-pane SFTP browser and verified icon.
- **`ZenoSSH-CLI.exe`**: Command-line automation version with the same verified icon.

---

## 1. Interactive GUI (`ZenoSSH-Windows.exe`)

The GUI provides a powerful environment for managing multiple servers at once.

### Key Features
- **Visual SFTP Browser**: Professional dual-pane explorer (Local vs. Remote).
- **Double-Click Navigation**: Open folders or initiate transfers with a double-click.
- **Auto-CD on Search**: Automatically navigate to the directory of found files.
- **Highlighting**: Found files are highlighted in **Yellow** in the file list.
- **Clickable Results**: Click any search result in the log to jump to that folder.
- **Robust Search**: Recursion depth limit (15 levels) prevents crashes on deep systems.
- **🏠 Home Button**: Quickly reset the remote browser to your home directory.
- **Command History**: Use **Up/Down arrow keys** in both terminal and broadcast entries.
- **ANSI Color Support**: High-performance rendering of Linux terminal colors.

### Examples
- **Recursive Search**: Type `*.log` in the search bar and click 🔍 **Search**. The browser will jump to the first result, and others will be clickable in the log.
- **Easy Transfer**: Select a file, navigate the other pane to your destination, and click the arrows (→ or ←) to transfer.

---

## 2. Automation CLI (`ZenoSSH-CLI.exe`)

Perfect for rapid one-off tasks or integration into your existing scripts.

- **Run command**: `.\ZenoSSH-CLI.exe run "uptime" --user admin --ask-pass`
- **Upload file**: `.\ZenoSSH-CLI.exe put "C:\setup.ps1" "/tmp/setup.ps1" --user admin`

---

## Configuration (`hosts.txt`)
The apps automatically look for `hosts.txt` in the same folder as the `.exe`. 
**SFTP Account Format**: `Alias | Host | Port | User` (Password will be prompted on connection).
