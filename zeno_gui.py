#!/usr/bin/python3
import gi
import os

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
        ctrl_box.pack_start(self.pwd_entry, False, False, 0)
        
        self.conn_btn = Gtk.Button(label="Connect")
        self.conn_btn.connect("clicked", lambda x: self.start_shell())
        ctrl_box.pack_start(self.conn_btn, False, False, 0)

        # Tabbed Content (Terminal / SFTP)
        self.inner_notebook = Gtk.Notebook()
        self.pack_start(self.inner_notebook, True, True, 0)

        # Terminal Tab
        scrolled = Gtk.ScrolledWindow()
        self.terminal = Vte.Terminal()
        self.terminal.set_scrollback_lines(10000)
        self.terminal.set_font(Pango.FontDescription.from_string("monospace 10"))
        self.terminal.set_color_foreground(Gdk.RGBA(0, 1, 0, 1)) # Green
        self.terminal.set_color_background(Gdk.RGBA(0, 0, 0, 1)) # Black
        scrolled.add(self.terminal)
        self.inner_notebook.append_page(scrolled, Gtk.Label(label="Terminal"))

        # SFTP Tab
        sftp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        sftp_box.set_margin_all(10)
        
        sftp_box.pack_start(Gtk.Label(label="Local Path:", xalign=0), False, False, 0)
        self.local_entry = Gtk.Entry(placeholder_text="/path/to/local/file")
        sftp_box.pack_start(self.local_entry, False, False, 0)
        
        sftp_box.pack_start(Gtk.Label(label="Remote Path:", xalign=0), False, False, 0)
        self.remote_entry = Gtk.Entry(placeholder_text="/home/user/remote_file")
        sftp_box.pack_start(self.remote_entry, False, False, 0)
        
        sftp_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        up_btn = Gtk.Button(label="Upload (Put)")
        up_btn.connect("clicked", lambda x: self.on_sftp_op("upload"))
        sftp_btn_box.pack_start(up_btn, False, False, 0)
        
        down_btn = Gtk.Button(label="Download (Get)")
        down_btn.connect("clicked", lambda x: self.on_sftp_op("download"))
        sftp_btn_box.pack_start(down_btn, False, False, 0)
        sftp_box.pack_start(sftp_btn_box, False, False, 0)
        
        sftp_log_scroll = Gtk.ScrolledWindow()
        self.sftp_log_view = Gtk.TextView(editable=False, cursor_visible=False)
        sftp_log_scroll.add(self.sftp_log_view)
        sftp_box.pack_start(sftp_log_scroll, True, True, 0)
        
        self.inner_notebook.append_page(sftp_box, Gtk.Label(label="File Transfer"))

    def log_sftp(self, msg):
        buf = self.sftp_log_view.get_buffer()
        buf.insert(buf.get_end_iter(), msg + "\n")
        
    def on_sftp_op(self, op_type):
        local = self.local_entry.get_text()
        remote = self.remote_entry.get_text()
        user = self.user_entry.get_text()
        pwd = self.pwd_entry.get_text()
        
        if not local or not remote:
            self.log_sftp("[-] Error: Paths required.")
            return
            
        threading.Thread(target=self._sftp_thread, args=(op_type, local, remote, user, pwd), daemon=True).start()

    def _sftp_thread(self, op_type, local, remote, user, pwd):
        try:
            GLib.idle_add(self.log_sftp, f"[*] Starting {op_type} to {self.host}...")
            transport = paramiko.Transport((self.host, 22))
            transport.connect(username=user, password=pwd)
            sftp = paramiko.SFTPClient.from_transport(transport)
            
            if op_type == "upload":
                sftp.put(local, remote)
            else:
                sftp.get(remote, local)
                
            sftp.close()
            transport.close()
            GLib.idle_add(self.log_sftp, f"[+] {op_type.capitalize()} successful!")
        except Exception as e:
            GLib.idle_add(self.log_sftp, f"[-] SFTP Error: {e}")

    def start_shell(self):
        if self.started:
            return
        self.started = True
        self.conn_btn.set_sensitive(False)
        self.conn_btn.set_label("Connecting...")
        
        user = self.user_entry.get_text()
        # ssh-askpass fallback or use expect if we wanted automation, 
        # but here we rely on the terminal's native password prompt support
        ssh_cmd = ["/usr/bin/ssh", "-t", f"{user}@{self.host}", "bash"]
        
        self.terminal.spawn_async(
            Vte.PtyFlags.DEFAULT,
            os.getcwd(),
            ssh_cmd,
            None,
            GLib.SpawnFlags.DEFAULT,
            None,
            None,
            -1,
            None,
            self.on_spawn_complete
        )

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
            # Connect the child-exited signal to handle disconnects
            self.terminal.connect("child-exited", self.on_child_exited)
            
            # Send password if provided
            pwd = self.pwd_entry.get_text()
            if pwd:
                GLib.timeout_add(1000, self.send_string, pwd + "\n")

    def on_child_exited(self, terminal, status):
        self.parent_gui.update_host_status(self.host, "error")
        self.conn_btn.set_sensitive(True)
        self.conn_btn.set_label("Connect")
        self.started = False

    def send_string(self, text):
        """Sends raw text to the shell's stdin."""
        self.terminal.feed_child(text.encode('utf-8'))
        return False

