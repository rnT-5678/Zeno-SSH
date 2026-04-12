import customtkinter as ctk
import paramiko
import threading
import os
import sys
import time
import re

class HostTerminal(ctk.CTkFrame):
    def __init__(self, master, host, user, password=None, identity=None):
        super().__init__(master)
        self.host = host
        self.user = user
        self.password = password
        self.identity = identity
        self.client = None
        self.shell = None
        
        # Regex to find ANSI escape sequences
        self.ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
        
        # Define color map for common ANSI codes
        self.color_map = {
            '30': 'black', '31': '#e74c3c', '32': '#2ecc71', '33': '#f1c40f',
            '34': '#3498db', '35': '#9b59b6', '36': '#1abc9c', '37': '#ecf0f1',
            '90': '#95a5a6', '91': '#ff6b6b', '92': '#51cf66', '93': '#fcc419',
            '94': '#339af0', '95': '#cc5de8', '96': '#22b8cf', '97': '#f8f9fa'
        }
        
        # Connection Controls
        self.ctrl_frame = ctk.CTkFrame(self)
        self.ctrl_frame.pack(fill="x", padx=5, pady=5)
        
        self.user_var = ctk.StringVar(value=user)
        self.user_input = ctk.CTkEntry(self.ctrl_frame, textvariable=self.user_var, width=120)
        self.user_input.pack(side="left", padx=5)
        
        self.pwd_var = ctk.StringVar(value=password if password else "")
        self.pwd_input = ctk.CTkEntry(self.ctrl_frame, textvariable=self.pwd_var, show="*", placeholder_text="Password", width=120)
        self.pwd_input.pack(side="left", padx=5)
        
        self.conn_btn = ctk.CTkButton(self.ctrl_frame, text="Connect", command=self.start_connection, width=100)
        self.conn_btn.pack(side="left", padx=5)
        
        # Tabs
        self.tab_container = ctk.CTkTabview(self)
        self.tab_container.pack(fill="both", expand=True, padx=5, pady=5)
        self.tab_container.add("Terminal")
        self.tab_container.add("File Transfer")
        
        # Terminal Tab (Move existing UI here)
        self.text_area = ctk.CTkTextbox(self.tab_container.tab("Terminal"), font=("Courier New", 12), text_color="#ecf0f1", fg_color="black")
        self.text_area.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.entry = ctk.CTkEntry(self.tab_container.tab("Terminal"), placeholder_text="Enter command...")
        self.entry.pack(fill="x", padx=5, pady=5)
        self.entry.bind("<Return>", self.send_command)

        # File Transfer Tab
        self.sftp_frame = ctk.CTkFrame(self.tab_container.tab("File Transfer"))
        self.sftp_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(self.sftp_frame, text="Local Path:").pack(anchor="w")
        self.local_path = ctk.CTkEntry(self.sftp_frame, placeholder_text="C:/path/to/local/file")
        self.local_path.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(self.sftp_frame, text="Remote Path:").pack(anchor="w")
        self.remote_path = ctk.CTkEntry(self.sftp_frame, placeholder_text="/home/user/remote_file")
        self.remote_path.pack(fill="x", pady=(0, 10))
        
        btn_box = ctk.CTkFrame(self.sftp_frame, fg_color="transparent")
        btn_box.pack(fill="x")
        
        self.upload_btn = ctk.CTkButton(btn_box, text="Upload (Put)", command=lambda: self.sftp_op("upload"), width=120)
        self.upload_btn.pack(side="left", padx=5)
        
        self.download_btn = ctk.CTkButton(btn_box, text="Download (Get)", command=lambda: self.sftp_op("download"), width=120)
        self.download_btn.pack(side="left", padx=5)
        
        self.sftp_log = ctk.CTkTextbox(self.sftp_frame, height=150, font=("Courier New", 11))
        self.sftp_log.pack(fill="both", expand=True, pady=10)
        self.sftp_log.configure(state="disabled")

        # Setup tags for colors (Rest of existing init...)
        
        self.status_callback = None

    def start_connection(self):
        self.user = self.user_var.get()
        self.password = self.pwd_var.get()
        self.conn_btn.configure(state="disabled", text="Connecting...")
        threading.Thread(target=self._ssh_thread, daemon=True).start()
        
    def connect(self, status_callback):
        self.status_callback = status_callback
        self.append_text(f"[*] Ready to connect to {self.host}. Click 'Connect' to begin.\n")
        
    def _ssh_thread(self):
        try:
            self.append_text(f"[*] Connecting to {self.host} as {self.user}...\n")
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            self.client.connect(
                hostname=self.host,
                username=self.user,
                password=self.password,
                key_filename=self.identity,
                timeout=15,
                allow_agent=True,
                look_for_keys=True
            )
            
            # Request a terminal that supports color
            self.shell = self.client.invoke_shell(term='xterm-256color', width=120, height=40)
            self.append_text(f"[+] Connected successfully!\n")
            self.conn_btn.configure(text="Connected")
            if self.status_callback:
                self.status_callback(self.host, "success")
                
            while self.shell:
                if self.shell.recv_ready():
                    data = self.shell.recv(8192).decode('utf-8', errors='ignore')
                    self.append_text(data)
                elif self.shell.exit_status_ready():
                    self.append_text("\n[!] Connection closed by remote host.\n")
                    self.conn_btn.configure(state="normal", text="Connect")
                    break
                else:
                    time.sleep(0.01)
                    
        except Exception as e:
            self.append_text(f"[-] Connection failed: {e}\n")
            self.conn_btn.configure(state="normal", text="Connect")
            if self.status_callback: self.status_callback(self.host, "error")

    def log_sftp(self, msg):
        self.sftp_log.configure(state="normal")
        self.sftp_log.insert("end", f"{msg}\n")
        self.sftp_log.see("end")
        self.sftp_log.configure(state="disabled")

    def sftp_op(self, op_type):
        if not self.client:
            self.log_sftp("[-] Error: Connect via SSH first.")
            return
            
        local = self.local_path.get().strip()
        remote = self.remote_path.get().strip()
        
        if not local or not remote:
            self.log_sftp("[-] Error: Provide both local and remote paths.")
            return
            
        threading.Thread(target=self._sftp_thread, args=(op_type, local, remote), daemon=True).start()

    def _sftp_thread(self, op_type, local, remote):
        try:
            self.log_sftp(f"[*] Starting {op_type}...")
            sftp = self.client.open_sftp()
            
            def progress(seen, total):
                # We could update a progress bar here
                pass

            if op_type == "upload":
                sftp.put(local, remote, callback=progress)
            else:
                sftp.get(remote, local, callback=progress)
                
            sftp.close()
            self.log_sftp(f"[+] {op_type.capitalize()} complete!")
        except Exception as e:
            self.log_sftp(f"[-] SFTP Error: {e}")

    def send_command(self, event=None):
        cmd = self.entry.get()
        if self.shell:
            self.shell.send(cmd + "\n")
            self.entry.delete(0, 'end')
        else:
            self.append_text("[-] Not connected.\n")

    def append_text(self, text):
        self.text_area.configure(state="normal")
        
        # Simple ANSI parser
        parts = self.ansi_escape.split(text)
        matches = self.ansi_escape.findall(text)
        
        for i, part in enumerate(parts):
            if part:
                if self.current_tag:
                    self.text_area.insert("end", part, self.current_tag)
                else:
                    self.text_area.insert("end", part)
            
            if i < len(matches):
                code_match = re.search(r'\[(\d+)(?:;\d+)*m', matches[i])
                if code_match:
                    code = code_match.group(1)
                    if code == '0':
                        self.current_tag = None
                    elif code in self.color_map:
                        self.current_tag = f"color_{code}"
        
        self.text_area.see("end")
        self.text_area.configure(state="disabled")

