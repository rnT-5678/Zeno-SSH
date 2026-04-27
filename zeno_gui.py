#!/usr/bin/python3
import gi
import os
import threading
import paramiko
from scp import SCPClient
import stat
import time
import fnmatch
import re

gi.require_version('Gtk', '3.0')
gi.require_version('Vte', '2.91')
gi.require_version('Pango', '1.0')
from gi.repository import Gtk, Vte, GLib, Gdk, Pango

class HostTerminal(Gtk.Box):
    def __init__(self, host, parent_gui, config=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.host = host; self.parent_gui = parent_gui; self.started = False
        self.local_cwd = os.getcwd(); self.remote_cwd = "."
        self.selected_local = None; self.selected_remote = None
        self.found_first_match = False
        
        if config:
            self.real_host = config["host"]; self.default_user = config["user"]
            self.default_port = config["port"]; self.default_pass = "" 
        else:
            self.real_host = host; self.default_user = os.getlogin(); self.default_pass = ""; self.default_port = "22"

        self.history = []; self.history_index = -1
        self.client = None; self.shell = None; self.sftp = None
        
        # Connection Controls
        ctrl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5); ctrl_box.set_margin_all(5)
        self.pack_start(ctrl_box, False, False, 0)
        self.user_entry = Gtk.Entry(); self.user_entry.set_text(self.default_user); ctrl_box.pack_start(self.user_entry, False, False, 0)
        self.pwd_entry = Gtk.Entry(); self.pwd_entry.set_visibility(False); self.pwd_entry.set_placeholder_text("Password")
        self.pwd_entry.connect("activate", lambda x: self.start_shell()); ctrl_box.pack_start(self.pwd_entry, False, False, 0)
        self.port_entry = Gtk.Entry(); self.port_entry.set_width_chars(5); self.port_entry.set_text(self.default_port); ctrl_box.pack_start(self.port_entry, False, False, 0)
        self.conn_btn = Gtk.Button(label="Connect"); self.conn_btn.connect("clicked", lambda x: self.start_shell()); ctrl_box.pack_start(self.conn_btn, False, False, 0)

        # Tabs
        self.inner_notebook = Gtk.Notebook(); self.pack_start(self.inner_notebook, True, True, 0)

        # Terminal Tab
        term_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        scrolled = Gtk.ScrolledWindow(); self.terminal = Vte.Terminal()
        self.terminal.set_font(Pango.FontDescription.from_string("monospace 10"))
        self.terminal.set_color_foreground(Gdk.RGBA(0, 1, 0, 1)); self.terminal.set_color_background(Gdk.RGBA(0, 0, 0, 1))
        scrolled.add(self.terminal); term_box.pack_start(scrolled, True, True, 0)
        self.entry = Gtk.Entry(placeholder_text="Enter command..."); self.entry.connect("activate", self.on_entry_activate)
        self.entry.connect("key-press-event", self.on_key_press); term_box.pack_start(self.entry, False, False, 0)
        self.inner_notebook.append_page(term_box, Gtk.Label(label="Terminal"))

        # SFTP Browser Tab
        sftp_main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); sftp_main.set_margin_all(5)
        sftp_tool = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        h_btn = Gtk.Button(label="🏠 Home"); h_btn.connect("clicked", lambda x: self.go_home()); sftp_tool.pack_start(h_btn, False, False, 0)
        root_btn = Gtk.Button(label="根 Root"); root_btn.connect("clicked", lambda x: self.go_root()); sftp_tool.pack_start(root_btn, False, False, 0)
        ref_btn = Gtk.Button(label="⟳ Refresh"); ref_btn.connect("clicked", lambda x: self.refresh_sftp()); sftp_tool.pack_start(ref_btn, False, False, 0)
        self.search_entry = Gtk.Entry(placeholder_text="Search (e.g. *.txt)..."); sftp_tool.pack_start(self.search_entry, True, True, 0)
        src_btn = Gtk.Button(label="🔍 Search"); src_btn.connect("clicked", lambda x: self.on_search_clicked()); sftp_tool.pack_start(src_btn, False, False, 0)
        sftp_main.pack_start(sftp_tool, False, False, 0)

        paned = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        sftp_main.pack_start(paned, True, True, 0)

        # Local
        l_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.l_path_lbl = Gtk.Label(xalign=0); l_box.pack_start(self.l_path_lbl, False, False, 0)
        self.l_scroll = Gtk.ScrolledWindow(); self.l_list = Gtk.ListBox(); self.l_scroll.add(self.l_list); l_box.pack_start(self.l_scroll, True, True, 0)
        paned.pack_start(l_box, True, True, 0)

        # Transfer Buttons (Middle)
        mid_btns = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10); mid_btns.set_center_widget(Gtk.Label())
        u_btn = Gtk.Button(label="→"); u_btn.connect("clicked", lambda x: self.do_upload()); mid_btns.pack_start(u_btn, False, False, 0)
        d_btn = Gtk.Button(label="←"); d_btn.connect("clicked", lambda x: self.do_download()); mid_btns.pack_start(d_btn, False, False, 0)
        paned.pack_start(mid_btns, False, False, 5)

        # Remote
        r_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.r_path_lbl = Gtk.Label(xalign=0); r_box.pack_start(self.r_path_lbl, False, False, 0)
        self.r_scroll = Gtk.ScrolledWindow(); self.r_list = Gtk.ListBox(); self.r_scroll.add(self.r_list); r_box.pack_start(self.r_scroll, True, True, 0)
        paned.pack_start(r_box, True, True, 0)
        
        # Dialogue Log
        log_scroll = Gtk.ScrolledWindow(); self.sftp_log_view = Gtk.TextView(editable=False); self.sftp_log_view.set_size_request(-1, 100); log_scroll.add(self.sftp_log_view); sftp_main.pack_start(log_scroll, False, False, 0)
        self.log_tag_table = self.sftp_log_view.get_buffer().get_tag_table()
        
        self.inner_notebook.append_page(sftp_main, Gtk.Label(label="SFTP Browser"))
        self.update_local_list()

    def go_home(self):
        self.remote_cwd = "."
        if self.sftp:
            try: self.remote_cwd = self.sftp.normalize(".")
            except: self.remote_cwd = "/"
        self.log_transfer("SFTP", f"Navigating to Home: {self.remote_cwd}")
        for child in self.r_list.get_children(): self.r_list.remove(child)
        self.r_list.add(Gtk.Label(label="Loading...", xalign=0.5)); self.r_list.show_all()
        GLib.timeout_add(100, self.refresh_sftp)

    def go_root(self):
        self.remote_cwd = "/"
        self.log_transfer("SFTP", "Navigating to Root (/)")
        for child in self.r_list.get_children(): self.r_list.remove(child)
        self.r_list.add(Gtk.Label(label="Loading...", xalign=0.5)); self.r_list.show_all()
        GLib.timeout_add(100, self.refresh_sftp)

    def log_transfer(self, protocol, msg, path_jump=None):
        GLib.idle_add(self._log_idle, msg, path_jump)

    def _log_idle(self, msg, path_jump):
        buf = self.sftp_log_view.get_buffer()
        iter = buf.get_end_iter()
        full_msg = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
        if path_jump:
            tag = Gtk.TextTag(); tag.set_property("foreground", "#3498db"); tag.set_property("underline", Pango.Underline.SINGLE)
            tag.connect("event", self.on_tag_event, path_jump)
            self.log_tag_table.add(tag)
            buf.insert_with_tags(iter, full_msg, tag)
        else: buf.insert(iter, full_msg)
        return False

    def on_tag_event(self, tag, widget, event, iter, path):
        if event.type == Gdk.EventType.BUTTON_PRESS:
            self.remote_cwd = path; self.refresh_sftp(); return True
        return False

    def update_local_list(self):
        for child in self.l_list.get_children(): self.l_list.remove(child)
        self.l_path_lbl.set_text(f"Local: {self.local_cwd}")
        adj = self.l_scroll.get_vadjustment(); adj.set_value(adj.get_lower())
        try:
            items = [".."] + sorted(os.listdir(self.local_cwd))
            for item in items:
                path = os.path.join(self.local_cwd, item); is_dir = os.path.isdir(path)
                lbl = Gtk.Label(label=f"{'📁' if is_dir else '📄'} {item}", xalign=0)
                row = Gtk.ListBoxRow(); row.add(lbl); row.show_all(); self.l_list.add(row)
            self.l_list.connect("row-activated", self.on_local_row_activated)
        except Exception as e: self.log_transfer("SFTP", f"Local Error: {e}")

    def on_local_row_activated(self, listbox, row):
        item = row.get_child().get_text()[3:]
        path = os.path.join(self.local_cwd, item)
        if item == "..": self.local_cwd = os.path.dirname(self.local_cwd); self.update_local_list()
        elif os.path.isdir(path): self.local_cwd = path; self.update_local_list()
        else: self.selected_local = path; self.log_transfer("SFTP", f"Selected Local: {item}")

    def refresh_sftp(self, highlight=None):
        if not self.sftp: return
        for child in self.r_list.get_children(): self.r_list.remove(child)
        self.r_path_lbl.set_text(f"Remote: {self.remote_cwd}")
        adj = self.r_scroll.get_vadjustment(); adj.set_value(adj.get_lower())
        try:
            self.sftp.chdir(self.remote_cwd); items = [".."] + sorted(self.sftp.listdir())
            for item in items:
                try:
                    attr = self.sftp.stat(item); is_dir = stat.S_ISDIR(attr.st_mode)
                    color = "#e67e22" if is_dir else "#2ecc71"
                    if highlight and item == highlight: color = "#f1c40f"
                    lbl = Gtk.Label(xalign=0); lbl.set_markup(f"<span foreground='{color}'>{'📁' if is_dir else '📄'} {item}</span>")
                    row = Gtk.ListBoxRow(); row.add(lbl); row.show_all(); self.r_list.add(row)
                except: pass
            self.r_list.connect("row-activated", self.on_remote_row_activated)
        except Exception as e: self.log_transfer("SFTP", f"Remote Error: {e}")

    def on_remote_row_activated(self, listbox, row):
        text = row.get_child().get_label(); item = re.sub('<[^<]+?>', '', text)[3:]
        for child in self.r_list.get_children(): self.r_list.remove(child)
        self.r_list.add(Gtk.Label(label="Loading...", xalign=0.5)); self.r_list.show_all()
        if item == "..":
            self.remote_cwd = os.path.dirname(self.remote_cwd).replace("\\", "/")
            if not self.remote_cwd or self.remote_cwd == ".": self.remote_cwd = "/"
            GLib.timeout_add(50, self.refresh_sftp)
        else:
            try:
                attr = self.sftp.stat(item)
                if stat.S_ISDIR(attr.st_mode): self.remote_cwd = (self.remote_cwd.rstrip("/") + "/" + item); GLib.timeout_add(50, self.refresh_sftp)
                else: self.selected_remote = item; self.do_download(); GLib.timeout_add(50, self.refresh_sftp)
            except: self.refresh_sftp()

    def on_search_clicked(self):
        pattern = self.search_entry.get_text()
        if not pattern or not self.sftp: return
        threading.Thread(target=self._search_thread, args=(pattern,), daemon=True).start()

    def _search_thread(self, pattern):
        self.log_transfer("SFTP", f"SEARCH: Scanning for '{pattern}'...")
        self.found_first = False
        def find(path, depth=0):
            if depth > 15: return
            try:
                for entry in self.sftp.listdir_attr(path):
                    if entry.filename in [".", ".."]: continue
                    full = (path.rstrip("/") + "/" + entry.filename)
                    if fnmatch.fnmatch(entry.filename.lower(), pattern.lower()) or pattern.lower() in entry.filename.lower():
                        self.log_transfer("SFTP", f"MATCH: {full}", path_jump=path)
                        if not self.found_first: self.found_first = True; self.remote_cwd = path; GLib.idle_add(self.refresh_sftp, entry.filename)
                    if stat.S_ISDIR(entry.st_mode): find(full, depth + 1)
            except: pass
        find(self.remote_cwd); self.log_transfer("SFTP", "Search finished.")

    def do_upload(self):
        if self.selected_local: self._transfer_op("upload", self.selected_local, (self.remote_cwd.rstrip("/") + "/" + os.path.basename(self.selected_local)))

    def do_download(self):
        if self.selected_remote: self._transfer_op("download", os.path.join(self.local_cwd, self.selected_remote), (self.remote_cwd.rstrip("/") + "/" + self.selected_remote))

    def _transfer_op(self, op, local, remote):
        threading.Thread(target=self._transfer_worker, args=(op, local, remote), daemon=True).start()

    def _transfer_worker(self, op, local, remote):
        try:
            self.log_transfer("SFTP", f"TASK: {op} starting...")
            if op == "upload": self.sftp.put(local, remote)
            else: self.sftp.get(remote, local)
            self.log_transfer("SFTP", f"SUCCESS: {op} complete.")
            GLib.idle_add(self.update_local_list); GLib.idle_add(self.refresh_sftp)
        except Exception as e: self.log_transfer("SFTP", f"ERROR: {e}")

    def start_shell(self):
        if self.started: return
        self.started = True; self.conn_btn.set_sensitive(False); self.conn_btn.set_label("Connecting...")
        user = self.user_entry.get_text(); port = self.port_entry.get_text(); pwd = self.pwd_entry.get_text()
        threading.Thread(target=self._ssh_connect_thread, args=(user, port, pwd), daemon=True).start()

    def _ssh_connect_thread(self, user, port, pwd):
        try:
            p_int = int(port) if port.isdigit() else 22
            self.client = paramiko.SSHClient(); self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(hostname=self.real_host, port=p_int, username=user, password=pwd, timeout=15, banner_timeout=30)
            self.sftp = self.client.open_sftp(); self.shell = self.client.invoke_shell(term='xterm-256color')
            # Linux specific initial home
            self.initial_home = self.sftp.normalize(".")
            self.remote_cwd = self.initial_home
            GLib.idle_add(self._on_connected)
            while self.shell:
                if self.shell.recv_ready(): data = self.shell.recv(8192).decode('utf-8', errors='ignore'); GLib.idle_add(self.append_text, data)
                elif self.shell.exit_status_ready(): break
                else: time.sleep(0.01)
        except Exception as e:
            self.log_transfer("SFTP", f"Connection failed: {e}")
            GLib.idle_add(self.conn_btn.set_sensitive, True); GLib.idle_add(self.conn_btn.set_label, "Connect")

    def _on_connected(self):
        self.conn_btn.set_label("Connected"); self.refresh_sftp()

    def append_text(self, text):
        self.terminal.feed_child(text.encode('utf-8'))

    def on_entry_activate(self, entry):
        cmd = entry.get_text(); entry.set_text("")
        if self.shell: self.shell.send(cmd + "\n")
        if cmd: self.history.append(cmd); self.history_index = len(self.history)

    def on_key_press(self, widget, event):
        if not self.history: return False
        if event.keyval == Gdk.KEY_Up:
            self.history_index = max(0, self.history_index - 1); widget.set_text(self.history[self.history_index]); return True
        elif event.keyval == Gdk.KEY_Down:
            self.history_index = min(len(self.history), self.history_index + 1); widget.set_text(self.history[self.history_index] if self.history_index < len(self.history) else ""); return True
        return False