class SSHGui(Gtk.Window):
    def __init__(self):
        # Read version from file
        self.version = "1.0.0"
        if os.path.exists("VERSION"):
            with open("VERSION", "r") as f:
                self.version = f.read().strip()
                
        super().__init__(title=f"Zeno-SSH v{self.version}")
        self.set_default_size(1200, 800)
        self.connect("destroy", Gtk.main_quit)

        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(self.paned)

        # Sidebar: Hosts Tree
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        sidebar.set_margin_top(10); sidebar.set_margin_bottom(10)
        sidebar.set_margin_start(10); sidebar.set_margin_end(10)
        sidebar.set_size_request(250, -1)
        
        sb_label = Gtk.Label(label="<b>Server Browser</b>", use_markup=True)
        sidebar.pack_start(sb_label, False, False, 5)

        sb_scrolled = Gtk.ScrolledWindow()
        self.tree_store = Gtk.TreeStore(str, str) # Label, Type (group/host)
        self.tree_view = Gtk.TreeView(model=self.tree_store)
        col = Gtk.TreeViewColumn("Systems")
        cell = Gtk.CellRendererText()
        col.pack_start(cell, True)
        col.add_attribute(cell, "text", 0)
        self.tree_view.append_column(col)
        self.tree_view.connect("row-activated", self.on_tree_item_activated)
        
        sb_scrolled.add(self.tree_view)
        sidebar.pack_start(sb_scrolled, True, True, 0)

        refresh_btn = Gtk.Button(label="Refresh List")
        refresh_btn.connect("clicked", lambda x: self.refresh_host_list())
        sidebar.pack_start(refresh_btn, False, False, 5)
        
        self.paned.pack1(sidebar, False, False)

        # Main Content
        main_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_content.set_margin_top(10)
        main_content.set_margin_bottom(10)
        main_content.set_margin_start(10)
        main_content.set_margin_end(10)
        self.paned.pack2(main_content, True, False)

        # Notebook (Tabs)
        self.notebook = Gtk.Notebook()
        self.notebook.set_scrollable(True)
        # self.notebook.connect("switch-page", self.on_tab_switched) # Removed auto-start
        main_content.pack_start(self.notebook, True, True, 0)

        # Broadcast Bar (Bottom)
        b_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        b_box.get_style_context().add_class("broadcast-bar")
        main_content.pack_start(b_box, False, False, 0)

        # Group Selector
        self.group_combo = Gtk.ComboBoxText()
        self.group_combo.append_text("All Groups")
        self.group_combo.set_active(0)
        b_box.pack_start(self.group_combo, False, False, 0)

        self.broadcast_entry = Gtk.Entry()
        self.broadcast_entry.set_placeholder_text("BROADCAST command to SELECTED group...")
        self.broadcast_entry.connect("activate", self.on_broadcast)
        b_box.pack_start(self.broadcast_entry, True, True, 0)

        b_btn = Gtk.Button(label="Broadcast All")
        b_btn.connect("clicked", self.on_broadcast)
        b_box.pack_start(b_btn, False, False, 0)

        # Permanent Editor Tab
        self.editor_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        ed_scrolled = Gtk.ScrolledWindow()
        self.host_text_view = Gtk.TextView()
        ed_scrolled.add(self.host_text_view)
        self.editor_box.pack_start(ed_scrolled, True, True, 0)
        
        save_btn = Gtk.Button(label="Save & Reload List")
        save_btn.connect("clicked", self.on_save_hosts)
        self.editor_box.pack_start(save_btn, False, False, 5)
        
        self.notebook.append_page(self.editor_box, Gtk.Label(label="⚙ Host Config"))

        self.host_widgets = {}
        self.tab_labels = {}
        self.host_groups = {}
        
        self.load_hosts_into_editor()
        self.refresh_host_list()
        self.apply_styles()

    def set_margin_all(self, widget, val):
        widget.set_margin_top(val)
        widget.set_margin_bottom(val)
        widget.set_margin_start(val)
        widget.set_margin_end(val)

    def add_host_tab(self, host):
        """Adds a terminal tab for a host if it doesn't already exist."""
        if host in self.host_widgets:
            # Switch to existing tab
            term = self.host_widgets[host]
            self.notebook.set_current_page(self.notebook.page_num(term))
            return

        term = HostTerminal(host, self)
        
        # Tab Label with status dot and group
        group = self.host_groups.get(host, "all")
        lbl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        dot = Gtk.Label(label="●")
        lbl_box.pack_start(dot, False, False, 0)
        
        label_text = f"{host} ({group})" if group != "all" else host
        lbl_box.pack_start(Gtk.Label(label=label_text), False, False, 0)
        
        # Close button for the tab
        close_btn = Gtk.Button.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU)
        close_btn.set_relief(Gtk.ReliefStyle.NONE)
        close_btn.connect("clicked", lambda x: self.close_tab(host))
        lbl_box.pack_start(close_btn, False, False, 0)
        
        lbl_box.show_all()
        
        new_index = self.notebook.append_page(term, lbl_box)
        self.host_widgets[host] = term
        self.tab_labels[host] = dot
        self.notebook.show_all()
        self.notebook.set_current_page(new_index)

    def close_tab(self, host):
        if host in self.host_widgets:
            term = self.host_widgets[host]
            page_num = self.notebook.page_num(term)
            self.notebook.remove_page(page_num)
            del self.host_widgets[host]
            del self.tab_labels[host]

    def update_host_status(self, host, state):
        GLib.idle_add(self._safe_status, host, state)

    def _safe_status(self, host, state):
        if host in self.tab_labels:
            dot = self.tab_labels[host]
            ctx = dot.get_style_context()
            for c in ["tab-label-idle", "tab-label-running", "tab-label-error", "tab-label-success"]:
                ctx.remove_class(c)
            ctx.add_class(f"tab-label-{state}")
        return False

    def on_broadcast(self, widget):
        cmd = self.broadcast_entry.get_text()
        if not cmd: return
        self.broadcast_entry.set_text("")
        
        selected_group = self.group_combo.get_active_text()
        
        for host, term in self.host_widgets.items():
            if term.started and (selected_group == "All Groups" or self.host_groups.get(host) == selected_group):
                term.send_string(cmd + "\n")

if __name__ == "__main__":
    win = SSHGui()
    win.show_all()
    Gtk.main()
