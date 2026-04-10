import customtkinter as ctk
import paramiko
import threading
import os
import sys

class HostTerminal(ctk.CTkFrame):
    def __init__(self, master, host, user, password=None, identity=None):
        super().__init__(master)
        self.host = host
        self.user = user
        self.password = password
        self.identity = identity
        self.client = None
        self.shell = None
        
        self.text_area = ctk.CTkTextbox(self, font=("Courier New", 12), text_color="#2ecc71", fg_color="black")
        self.text_area.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.entry = ctk.CTkEntry(self, placeholder_text="Enter command...")
        self.entry.pack(fill="x", padx=5, pady=5)
        self.entry.bind("<Return>", self.send_command)
        
        self.status_callback = None
        
    def connect(self, status_callback):
        self.status_callback = status_callback
        threading.Thread(target=self._ssh_thread, daemon=True).start()
        
    def _ssh_thread(self):
        try:
            self.append_text(f"[*] Connecting to {self.host}...\n")
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            self.client.connect(
                hostname=self.host,
                username=self.user,
                password=self.password,
                key_filename=self.identity,
                timeout=10
            )
            
            self.shell = self.client.invoke_shell()
            self.append_text(f"[+] Connected!\n")
            if self.status_callback:
                self.status_callback(self.host, "success")
                
            # Read thread
            while self.shell:
                if self.shell.recv_ready():
                    data = self.shell.recv(1024).decode('utf-8', errors='ignore')
                    self.append_text(data)
                if self.shell.exit_status_ready():
                    break
                    
        except Exception as e:
            self.append_text(f"[-] Connection failed: {e}\n")
            if self.status_callback:
                self.status_callback(self.host, "error")

    def send_command(self, event=None):
        cmd = self.entry.get()
        if self.shell:
            self.shell.send(cmd + "\n")
            self.entry.delete(0, 'end')
        else:
            self.append_text("[-] Not connected.\n")

    def append_text(self, text):
        self.text_area.configure(state="normal")
        self.text_area.insert("end", text)
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
        self.main_frame.grid_rowconfigure(1, weight=1)
        
        # Broadcast Bar
        self.broadcast_frame = ctk.CTkFrame(self.main_frame)
        self.broadcast_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        self.user_entry = ctk.CTkEntry(self.broadcast_frame, placeholder_text="User", width=100)
        self.user_entry.pack(side="left", padx=5)
        self.user_entry.insert(0, os.getlogin() if hasattr(os, 'getlogin') else "user")
        
        self.pwd_entry = ctk.CTkEntry(self.broadcast_frame, placeholder_text="Password", show="*", width=100)
        self.pwd_entry.pack(side="left", padx=5)
        
        self.broadcast_entry = ctk.CTkEntry(self.broadcast_frame, placeholder_text="Broadcast command...")
        self.broadcast_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.broadcast_entry.bind("<Return>", self.broadcast_command)
        
        self.broadcast_btn = ctk.CTkButton(self.broadcast_frame, text="Broadcast", width=100, command=self.broadcast_command)
        self.broadcast_btn.pack(side="left", padx=5)
        
        # Tabs
        self.tabview = ctk.CTkTabview(self.main_frame)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.tabview.add("Config")
        
        # Config Editor
        self.config_text = ctk.CTkTextbox(self.tabview.tab("Config"), font=("Courier New", 12))
        self.config_text.pack(fill="both", expand=True)
        self.save_btn = ctk.CTkButton(self.tabview.tab("Config"), text="Save & Reload", command=self.save_hosts)
        self.save_btn.pack(pady=10)
        
        self.terminals = {}
        self.load_hosts()

    def load_hosts(self):
        # Clear host list frame
        for widget in self.host_list_frame.winfo_children():
            widget.destroy()
            
        if os.path.exists("hosts.txt"):
            with open("hosts.txt", "r") as f:
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
        with open("hosts.txt", "w") as f:
            f.write(content)
        self.load_hosts()

    def add_terminal(self, host):
        if host in self.terminals:
            self.tabview.set(host)
            return
            
        user = self.user_entry.get()
        pwd = self.pwd_entry.get()
        
        self.tabview.add(host)
        term = HostTerminal(self.tabview.tab(host), host, user, pwd)
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
