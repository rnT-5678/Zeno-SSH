import customtkinter as ctk
import paramiko
from scp import SCPClient
import threading
import os
import sys
import time
import re
import stat
import fnmatch

class HostTerminal(ctk.CTkFrame):
    def __init__(self, master, host, user, password=None, identity=None, base_dir=None):
        super().__init__(master)
        self.host = host; self.user = user; self.password = password; self.identity = identity
        self.base_dir = base_dir or os.getcwd()
        self.port = 22; self.client = None; self.shell = None; self.sftp = None
        
        # State
        self.local_cwd = self.base_dir; self.remote_cwd = "."
        self.selected_local = None; self.selected_remote = None
        
        self.ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]|\x1B\].*?(?:\x07|\x1B\\)|\x1B[@-Z\\-_]')
        self.history = []; self.history_index = -1
        
        # Connection Controls
        self.ctrl_frame = ctk.CTkFrame(self); self.ctrl_frame.pack(fill="x", padx=5, pady=5)
        self.user_var = ctk.StringVar(value=user)
        ctk.CTkEntry(self.ctrl_frame, textvariable=self.user_var, width=120).pack(side="left", padx=5)
        self.pwd_var = ctk.StringVar(value=password if password else "")
        self.pwd_input = ctk.CTkEntry(self.ctrl_frame, textvariable=self.pwd_var, show="*", placeholder_text="Password", width=120)
        self.pwd_input.pack(side="left", padx=5); self.pwd_input.bind("<Return>", lambda e: self.start_connection())
        self.port_var = ctk.StringVar(value="22")
        ctk.CTkEntry(self.ctrl_frame, textvariable=self.port_var, placeholder_text="Port", width=60).pack(side="left", padx=5)
        self.conn_btn = ctk.CTkButton(self.ctrl_frame, text="Connect", command=self.start_connection, width=100)
        self.conn_btn.pack(side="left", padx=5)
        
        # Tabs
        self.tab_container = ctk.CTkTabview(self); self.tab_container.pack(fill="both", expand=True, padx=5, pady=5)
        self.tab_container.add("Terminal"); self.tab_container.add("SFTP Browser"); self.tab_container.add("SCP")
        
        # Terminal Tab
        self.text_area = ctk.CTkTextbox(self.tab_container.tab("Terminal"), font=("Courier New", 12), text_color="#ecf0f1", fg_color="black")
        self.text_area.pack(fill="both", expand=True, padx=5, pady=5); self.text_area.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.entry = ctk.CTkEntry(self.tab_container.tab("Terminal"), placeholder_text="Enter command...")
        self.entry.pack(fill="x", padx=5, pady=5); self.entry.bind("<Return>", self.send_command)
        self.entry.bind("<Up>", self.navigate_history); self.entry.bind("<Down>", self.navigate_history)

        # SFTP Browser Tab
        self.sftp_frame = ctk.CTkFrame(self.tab_container.tab("SFTP Browser")); self.sftp_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Toolbar
        sftp_tool = ctk.CTkFrame(self.sftp_frame, fg_color="transparent"); sftp_tool.pack(fill="x", pady=5)
        ctk.CTkButton(sftp_tool, text="🏠 Home", width=70, command=self.go_home).pack(side="left", padx=2)
        ctk.CTkButton(sftp_tool, text="⟳ Refresh", width=70, command=self.refresh_sftp).pack(side="left", padx=2)
        self.search_entry = ctk.CTkEntry(sftp_tool, placeholder_text="Search (e.g. *.log)...", width=200); self.search_entry.pack(side="left", padx=5)
        ctk.CTkButton(sftp_tool, text="🔍 Search", width=80, command=self.sftp_search).pack(side="left")
        
        # Split Explorer
        self.exp_container = ctk.CTkFrame(self.sftp_frame, fg_color="transparent"); self.exp_container.pack(fill="both", expand=True)
        self.l_side = ctk.CTkFrame(self.exp_container); self.l_side.pack(side="left", fill="both", expand=True, padx=2)
        self.l_path_lbl = ctk.CTkLabel(self.l_side, text=f"Local: {self.local_cwd}", font=ctk.CTkFont(size=10), anchor="w"); self.l_path_lbl.pack(fill="x", padx=5)
        self.l_list = ctk.CTkScrollableFrame(self.l_side, fg_color="#1a1a1a"); self.l_list.pack(fill="both", expand=True)
        
        mid_btns = ctk.CTkFrame(self.exp_container, width=50, fg_color="transparent"); mid_btns.pack(side="left", fill="y", padx=5)
        ctk.CTkButton(mid_btns, text="→", width=40, command=self.do_upload).pack(pady=10)
        ctk.CTkButton(mid_btns, text="←", width=40, command=self.do_download).pack(pady=10)
        
        self.r_side = ctk.CTkFrame(self.exp_container); self.r_side.pack(side="left", fill="both", expand=True, padx=2)
        self.r_path_lbl = ctk.CTkLabel(self.r_side, text=f"Remote: {self.remote_cwd}", font=ctk.CTkFont(size=10), anchor="w"); self.r_path_lbl.pack(fill="x", padx=5)
        self.r_list = ctk.CTkScrollableFrame(self.r_side, fg_color="#1a1a1a"); self.r_list.pack(fill="both", expand=True)
        
        # Dialogue Log
        self.sftp_log = ctk.CTkTextbox(self.sftp_frame, height=100, font=("Courier New", 11), fg_color="#000")
        self.sftp_log.pack(fill="x", pady=(5, 0)); self.sftp_log.configure(state="disabled")
        self.sftp_log._textbox.tag_config("clickable", foreground="#3498db", underline=True)
        self.sftp_log._textbox.bind("<Button-1>", self.on_log_click)
        self.click_map = {}

        # SCP Tab
        self.scp_frame = ctk.CTkFrame(self.tab_container.tab("SCP")); self.scp_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.scp_l = ctk.CTkEntry(self.scp_frame, placeholder_text="Local Path"); self.scp_l.pack(fill="x", pady=5); self.scp_l.insert(0, self.base_dir)
        self.scp_r = ctk.CTkEntry(self.scp_frame, placeholder_text="Remote Path"); self.scp_r.pack(fill="x", pady=5)
        ctk.CTkButton(self.scp_frame, text="SCP Download", command=lambda: self.on_scp_op("download")).pack(side="left", padx=5)
        ctk.CTkButton(self.scp_frame, text="SCP Upload", command=lambda: self.on_scp_op("upload")).pack(side="left", padx=5)
        self.scp_log = ctk.CTkTextbox(self.scp_frame, height=150); self.scp_log.pack(fill="both", expand=True, pady=10)
        self.status_callback = None

    def log_transfer(self, protocol, msg, path_jump=None):
        self.after(0, self._log_callback, protocol, msg, path_jump)

    def _log_callback(self, protocol, msg, path_jump=None):
        log = self.sftp_log if protocol == "SFTP" else self.scp_log
        log.configure(state="normal")
        start_idx = log.index("end-1c")
        full_msg = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
        log.insert("end", full_msg)
        if path_jump:
            end_idx = log.index("end-1c")
            log._textbox.tag_add("clickable", start_idx, end_idx)
            self.click_map[float(start_idx.split('.')[0])] = path_jump
        log.see("end"); log.configure(state="disabled")

    def on_log_click(self, event):
        idx = self.sftp_log._textbox.index(f"@{event.x},{event.y}")
        try:
            line = float(idx.split('.')[0])
            if line in self.click_map:
                self.remote_cwd = self.click_map[line]
                self.refresh_sftp()
        except: pass

    def go_home(self):
        self.remote_cwd = "."
        if self.sftp:
            try: self.remote_cwd = self.sftp.normalize(".")
            except: pass
        self.refresh_sftp()
        self.log_transfer("SFTP", "Navigated to Home (~)")

    def start_connection(self):
        self.user = self.user_var.get(); self.password = self.pwd_var.get()
        self.port = int(self.port_var.get()) if self.port_var.get().isdigit() else 22
        self.conn_btn.configure(state="disabled", text="Connecting...")
        threading.Thread(target=self._ssh_thread, daemon=True).start()

    def connect(self, status_callback):
        self.status_callback = status_callback
        self.update_local_list()

    def _ssh_thread(self):
        try:
            self.log_transfer("SFTP", f"Connecting to {self.host}:{self.port}...")
            self.client = paramiko.SSHClient(); self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(self.host, self.port, self.user, self.password, timeout=15, banner_timeout=30)
            self.sftp = self.client.open_sftp(); self.shell = self.client.invoke_shell(term='xterm-256color')
            self.log_transfer("SFTP", "SUCCESS: Connection established.")
            self.after(0, lambda: self.conn_btn.configure(text="Connected"))
            self.after(0, self.refresh_sftp)
            if self.status_callback: self.after(0, lambda: self.status_callback(self.host, "success"))
            while self.shell:
                if self.shell.recv_ready():
                    data = self.shell.recv(8192).decode('utf-8', errors='ignore')
                    self.after(0, self.append_text, data)
                elif self.shell.exit_status_ready(): break
                else: time.sleep(0.01)
        except Exception as e:
            self.log_transfer("SFTP", f"ERROR: {e}")
            self.after(0, lambda: self.conn_btn.configure(state="normal", text="Connect"))

    def update_local_list(self):
        for w in self.l_list.winfo_children(): w.destroy()
        self.l_path_lbl.configure(text=f"Local: {self.local_cwd}")
        try:
            items = [".."] + sorted(os.listdir(self.local_cwd))
            for item in items:
                path = os.path.join(self.local_cwd, item); is_dir = os.path.isdir(path)
                color = "#3498db" if is_dir else "#ecf0f1"
                btn = ctk.CTkButton(self.l_list, text=f"{'📁' if is_dir else '📄'} {item}", fg_color="transparent", text_color=color, anchor="w", height=20, command=lambda p=path, i=item: self.on_local_click(p, i))
                btn.pack(fill="x")
        except Exception as e: self.log_transfer("SFTP", f"Local Error: {e}")

    def on_local_click(self, path, item):
        if item == "..": self.local_cwd = os.path.dirname(self.local_cwd); self.update_local_list()
        elif os.path.isdir(path): self.local_cwd = path; self.update_local_list()
        else: self.selected_local = path; self.log_transfer("SFTP", f"Selected Local: {item}")

    def refresh_sftp(self):
        if not self.sftp: return
        for w in self.r_list.winfo_children(): w.destroy()
        self.r_path_lbl.configure(text=f"Remote: {self.remote_cwd}")
        try:
            self.sftp.chdir(self.remote_cwd); items = [".."] + sorted(self.sftp.listdir())
            for item in items:
                try:
                    attr = self.sftp.stat(item); is_dir = stat.S_ISDIR(attr.st_mode)
                    color = "#e67e22" if is_dir else "#2ecc71"
                    btn = ctk.CTkButton(self.r_list, text=f"{'📁' if is_dir else '📄'} {item}", fg_color="transparent", text_color=color, anchor="w", height=20, command=lambda i=item: self.on_remote_click(i))
                    btn.pack(fill="x")
                except: pass
        except Exception as e: self.log_transfer("SFTP", f"Remote Error: {e}")

    def on_remote_click(self, item):
        if item == "..":
            self.remote_cwd = os.path.dirname(self.remote_cwd).replace("\\", "/")
            if not self.remote_cwd or self.remote_cwd == ".": self.remote_cwd = "/"
            self.refresh_sftp()
        else:
            try:
                attr = self.sftp.stat(item)
                if stat.S_ISDIR(attr.st_mode): self.remote_cwd = (self.remote_cwd.rstrip("/") + "/" + item).replace("//", "/"); self.refresh_sftp()
                else: self.selected_remote = item; self.log_transfer("SFTP", f"Selected Remote: {item}")
            except: pass

    def do_upload(self):
        if not self.selected_local or not self.sftp: return
        dest = (self.remote_cwd.rstrip("/") + "/" + os.path.basename(self.selected_local)).replace("//", "/")
        threading.Thread(target=self._transfer_thread, args=("SFTP", "upload", self.selected_local, dest), daemon=True).start()

    def do_download(self):
        if not self.selected_remote or not self.sftp: return
        src = (self.remote_cwd.rstrip("/") + "/" + self.selected_remote).replace("//", "/")
        dest = os.path.join(self.local_cwd, self.selected_remote)
        threading.Thread(target=self._transfer_thread, args=("SFTP", "download", dest, src), daemon=True).start()

    def on_scp_op(self, op):
        l = self.scp_l.get(); r = self.scp_r.get()
        threading.Thread(target=self._transfer_thread, args=("SCP", op, l, r), daemon=True).start()

    def _transfer_thread(self, protocol, op, local, remote):
        try:
            self.log_transfer(protocol, f"TASK: {op} starting...")
            if protocol == "SFTP":
                if op == "upload": self.sftp.put(local, remote)
                else: self.sftp.get(remote, local)
            else:
                with SCPClient(self.client.get_transport()) as scp:
                    if op == "upload": scp.put(local, remote)
                    else: scp.get(remote, local)
            self.log_transfer(protocol, "SUCCESS: Transfer complete."); self.after(0, self.update_local_list); self.after(0, self.refresh_sftp)
        except Exception as e: self.log_transfer(protocol, f"ERROR: {e}")

    def sftp_search(self):
        pattern = self.search_entry.get().strip()
        if not pattern or not self.sftp: return
        threading.Thread(target=self._search_thread, args=(pattern,), daemon=True).start()

    def _search_thread(self, pattern):
        self.log_transfer("SFTP", f"SEARCH: Scanning for '{pattern}'...")
        self.found_first = False
        def find(path):
            try:
                for entry in self.sftp.listdir_attr(path):
                    full = (path.rstrip("/") + "/" + entry.filename).replace("//", "/")
                    if fnmatch.fnmatch(entry.filename.lower(), pattern.lower()) or pattern.lower() in entry.filename.lower():
                        self.log_transfer("SFTP", f"MATCH: {full}", path_jump=path)
                        if not self.found_first: self.found_first = True; self.remote_cwd = path; self.after(0, self.refresh_sftp)
                    if stat.S_ISDIR(entry.st_mode): find(full)
            except: pass
        find(self.remote_cwd); self.log_transfer("SFTP", "SEARCH: Finished.")

    def send_command(self, event=None):
        cmd = self.entry.get(); self.entry.delete(0, 'end')
        if self.shell:
            self.shell.send(cmd + "\n")
            if cmd: self.history.append(cmd); self.history_index = len(self.history)

    def navigate_history(self, event):
        if not self.history: return
        if event.keysym == "Up": self.history_index = max(0, self.history_index - 1)
        else: self.history_index = min(len(self.history), self.history_index + 1)
        self.entry.delete(0, 'end')
        if 0 <= self.history_index < len(self.history): self.entry.insert(0, self.history[self.history_index])

    def append_text(self, text):
        if not text: return
        clean = "".join(ch for ch in self.ansi_escape.sub('', text) if ch == '\n' or ch == '\t' or ord(ch) >= 32)
        if not clean: return
        self.text_area.configure(state="normal"); self.text_area.insert("end", clean); self.text_area.see("end"); self.text_area.configure(state="disabled")

