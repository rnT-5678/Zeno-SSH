#!/usr/bin/python3
import gi
import os

gi.require_version('Gtk', '3.0')
gi.require_version('Vte', '2.91')
gi.require_version('Pango', '1.0')
from gi.repository import Gtk, Vte, GLib, Gdk, Pango

class HostTerminal(Vte.Terminal):
    def __init__(self, host, parent_gui):
        super().__init__()
        self.host = host
        self.parent_gui = parent_gui
        self.started = False
        self.set_scrollback_lines(10000)
        self.set_font(Pango.FontDescription.from_string("monospace 10"))
        
        # Style like a terminal
        self.set_color_foreground(Gdk.RGBA(0, 1, 0, 1)) # Green
        self.set_color_background(Gdk.RGBA(0, 0, 0, 1)) # Black

    def start_shell(self):
        if self.started:
            return
        self.started = True
        user = self.parent_gui.user_entry.get_text()
        # Remove BatchMode=yes to allow for interactive password prompts
        ssh_cmd = ["/usr/bin/ssh", "-t", f"{user}@{self.host}", "bash"]
        
        self.spawn_async(
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
        else:
            self.parent_gui.update_host_status(self.host, "success")
            # Connect the child-exited signal to handle disconnects
            self.connect("child-exited", self.on_child_exited)

    def on_child_exited(self, terminal, status):
        self.parent_gui.update_host_status(self.host, "error")

    def send_string(self, text):
        """Sends raw text to the shell's stdin."""
        self.feed_child(text.encode('utf-8'))

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

        # Broadcast Bar
        b_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        b_box.get_style_context().add_class("broadcast-bar")
        main_content.pack_start(b_box, False, False, 0)

        self.user_entry = Gtk.Entry()
        self.user_entry.set_width_chars(8)
        self.user_entry.set_text(os.getlogin() if hasattr(os, 'getlogin') else "user")
        self.user_entry.set_placeholder_text("User")
        b_box.pack_start(self.user_entry, False, False, 0)

        self.password_entry = Gtk.Entry()
        self.password_entry.set_width_chars(8)
        self.password_entry.set_visibility(False)
        self.password_entry.set_placeholder_text("Password")
        b_box.pack_start(self.password_entry, False, False, 0)

        p_btn = Gtk.Button(label="Send Pwd")
        p_btn.connect("clicked", self.on_send_password)
        b_box.pack_start(p_btn, False, False, 0)

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

        # Notebook (Tabs)
        self.notebook = Gtk.Notebook()
        self.notebook.set_scrollable(True)
        self.notebook.connect("switch-page", self.on_tab_switched)
        main_content.pack_start(self.notebook, True, True, 0)

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

    def on_tab_switched(self, notebook, page, page_num):
        # page is the ScrolledWindow
        term = page.get_child()
        if isinstance(term, HostTerminal):
            term.start_shell()

    def set_margin_all(self, widget, val):
        widget.set_margin_top(val)
        widget.set_margin_bottom(val)
        widget.set_margin_start(val)
        widget.set_margin_end(val)

    def apply_styles(self):
        css = b"""
            .broadcast-bar { background-color: #2c3e50; padding: 10px; border-radius: 5px; }
            .tab-label-running { color: #3498db; font-weight: bold; }
            .tab-label-error { color: #e74c3c; font-weight: bold; }
            .tab-label-success { color: #2ecc71; font-weight: bold; }
            .tab-label-idle { color: #555; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def load_hosts_into_editor(self):
        if os.path.exists("hosts.txt"):
            with open("hosts.txt", "r") as f:
                self.host_text_view.get_buffer().set_text(f.read())

    def on_save_hosts(self, btn):
        buf = self.host_text_view.get_buffer()
        content = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
        with open("hosts.txt", "w") as f: f.write(content)
        self.refresh_host_list()

    def refresh_host_list(self):
        """Refreshes the sidebar tree and group combo based on hosts.txt."""
        self.tree_store.clear()
        self.host_groups = {}
        
        self.group_combo.remove_all()
        self.group_combo.append_text("All Groups")
        self.group_combo.set_active(0)
        found_groups = set()

        if os.path.exists("hosts.txt"):
            current_group = "all"
            group_iter = None
            
            with open("hosts.txt", "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    
                    if line.startswith("[") and line.endswith("]"):
                        current_group = line[1:-1]
                        group_iter = self.tree_store.append(None, [current_group, "group"])
                        if current_group not in found_groups:
                            self.group_combo.append_text(current_group)
                            found_groups.add(current_group)
                        continue

                    host = line
                    self.host_groups[host] = current_group
                    self.tree_store.append(group_iter, [host, "host"])

    def on_tree_item_activated(self, tree_view, path, column):
        model = tree_view.get_model()
        iter = model.get_iter(path)
        label, type = model.get(iter, 0, 1)
        
        if type == "host":
            self.add_host_tab(label)

    def add_host_tab(self, host):
        """Adds a terminal tab for a host if it doesn't already exist."""
        if host in self.host_widgets:
            # Switch to existing tab
            term = self.host_widgets[host]
            page_num = self.notebook.page_num(term.get_parent())
            self.notebook.set_current_page(page_num)
            return

        # Scrolled Window to wrap VTE Terminal
        scrolled = Gtk.ScrolledWindow()
        term = HostTerminal(host, self)
        scrolled.add(term)
        
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
        
        new_index = self.notebook.append_page(scrolled, lbl_box)
        self.host_widgets[host] = term
        self.tab_labels[host] = dot
        self.notebook.show_all()
        self.notebook.set_current_page(new_index)

    def close_tab(self, host):
        if host in self.host_widgets:
            term = self.host_widgets[host]
            scrolled = term.get_parent()
            page_num = self.notebook.page_num(scrolled)
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

    def on_send_password(self, btn):
        pwd = self.password_entry.get_text()
        if not pwd: return
        self.password_entry.set_text("")
        
        selected_group = self.group_combo.get_active_text()
        
        for host, term in self.host_widgets.items():
            if term.started and (selected_group == "All Groups" or self.host_groups.get(host) == selected_group):
                term.send_string(pwd + "\n")

if __name__ == "__main__":
    win = SSHGui()
    win.show_all()
    Gtk.main()
