#!/usr/bin/python3
import gi
import os
import threading
import paramiko
from scp import SCPClient

gi.require_version('Gtk', '3.0')
gi.require_version('Vte', '2.91')
gi.require_version('Pango', '1.0')
from gi.repository import Gtk, Vte, GLib, Gdk, Pango

class HostTerminal(Gtk.Box):
    def __init__(self, host, parent_gui):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.host = host
        self.parent_gui = parent_gui
        self.started = False
        self.base_dir = os.getcwd()
        
        # History
        self.history = []
        self.history_index = -1
        
        # Connection Controls
        ctrl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        ctrl_box.set_margin_top(5); ctrl_box.set_margin_bottom(5)
        ctrl_box.set_margin_start(5); ctrl_box.set_margin_end(5)
        self.pack_start(ctrl_box, False, False, 0)
        
        self.user_entry = Gtk.Entry()
        self.user_entry.set_width_chars(12)
        self.user_entry.set_text(os.getlogin() if hasattr(os, 'getlogin') else "user")
        ctrl_box.pack_start(self.user_entry, False, False, 0)
        
        self.pwd_entry = Gtk.Entry()
        self.pwd_entry.set_width_chars(12)
        self.pwd_entry.set_visibility(False)
        self.pwd_entry.set_placeholder_text("Password")
        self.pwd_entry.connect("activate", lambda x: self.start_shell())
        ctrl_box.pack_start(self.pwd_entry, False, False, 0)
        
        self.port_entry = Gtk.Entry()
        self.port_entry.set_width_chars(5)
        self.port_entry.set_text("22")
        ctrl_box.pack_start(self.port_entry, False, False, 0)
        
        self.conn_btn = Gtk.Button(label="Connect")
        self.conn_btn.connect("clicked", lambda x: self.start_shell())
        ctrl_box.pack_start(self.conn_btn, False, False, 0)

        # Tabbed Content (Terminal / SFTP / SCP)
        self.inner_notebook = Gtk.Notebook()
        self.pack_start(self.inner_notebook, True, True, 0)

        # Terminal Tab
        terminal_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        scrolled = Gtk.ScrolledWindow()
        self.terminal = Vte.Terminal()
        self.terminal.set_scrollback_lines(10000)
        self.terminal.set_font(Pango.FontDescription.from_string("monospace 10"))
        self.terminal.set_color_foreground(Gdk.RGBA(0, 1, 0, 1)) # Green
        self.terminal.set_color_background(Gdk.RGBA(0, 0, 0, 1)) # Black
        scrolled.add(self.terminal)
        terminal_box.pack_start(scrolled, True, True, 0)
        
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Enter command...")
        self.entry.connect("activate", self.on_entry_activate)
        self.entry.connect("key-press-event", self.on_key_press)
        terminal_box.pack_start(self.entry, False, False, 0)
        
        self.inner_notebook.append_page(terminal_box, Gtk.Label(label="Terminal"))

        # SFTP Tab
        self.sftp_box = self.create_transfer_tab("SFTP")
        self.inner_notebook.append_page(self.sftp_box, Gtk.Label(label="SFTP"))

        # SCP Tab
        self.scp_box = self.create_transfer_tab("SCP")
        self.inner_notebook.append_page(self.scp_box, Gtk.Label(label="SCP"))

    def create_transfer_tab(self, protocol):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_all(10)
        
        box.pack_start(Gtk.Label(label="Local Path:", xalign=0), False, False, 0)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        local_entry = Gtk.Entry(placeholder_text="/path/to/local/file")
        local_entry.set_text(self.base_dir)
        hbox.pack_start(local_entry, True, True, 0)
        browse_btn = Gtk.Button(label="Browse...")
        browse_btn.connect("clicked", lambda b: self.on_browse_clicked(local_entry))
        hbox.pack_start(browse_btn, False, False, 0)
        box.pack_start(hbox, False, False, 0)
        
        box.pack_start(Gtk.Label(label="Remote Path:", xalign=0), False, False, 0)
        remote_entry = Gtk.Entry(placeholder_text="/remote/path")
        box.pack_start(remote_entry, False, False, 0)
        
        btn_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        up_btn = Gtk.Button(label=f"{protocol} Upload")
        up_btn.connect("clicked", lambda x: self.on_transfer_op(protocol, "upload", local_entry, remote_entry))
        btn_hbox.pack_start(up_btn, False, False, 0)
        
        down_btn = Gtk.Button(label=f"{protocol} Download")
        down_btn.connect("clicked", lambda x: self.on_transfer_op(protocol, "download", local_entry, remote_entry))
        btn_hbox.pack_start(down_btn, False, False, 0)
        box.pack_start(btn_hbox, False, False, 0)
        
        log_scroll = Gtk.ScrolledWindow()
        log_view = Gtk.TextView(editable=False, cursor_visible=False)
        log_scroll.add(log_view)
        box.pack_start(log_scroll, True, True, 0)
        
        # Store refs
        if protocol == "SFTP":
            self.sftp_local = local_entry; self.sftp_remote = remote_entry; self.sftp_log_view = log_view
        else:
            self.scp_local = local_entry; self.scp_remote = remote_entry; self.scp_log_view = log_view
            
        return box

    def set_margin_all(self, widget, val):
        widget.set_margin_top(val)
        widget.set_margin_bottom(val)
        widget.set_margin_start(val)
        widget.set_margin_end(val)

    def on_browse_clicked(self, entry):
        dialog = Gtk.FileChooserDialog(
            title="Please choose a file", parent=self.get_toplevel(),
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        if dialog.run() == Gtk.ResponseType.OK:
            entry.set_text(dialog.get_filename())
        dialog.destroy()

    def log_transfer(self, protocol, msg):
        log_view = self.sftp_log_view if protocol == "SFTP" else self.scp_log_view
        buf = log_view.get_buffer()
        buf.insert(buf.get_end_iter(), msg + "\n")

    def on_transfer_op(self, protocol, op_type, local_ent, remote_ent):
        local = local_ent.get_text()
        remote = remote_ent.get_text()
        user = self.user_entry.get_text()
        pwd = self.pwd_entry.get_text()
        port = int(self.port_entry.get_text()) if self.port_entry.get_text().isdigit() else 22
        
        if not local or not remote:
            self.log_transfer(protocol, "[-] Error: Paths required.")
            return
            
        threading.Thread(target=self._transfer_thread, args=(protocol, op_type, local, remote, user, pwd, port), daemon=True).start()

    def _transfer_thread(self, protocol, op_type, local, remote, user, pwd, port):
        try:
            GLib.idle_add(self.log_transfer, protocol, f"[*] Starting {op_type} via {protocol} to {self.host}:{port}...")
            
            transport = paramiko.Transport((self.host, port))
            transport.connect(username=user, password=pwd)
            
            if protocol == "SFTP":
                sftp = paramiko.SFTPClient.from_transport(transport)
                if op_type == "upload":
                    sftp.put(local, remote)
                else:
                    sftp.get(remote, local)
                sftp.close()
            else:
                with SCPClient(transport) as scp:
                    if op_type == "upload":
                        scp.put(local, recursive=True, remote_path=remote)
                    else:
                        scp.get(remote, local_path=local, recursive=True)
                
            transport.close()
            GLib.idle_add(self.log_transfer, protocol, f"[+] {op_type.capitalize()} successful!")
        except Exception as e:
            GLib.idle_add(self.log_transfer, protocol, f"[-] {protocol} Error: {e}")

    def on_entry_activate(self, entry):
        cmd = self.entry.get_text()
        if self.started:
            self.send_string(cmd + "\n")
            if cmd:
                self.history.append(cmd)
                self.history_index = len(self.history)
            self.entry.set_text("")

    def on_key_press(self, widget, event):
        if not self.history: return False
        if event.keyval == Gdk.KEY_Up:
            self.history_index = max(0, self.history_index - 1)
            self.entry.set_text(self.history[self.history_index])
            return True
        elif event.keyval == Gdk.KEY_Down:
            self.history_index = min(len(self.history), self.history_index + 1)
            if self.history_index < len(self.history):
                self.entry.set_text(self.history[self.history_index])
            else:
                self.entry.set_text("")
            return True
        return False

    def start_shell(self):
        if self.started: return
        self.started = True
        self.conn_btn.set_sensitive(False)
        self.conn_btn.set_label("Connecting...")
        user = self.user_entry.get_text()
        port = self.port_entry.get_text()
        ssh_cmd = ["/usr/bin/ssh", "-p", port, "-t", f"{user}@{self.host}", "bash"]
        self.terminal.spawn_async(Vte.PtyFlags.DEFAULT, os.getcwd(), ssh_cmd, None, GLib.SpawnFlags.DEFAULT, None, None, -1, None, self.on_spawn_complete)

    def on_spawn_complete(self, terminal, pid, error):
        if error:
            print(f"Error spawning for {self.host}: {error.message}")
            self.parent_gui.update_host_status(self.host, "error")
            self.conn_btn.set_sensitive(True)
            self.conn_btn.set_label("Connect")
            self.started = False
        else:
            self.parent_gui.update_host_status(self.host, "success")
            self.conn_btn.set_label("Connected")
            self.terminal.connect("child-exited", self.on_child_exited)
            pwd = self.pwd_entry.get_text()
            if pwd: GLib.timeout_add(1000, self.send_string, pwd + "\n")

    def on_child_exited(self, terminal, status):
        self.parent_gui.update_host_status(self.host, "error")
        self.conn_btn.set_sensitive(True)
        self.conn_btn.set_label("Connect")
        self.started = False

    def send_string(self, text):
        self.terminal.feed_child(text.encode('utf-8'))
        return False

class SSHGui(Gtk.Window):
    def __init__(self):
        self.version = "1.0.0"
        if os.path.exists("VERSION"):
            with open("VERSION", "r") as f: self.version = f.read().strip()
        super().__init__(title=f"Zeno-SSH v{self.version}")
        self.set_default_size(1200, 800)
        self.connect("destroy", Gtk.main_quit)
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(self.paned)
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        sidebar.set_margin_all(10); sidebar.set_size_request(250, -1)
        sidebar.pack_start(Gtk.Label(label="<b>Server Browser</b>", use_markup=True), False, False, 5)
        sb_scrolled = Gtk.ScrolledWindow()
        self.tree_store = Gtk.TreeStore(str, str)
        self.tree_view = Gtk.TreeView(model=self.tree_store)
        col = Gtk.TreeViewColumn("Systems")
        cell = Gtk.CellRendererText()
        col.pack_start(cell, True); col.add_attribute(cell, "text", 0)
        self.tree_view.append_column(col)
        self.tree_view.connect("row-activated", self.on_tree_item_activated)
        sb_scrolled.add(self.tree_view)
        sidebar.pack_start(sb_scrolled, True, True, 0)
        refresh_btn = Gtk.Button(label="Refresh List")
        refresh_btn.connect("clicked", lambda x: self.refresh_host_list())
        sidebar.pack_start(refresh_btn, False, False, 5)
        self.paned.pack1(sidebar, False, False)
        main_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_content.set_margin_all(10); self.paned.pack2(main_content, True, False)
        self.notebook = Gtk.Notebook()
        self.notebook.set_scrollable(True)
        main_content.pack_start(self.notebook, True, True, 0)
        b_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        b_box.get_style_context().add_class("broadcast-bar")
        main_content.pack_start(b_box, False, False, 0)
        self.b_history = []; self.b_history_index = -1
        self.group_combo = Gtk.ComboBoxText()
        self.group_combo.append_text("All Groups"); self.group_combo.set_active(0)
        b_box.pack_start(self.group_combo, False, False, 0)
        self.broadcast_entry = Gtk.Entry()
        self.broadcast_entry.set_placeholder_text("BROADCAST command to SELECTED group...")
        self.broadcast_entry.connect("activate", self.on_broadcast)
        self.broadcast_entry.connect("key-press-event", self.on_broadcast_key_press)
        b_box.pack_start(self.broadcast_entry, True, True, 0)
        b_btn = Gtk.Button(label="Broadcast All")
        b_btn.connect("clicked", self.on_broadcast)
        b_box.pack_start(b_btn, False, False, 0)
        self.editor_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        ed_scrolled = Gtk.ScrolledWindow()
        self.host_text_view = Gtk.TextView()
        ed_scrolled.add(self.host_text_view)
        self.editor_box.pack_start(ed_scrolled, True, True, 0)
        save_btn = Gtk.Button(label="Save & Reload List")
        save_btn.connect("clicked", self.on_save_hosts)
        self.editor_box.pack_start(save_btn, False, False, 5)
        self.notebook.append_page(self.editor_box, Gtk.Label(label="⚙ Host Config"))
        self.host_widgets = {}; self.tab_labels = {}; self.host_groups = {}
        self.load_hosts_into_editor(); self.refresh_host_list(); self.apply_styles()

    def set_margin_all(self, widget, val):
        widget.set_margin_top(val); widget.set_margin_bottom(val); widget.set_margin_start(val); widget.set_margin_end(val)

    def apply_styles(self):
        css = b".broadcast-bar { background-color: #2c3e50; padding: 10px; border-radius: 5px; }"
        provider = Gtk.CssProvider(); provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def load_hosts_into_editor(self):
        if os.path.exists("hosts.txt"):
            with open("hosts.txt", "r") as f: self.host_text_view.get_buffer().set_text(f.read())

    def on_save_hosts(self, btn):
        buf = self.host_text_view.get_buffer()
        content = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
        with open("hosts.txt", "w") as f: f.write(content)
        self.refresh_host_list()

    def refresh_host_list(self):
        self.tree_store.clear(); self.host_groups = {}
        self.group_combo.remove_all(); self.group_combo.append_text("All Groups"); self.group_combo.set_active(0)
        found_groups = set()
        if os.path.exists("hosts.txt"):
            current_group = "all"; group_iter = None
            with open("hosts.txt", "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    if line.startswith("[") and line.endswith("]"):
                        current_group = line[1:-1]
                        group_iter = self.tree_store.append(None, [current_group, "group"])
                        if current_group not in found_groups:
                            self.group_combo.append_text(current_group); found_groups.add(current_group)
                        continue
                    self.host_groups[line] = current_group; self.tree_store.append(group_iter, [line, "host"])

    def on_tree_item_activated(self, tree_view, path, column):
        model = tree_view.get_model(); iter = model.get_iter(path)
        label, type = model.get(iter, 0, 1)
        if type == "host": self.add_host_tab(label)

    def add_host_tab(self, host):
        if host in self.host_widgets:
            self.notebook.set_current_page(self.notebook.page_num(self.host_widgets[host]))
            return
        term = HostTerminal(host, self)
        group = self.host_groups.get(host, "all")
        lbl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        dot = Gtk.Label(label="●"); lbl_box.pack_start(dot, False, False, 0)
        lbl_box.pack_start(Gtk.Label(label=f"{host} ({group})" if group != "all" else host), False, False, 0)
        close_btn = Gtk.Button.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU)
        close_btn.set_relief(Gtk.ReliefStyle.NONE); close_btn.connect("clicked", lambda x: self.close_tab(host))
        lbl_box.pack_start(close_btn, False, False, 0); lbl_box.show_all()
        new_index = self.notebook.append_page(term, lbl_box)
        self.host_widgets[host] = term; self.tab_labels[host] = dot; self.notebook.show_all(); self.notebook.set_current_page(new_index)

    def close_tab(self, host):
        if host in self.host_widgets:
            self.notebook.remove_page(self.notebook.page_num(self.host_widgets[host]))
            del self.host_widgets[host]; del self.tab_labels[host]

    def update_host_status(self, host, state):
        GLib.idle_add(self._safe_status, host, state)

    def _safe_status(self, host, state):
        if host in self.tab_labels:
            dot = self.tab_labels[host]; ctx = dot.get_style_context()
            for c in ["tab-label-idle", "tab-label-running", "tab-label-error", "tab-label-success"]: ctx.remove_class(c)
            ctx.add_class(f"tab-label-{state}")
        return False

    def on_broadcast(self, widget):
        cmd = self.broadcast_entry.get_text(); self.broadcast_entry.set_text("")
        if cmd: self.b_history.append(cmd); self.b_history_index = len(self.b_history)
        selected_group = self.group_combo.get_active_text()
        for host, term in self.host_widgets.items():
            if term.started and (selected_group == "All Groups" or self.host_groups.get(host) == selected_group):
                term.send_string(cmd + "\n")

    def on_broadcast_key_press(self, widget, event):
        if not self.b_history: return False
        if event.keyval == Gdk.KEY_Up:
            self.b_history_index = max(0, self.b_history_index - 1)
            self.broadcast_entry.set_text(self.b_history[self.b_history_index])
            return True
        elif event.keyval == Gdk.KEY_Down:
            self.b_history_index = min(len(self.b_history), self.b_history_index + 1)
            self.broadcast_entry.set_text(self.b_history[self.b_history_index] if self.b_history_index < len(self.b_history) else "")
            return True
        return False

if __name__ == "__main__":
    win = SSHGui(); win.show_all(); Gtk.main()