class ZenoSSHWin(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Zeno-SSH Windows Edition")
        self.geometry("1100x700")
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="Zeno-SSH", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.pack(pady=20)
        
        self.host_list_frame = ctk.CTkScrollableFrame(self.sidebar, label_text="Hosts")
        self.host_list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.refresh_btn = ctk.CTkButton(self.sidebar, text="Refresh", command=self.load_hosts)
        self.refresh_btn.pack(pady=10)
        
        # Main Area
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)
        
        # Tabs
        self.tabview = ctk.CTkTabview(self.main_frame)
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.tabview.add("Config")
        
        # Broadcast Bar (At the bottom now)
        self.broadcast_frame = ctk.CTkFrame(self.main_frame)
        self.broadcast_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        
        self.broadcast_entry = ctk.CTkEntry(self.broadcast_frame, placeholder_text="Broadcast command to all active tabs...")
        self.broadcast_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.broadcast_entry.bind("<Return>", self.broadcast_command)
        
        self.broadcast_btn = ctk.CTkButton(self.broadcast_frame, text="Broadcast", width=100, command=self.broadcast_command)
        self.broadcast_btn.pack(side="left", padx=5)
        
        # Config Editor
        self.config_text = ctk.CTkTextbox(self.tabview.tab("Config"), font=("Courier New", 12))
        self.config_text.pack(fill="both", expand=True)
        self.save_btn = ctk.CTkButton(self.tabview.tab("Config"), text="Save & Reload", command=self.save_hosts)
        self.save_btn.pack(pady=10)
        
        # Get the directory where the script or executable is located
        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
            
        self.hosts_path = os.path.join(self.base_dir, "hosts.txt")
        
        self.terminals = {}
        self.ensure_hosts_file()
        self.load_hosts()

    def ensure_hosts_file(self):
        """Creates a default hosts.txt if it doesn't exist."""
        if not os.path.exists(self.hosts_path):
            default_content = "[web-servers]\n# example-01.com\n127.0.0.1\n\n[database]\n# 10.0.0.5\n"
            with open(self.hosts_path, "w") as f:
                f.write(default_content)

    def load_hosts(self):
        # Clear host list frame
        for widget in self.host_list_frame.winfo_children():
            widget.destroy()
            
        if os.path.exists(self.hosts_path):
            with open(self.hosts_path, "r") as f:
                content = f.read()
                self.config_text.delete("1.0", "end")
                self.config_text.insert("1.0", content)
                
                f.seek(0)
                for line in f:
                    line = line.strip()
                    if not line or line.startswith(("#", "[")):
                        continue
                    btn = ctk.CTkButton(self.host_list_frame, text=line, fg_color="transparent", border_width=1, anchor="w", command=lambda h=line: self.add_terminal(h))
                    btn.pack(fill="x", pady=2)

    def save_hosts(self):
        content = self.config_text.get("1.0", "end-1c")
        with open(self.hosts_path, "w") as f:
            f.write(content)
        self.load_hosts()

    def add_terminal(self, host):
        if host in self.terminals:
            self.tabview.set(host)
            return
            
        default_user = os.getlogin() if hasattr(os, 'getlogin') else "user"
        
        self.tabview.add(host)
        term = HostTerminal(self.tabview.tab(host), host, default_user, "")
        term.pack(fill="both", expand=True)
        self.terminals[host] = term
        self.tabview.set(host)
        term.connect(self.update_status)

    def update_status(self, host, status):
        # In a real app we'd change tab color, but ctk tabview is limited
        print(f"Host {host} status: {status}")

    def broadcast_command(self, event=None):
        cmd = self.broadcast_entry.get()
        if not cmd: return
        for term in self.terminals.values():
            term.send_command_manual(cmd)
        self.broadcast_entry.delete(0, 'end')

    # Add helper for manual send
    def send_command_to_term(self, host, cmd):
        if host in self.terminals:
            self.terminals[host].shell.send(cmd + "\n")

# Patch HostTerminal to allow manual send
def send_command_manual(self, cmd):
    if self.shell:
        self.shell.send(cmd + "\n")

HostTerminal.send_command_manual = send_command_manual

if __name__ == "__main__":
    app = ZenoSSHWin()
    app.mainloop()
