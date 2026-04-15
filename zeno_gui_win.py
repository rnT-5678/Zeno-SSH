import customtkinter as ctk
import paramiko
from scp import SCPClient
import threading
import os
import sys
import time
import re

class HostTerminal(ctk.CTkFrame):
    def __init__(self, master, host, user, password=None, identity=None, base_dir=None):
        super().__init__(master)
        self.host = host
        self.user = user
        self.password = password
        self.identity = identity
        self.base_dir = base_dir or os.getcwd()
        self.port = 22
        self.client = None
        self.shell = None
        
        # Precise Regex for ANSI sequences:
        self.ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]|\x1B\].*?(?:\x07|\x1B\\)|\x1B[@-Z\\-_]')
        
        # History
        self.history = []
        self.history_index = -1
        
        # Connection Controls
        self.ctrl_frame = ctk.CTkFrame(self)
        self.ctrl_frame.pack(fill="x", padx=5, pady=5)
        
        self.user_var = ctk.StringVar(value=user)
        self.user_input = ctk.CTkEntry(self.ctrl_frame, textvariable=self.user_var, width=120)
        self.user_input.pack(side="left", padx=5)
        
        self.pwd_var = ctk.StringVar(value=password if password else "")
        self.pwd_input = ctk.CTkEntry(self.ctrl_frame, textvariable=self.pwd_var, show="*", placeholder_text="Password", width=120)
        self.pwd_input.pack(side="left", padx=5)
        self.pwd_input.bind("<Return>", lambda e: self.start_connection())
        
        self.port_var = ctk.StringVar(value="22")
        self.port_input = ctk.CTkEntry(self.ctrl_frame, textvariable=self.port_var, placeholder_text="Port", width=60)
        self.port_input.pack(side="left", padx=5)
        
        self.conn_btn = ctk.CTkButton(self.ctrl_frame, text="Connect", command=self.start_connection, width=100)
        self.conn_btn.pack(side="left", padx=5)
        
        # Tabs
        self.tab_container = ctk.CTkTabview(self)
        self.tab_container.pack(fill="both", expand=True, padx=5, pady=5)
        self.tab_container.add("Terminal")
        self.tab_container.add("SFTP")
        self.tab_container.add("SCP")
        
        # Terminal Tab
        self.text_area = ctk.CTkTextbox(self.tab_container.tab("Terminal"), font=("Courier New", 12), text_color="#ecf0f1", fg_color="black")
        self.text_area.pack(fill="both", expand=True, padx=5, pady=5)
        self.text_area.bind("<Button-1>", lambda e: self.entry.focus_set())
        
        self.entry = ctk.CTkEntry(self.tab_container.tab("Terminal"), placeholder_text="Enter command...")
        self.entry.pack(fill="x", padx=5, pady=5)
        self.entry.bind("<Return>", self.send_command)
        self.entry.bind("<Up>", self.navigate_history)
        self.entry.bind("<Down>", self.navigate_history)

        # SFTP Tab
        self.sftp_frame = ctk.CTkFrame(self.tab_container.tab("SFTP"))
        self.sftp_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(self.sftp_frame, text="Local Path:").pack(anchor="w")
        local_path_box_sftp = ctk.CTkFrame(self.sftp_frame, fg_color="transparent")
        local_path_box_sftp.pack(fill="x", pady=(0, 10))
        self.local_path_sftp = ctk.CTkEntry(local_path_box_sftp, placeholder_text="C:/local/file")
        self.local_path_sftp.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.local_path_sftp.insert(0, self.base_dir)
        ctk.CTkButton(local_path_box_sftp, text="File...", width=60, command=lambda: self.browse_file(self.local_path_sftp)).pack(side="left", padx=2)
        ctk.CTkButton(local_path_box_sftp, text="Folder...", width=60, command=lambda: self.browse_folder(self.local_path_sftp)).pack(side="left", padx=2)
        
        ctk.CTkLabel(self.sftp_frame, text="Remote Path:").pack(anchor="w")
        self.remote_path_sftp = ctk.CTkEntry(self.sftp_frame, placeholder_text="/remote/path")
        self.remote_path_sftp.pack(fill="x", pady=(0, 10))
        
        btn_box_sftp = ctk.CTkFrame(self.sftp_frame, fg_color="transparent")
        btn_box_sftp.pack(fill="x")
        ctk.CTkButton(btn_box_sftp, text="SFTP Upload", command=lambda: self.transfer_op("SFTP", "upload"), width=120).pack(side="left", padx=5)
        ctk.CTkButton(btn_box_sftp, text="SFTP Download", command=lambda: self.transfer_op("SFTP", "download"), width=120).pack(side="left", padx=5)
        
        self.sftp_log = ctk.CTkTextbox(self.sftp_frame, height=150, font=("Courier New", 11))
        self.sftp_log.pack(fill="both", expand=True, pady=10)
        self.sftp_log.configure(state="disabled")

        # SCP Tab
        self.scp_frame = ctk.CTkFrame(self.tab_container.tab("SCP"))
        self.scp_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(self.scp_frame, text="Local Path:").pack(anchor="w")
        local_path_box_scp = ctk.CTkFrame(self.scp_frame, fg_color="transparent")
        local_path_box_scp.pack(fill="x", pady=(0, 10))
        self.local_path_scp = ctk.CTkEntry(local_path_box_scp, placeholder_text="C:/local/file")
        self.local_path_scp.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.local_path_scp.insert(0, self.base_dir)
        ctk.CTkButton(local_path_box_scp, text="File...", width=60, command=lambda: self.browse_file(self.local_path_scp)).pack(side="left", padx=2)
        ctk.CTkButton(local_path_box_scp, text="Folder...", width=60, command=lambda: self.browse_folder(self.local_path_scp)).pack(side="left", padx=2)
        
        ctk.CTkLabel(self.scp_frame, text="Remote Path:").pack(anchor="w")
        self.remote_path_scp = ctk.CTkEntry(self.scp_frame, placeholder_text="/remote/path")
        self.remote_path_scp.pack(fill="x", pady=(0, 10))
        
        btn_box_scp = ctk.CTkFrame(self.scp_frame, fg_color="transparent")
        btn_box_scp.pack(fill="x")
        ctk.CTkButton(btn_box_scp, text="SCP Upload", command=lambda: self.transfer_op("SCP", "upload"), width=120).pack(side="left", padx=5)
        ctk.CTkButton(btn_box_scp, text="SCP Download", command=lambda: self.transfer_op("SCP", "download"), width=120).pack(side="left", padx=5)
        
        self.scp_log = ctk.CTkTextbox(self.scp_frame, height=150, font=("Courier New", 11))
        self.scp_log.pack(fill="both", expand=True, pady=10)
        self.scp_log.configure(state="disabled")

        self.status_callback = None

    def start_connection(self):
        self.user = self.user_var.get()
        self.password = self.pwd_var.get()
        self.port = int(self.port_var.get()) if self.port_var.get().isdigit() else 22
        self.conn_btn.configure(state="disabled", text="Connecting...")
        threading.Thread(target=self._ssh_thread, daemon=True).start()
        
    def connect(self, status_callback):
        self.status_callback = status_callback
        self.append_text(f"[*] Ready to connect to {self.host}. Click 'Connect' to begin.\n")
        
    def _ssh_thread(self):
        try:
            self.append_text(f"[*] Connecting to {self.host}:{self.port} as {self.user}...\n")
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                key_filename=self.identity,
                timeout=15,
                allow_agent=True,
                look_for_keys=True
            )
            
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

    def log_transfer(self, protocol, msg):
        log_widget = self.sftp_log if protocol == "SFTP" else self.scp_log
        log_widget.configure(state="normal")
        log_widget.insert("end", f"{msg}\n")
        log_widget.see("end")
        log_widget.configure(state="disabled")

    def transfer_op(self, protocol, op_type):
        if not self.client:
            self.log_transfer(protocol, "[-] Error: Connect via SSH first.")
            return
            
        local = self.local_path_sftp.get().strip() if protocol == "SFTP" else self.local_path_scp.get().strip()
        remote = self.remote_path_sftp.get().strip() if protocol == "SFTP" else self.remote_path_scp.get().strip()
        
        if not local or not remote:
            self.log_transfer(protocol, "[-] Error: Provide both local and remote paths.")
            return
            
        threading.Thread(target=self._transfer_thread, args=(protocol, op_type, local, remote), daemon=True).start()

    def _transfer_thread(self, protocol, op_type, local, remote):
        try:
            # If downloading to a directory, append the remote filename
            if op_type == "download" and os.path.isdir(local):
                filename = os.path.basename(remote)
                local = os.path.join(local, filename)
                self.log_transfer(protocol, f"[*] Destination is a directory. Saving as: {local}")

            self.log_transfer(protocol, f"[*] Starting {op_type} via {protocol}...")
            
            if protocol == "SFTP":
                sftp = self.client.open_sftp()
                if op_type == "upload":
                    sftp.put(local, remote)
                else:
                    sftp.get(remote, local)
                sftp.close()
            else:
                with SCPClient(self.client.get_transport()) as scp:
                    if op_type == "upload":
                        scp.put(local, recursive=True, remote_path=remote)
                    else:
                        scp.get(remote, local_path=local, recursive=True)
                
            self.log_transfer(protocol, f"[+] {op_type.capitalize()} complete!")
        except Exception as e:
            self.log_transfer(protocol, f"[-] {protocol} Error: {e}")

    def browse_file(self, entry_widget):
        filename = ctk.filedialog.askopenfilename()
        if filename:
            entry_widget.delete(0, 'end')
            entry_widget.insert(0, filename)

    def browse_folder(self, entry_widget):
        folder = ctk.filedialog.askdirectory()
        if folder:
            entry_widget.delete(0, 'end')
            entry_widget.insert(0, folder)

    def send_command(self, event=None):
        cmd = self.entry.get()
        if self.shell:
            self.shell.send(cmd + "\n")
            if cmd:
                self.history.append(cmd)
                self.history_index = len(self.history)
            self.entry.delete(0, 'end')
        else:
            self.append_text("[-] Not connected.\n")

    def navigate_history(self, event):
        if not self.history: return
        if event.keysym == "Up":
            self.history_index = max(0, self.history_index - 1)
        elif event.keysym == "Down":
            self.history_index = min(len(self.history), self.history_index + 1)
        self.entry.delete(0, 'end')
        if 0 <= self.history_index < len(self.history):
            self.entry.insert(0, self.history[self.history_index])

    def append_text(self, text):
        if not text: return
        clean_text = self.ansi_escape.sub('', text)
        clean_text = "".join(ch for ch in clean_text if ch == '\n' or ch == '\t' or ord(ch) >= 32)
        if not clean_text: return
        self.text_area.configure(state="normal")
        self.text_area.insert("end", clean_text)
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
        
        # Broadcast Bar
        self.broadcast_frame = ctk.CTkFrame(self.main_frame)
        self.broadcast_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        self.b_history = []
        self.b_history_index = -1
        self.broadcast_entry = ctk.CTkEntry(self.broadcast_frame, placeholder_text="Broadcast command to all active tabs...")
        self.broadcast_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.broadcast_entry.bind("<Return>", self.broadcast_command)
        self.broadcast_entry.bind("<Up>", self.navigate_broadcast_history)
        self.broadcast_entry.bind("<Down>", self.navigate_broadcast_history)
        ctk.CTkButton(self.broadcast_frame, text="Broadcast", width=100, command=self.broadcast_command).pack(side="left", padx=5)
        
        # Config Editor
        self.config_text = ctk.CTkTextbox(self.tabview.tab("Config"), font=("Courier New", 12))
        self.config_text.pack(fill="both", expand=True)
        ctk.CTkButton(self.tabview.tab("Config"), text="Save & Reload", command=self.save_hosts).pack(pady=10)
        
        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.hosts_path = os.path.join(self.base_dir, "hosts.txt")
        self.terminals = {}
        self.ensure_hosts_file()
        self.load_hosts()

    def ensure_hosts_file(self):
        if not os.path.exists(self.hosts_path):
            default_content = "[web-servers]\n# example-01.com\n127.0.0.1\n\n[database]\n# 10.0.0.5\n"
            with open(self.hosts_path, "w") as f:
                f.write(default_content)

    def load_hosts(self):
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
                    ctk.CTkButton(self.host_list_frame, text=line, fg_color="transparent", border_width=1, anchor="w", command=lambda h=line: self.add_terminal(h)).pack(fill="x", pady=2)

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
        term = HostTerminal(self.tabview.tab(host), host, default_user, "", base_dir=self.base_dir)
        term.pack(fill="both", expand=True)
        self.terminals[host] = term
        self.tabview.set(host)
        term.connect(self.update_status)

    def update_status(self, host, status):
        print(f"Host {host} status: {status}")

    def broadcast_command(self, event=None):
        cmd = self.broadcast_entry.get()
        if cmd:
            self.b_history.append(cmd)
            self.b_history_index = len(self.b_history)
        for term in self.terminals.values():
            term.send_command_manual(cmd)
        self.broadcast_entry.delete(0, 'end')

    def navigate_broadcast_history(self, event):
        if not self.b_history: return
        if event.keysym == "Up":
            self.b_history_index = max(0, self.b_history_index - 1)
        elif event.keysym == "Down":
            self.b_history_index = min(len(self.b_history), self.b_history_index + 1)
        self.broadcast_entry.delete(0, 'end')
        if 0 <= self.b_history_index < len(self.b_history):
            self.broadcast_entry.insert(0, self.b_history[self.b_history_index])

    def send_command_to_term(self, host, cmd):
        if host in self.terminals:
            self.terminals[host].shell.send(cmd + "\n")

def send_command_manual(self, cmd):
    if self.shell:
        self.shell.send(cmd + "\n")

HostTerminal.send_command_manual = send_command_manual

if __name__ == "__main__":
    app = ZenoSSHWin()
    app.mainloop()