class ZenoSSHWin(ctk.CTk):
    def __init__(self):
        super().__init__(); self.title("Zeno-SSH Explorer"); self.geometry("1200x800")
        if getattr(sys, 'frozen', False): self.base_dir = os.path.dirname(sys.executable)
        else: self.base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(self.base_dir, "final_zeno.ico")
        if os.path.exists(icon_path):
            try: self.iconbitmap(icon_path)
            except: pass
        self.grid_columnconfigure(1, weight=1); self.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(self, width=200); self.sidebar.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(self.sidebar, text="Zeno-SSH", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=20)
        self.host_list_frame = ctk.CTkScrollableFrame(self.sidebar, label_text="Systems"); self.host_list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkButton(self.sidebar, text="Refresh", command=self.load_hosts).pack(pady=10)
        self.main_frame = ctk.CTkFrame(self); self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1); self.main_frame.grid_rowconfigure(0, weight=1)
        self.tabview = ctk.CTkTabview(self.main_frame); self.tabview.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.tabview.add("Config")
        self.broadcast_entry = ctk.CTkEntry(self.main_frame, placeholder_text="Broadcast to all active terminal sessions..."); self.broadcast_entry.grid(row=1, column=0, sticky="ew", padx=10, pady=5); self.broadcast_entry.bind("<Return>", self.broadcast_command)
        self.config_text = ctk.CTkTextbox(self.tabview.tab("Config")); self.config_text.pack(fill="both", expand=True)
        ctk.CTkButton(self.tabview.tab("Config"), text="Save & Reload", command=self.save_hosts).pack(pady=5)
        self.hosts_path = os.path.join(self.base_dir, "hosts.txt"); self.terminals = {}; self.host_configs = {}
        self.ensure_hosts_file(); self.load_hosts()

    def ensure_hosts_file(self):
        if not os.path.exists(self.hosts_path):
            with open(self.hosts_path, "w") as f: f.write("[servers]\n127.0.0.1\n\n[sftp]\nAlias | 1.2.3.4 | 22 | user\n")

    def load_hosts(self):
        for w in self.host_list_frame.winfo_children(): w.destroy()
        self.host_configs = {}
        if os.path.exists(self.hosts_path):
            with open(self.hosts_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    if line.startswith("["): ctk.CTkLabel(self.host_list_frame, text=line.upper(), font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(10, 2)); continue
                    display = line; host_id = line
                    if "|" in line:
                        p = [x.strip() for x in line.split("|")]
                        if len(p) >= 2:
                            alias = p[0]; self.host_configs[alias] = {"host":p[1], "port":p[2] if len(p)>2 else "22", "user":p[3] if len(p)>3 else ""}
                            display = f"SFTP: {alias}"; host_id = alias
                    ctk.CTkButton(self.host_list_frame, text=display, fg_color="transparent", border_width=1, anchor="w", command=lambda h=host_id: self.add_terminal(h)).pack(fill="x", pady=1, padx=10)

    def save_hosts(self):
        with open(self.hosts_path, "w") as f: f.write(self.config_text.get("1.0", "end-1c"))
        self.load_hosts()

    def add_terminal(self, host):
        if host in self.terminals: self.tabview.set(host); return
        cfg = self.host_configs.get(host)
        self.tabview.add(host)
        term = HostTerminal(self.tabview.tab(host), cfg["host"] if cfg else host, cfg["user"] if cfg else os.getlogin(), base_dir=self.base_dir)
        if cfg: term.port_var.set(cfg["port"])
        term.pack(fill="both", expand=True); self.terminals[host] = term; self.tabview.set(host); term.connect(None); term.pwd_input.focus_set()

    def broadcast_command(self, e=None):
        cmd = self.broadcast_entry.get(); self.broadcast_entry.delete(0, 'end')
        for t in self.terminals.values():
            if t.shell: t.shell.send(cmd + "\n")

if __name__ == "__main__":
    app = ZenoSSHWin(); app.mainloop()