class SSHGui(Gtk.Window):
    def __init__(self):
        super().__init__(title="Zeno-SSH Explorer"); self.set_default_size(1200, 800); self.connect("destroy", Gtk.main_quit)
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL); self.add(self.paned)
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); sidebar.set_margin_all(10); sidebar.set_size_request(250, -1)
        sb_scrolled = Gtk.ScrolledWindow(); self.tree_store = Gtk.TreeStore(str, str); self.tree_view = Gtk.TreeView(model=self.tree_store)
        col = Gtk.TreeViewColumn("Systems"); cell = Gtk.CellRendererText(); col.pack_start(cell, True); col.add_attribute(cell, "text", 0); self.tree_view.append_column(col); self.tree_view.connect("row-activated", self.on_tree_item_activated); sb_scrolled.add(self.tree_view)
        sidebar.pack_start(sb_scrolled, True, True, 0); r_btn = Gtk.Button(label="Refresh List"); r_btn.connect("clicked", lambda x: self.refresh_host_list()); sidebar.pack_start(r_btn, False, False, 5); self.paned.pack1(sidebar, False, False)
        main_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10); main_content.set_margin_all(10); self.paned.pack2(main_content, True, False)
        self.notebook = Gtk.Notebook(); self.notebook.set_scrollable(True); main_content.pack_start(self.notebook, True, True, 0)
        b_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10); b_box.get_style_context().add_class("broadcast-bar"); main_content.pack_start(b_box, False, False, 0)
        self.broadcast_entry = Gtk.Entry(placeholder_text="Broadcast to all active terminal sessions..."); self.broadcast_entry.connect("activate", self.on_broadcast); b_box.pack_start(self.broadcast_entry, True, True, 0)
        ed_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5); ed_scrolled = Gtk.ScrolledWindow(); self.host_text_view = Gtk.TextView(); ed_scrolled.add(self.host_text_view); ed_box.pack_start(ed_scrolled, True, True, 0)
        s_btn = Gtk.Button(label="Save & Reload List"); s_btn.connect("clicked", self.on_save_hosts); ed_box.pack_start(s_btn, False, False, 5); self.notebook.append_page(ed_box, Gtk.Label(label="⚙ Host Config"))
        self.host_widgets = {}; self.host_configs = {}
        self.load_hosts_into_editor(); self.refresh_host_list(); self.apply_styles()

    def load_hosts_into_editor(self):
        if os.path.exists("hosts.txt"):
            with open("hosts.txt", "r") as f: self.host_text_view.get_buffer().set_text(f.read())

    def on_save_hosts(self, btn):
        buf = self.host_text_view.get_buffer(); content = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
        if content:
            with open("hosts.txt", "w") as f: f.write(content)
            self.refresh_host_list()

    def refresh_host_list(self):
        self.tree_store.clear(); self.host_groups = {}; self.host_configs = {}
        self.group_combo.remove_all(); self.group_combo.append_text("All Groups"); self.group_combo.set_active(0)
        if os.path.exists("hosts.txt"):
            current_group = "all"; group_iter = None
            with open("hosts.txt", "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    if line.startswith("["): current_group = line[1:-1]; group_iter = self.tree_store.append(None, [current_group.upper(), "group"]); self.group_combo.append_text(current_group); continue
                    if "|" in line:
                        p = [x.strip() for x in line.split("|")]
                        if len(p) >= 2:
                            alias = p[0]; self.host_configs[alias] = {"host":p[1], "port":p[2] if len(p)>2 else "22", "user":p[3] if len(p)>3 else ""}
                            self.tree_store.append(group_iter, [f"SFTP: {alias}", "host"])
                    else: self.tree_store.append(group_iter, [line, "host"])
        self.tree_view.expand_all()

    def on_tree_item_activated(self, tree_view, path, column):
        model = tree_view.get_model(); iter = model.get_iter(path); label, type = model.get(iter, 0, 1)
        if type == "host":
            if label.startswith("SFTP: "): label = label[6:]
            self.add_host_tab(label)

    def add_host_tab(self, host):
        if host in self.host_widgets: self.notebook.set_current_page(self.notebook.page_num(self.host_widgets[host])); return
        term = HostTerminal(host, self, self.host_configs.get(host))
        lbl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5); lbl_box.pack_start(Gtk.Label(label=host), False, False, 0)
        c_btn = Gtk.Button.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU); c_btn.set_relief(Gtk.ReliefStyle.NONE); c_btn.connect("clicked", lambda x: self.close_tab(host)); lbl_box.pack_start(c_btn, False, False, 0); lbl_box.show_all()
        new_index = self.notebook.append_page(term, lbl_box); self.host_widgets[host] = term; self.notebook.show_all(); self.notebook.set_current_page(new_index)

    def close_tab(self, host):
        if host in self.host_widgets: self.notebook.remove_page(self.notebook.page_num(self.host_widgets[host])); del self.host_widgets[host]

    def on_broadcast(self, widget):
        cmd = self.broadcast_entry.get_text(); self.broadcast_entry.set_text("")
        for host, term in self.host_widgets.items():
            if term.shell: term.shell.send(cmd + "\n")

    def apply_styles(self):
        css = b".broadcast-bar { background-color: #2c3e50; padding: 10px; border-radius: 5px; }"
        provider = Gtk.CssProvider(); provider.load_from_data(css); Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

if __name__ == "__main__":
    win = SSHGui(); win.show_all(); Gtk.main()
