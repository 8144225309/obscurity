import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import os
import obscurity_backend 

# --- CONFIGURATION ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class ObscurityApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Initialize Backend
        self.data_manager = obscurity_backend.DataManager()

        # Window Setup
        self.title("Obscurity [Fork-Aware] // Professional Edition")
        self.geometry("1300x850")

        # --- MAIN GRID LAYOUT ---
        # Col 0: Chains (Left)
        # Col 1: Blocks (Mid)
        # Col 2: Factories/System (Right)
        self.grid_columnconfigure(0, weight=0, minsize=220)
        self.grid_columnconfigure(1, weight=0, minsize=300)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. Left (Chains)
        self.frame_chains = ctk.CTkFrame(self, corner_radius=0)
        self.frame_chains.grid(row=0, column=0, sticky="nsew")
        self.build_chains_column()

        # 2. Mid (Blocks)
        self.frame_blocks = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a1a")
        self.frame_blocks.grid(row=0, column=1, sticky="nsew")
        self.build_blocks_column()

        # 3. Right (Factories + System)
        self.frame_right = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_right.grid(row=0, column=2, sticky="nsew", padx=20, pady=20)
        
        # Build the Right-Side Container Logic
        self.build_right_header()
        
        # Container for swappable views
        self.container = ctk.CTkFrame(self.frame_right, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        # Create the views
        self.view_factories = self.create_factories_view(self.container)
        self.view_config = self.create_config_view(self.container)
        self.view_keystore = self.create_keystore_view(self.container)

        # Start with Factories visible
        self.show_view("factories")
        
        # Apply hacky styles for Treeview and load data
        self.style_legacy_widgets()
        self.refresh_chain_list()

    def style_legacy_widgets(self):
        """Forces standard Tkinter Treeviews to look dark."""
        style = ttk.Style()
        style.theme_use("clam")
        
        bg_color = "#2b2b2b"
        fg_color = "#ffffff"
        hl_color = "#1f538d"
        
        style.configure("Treeview", 
                        background=bg_color, 
                        foreground=fg_color, 
                        fieldbackground=bg_color, 
                        borderwidth=0, 
                        rowheight=30, 
                        font=("Roboto Medium", 10))
        
        style.configure("Treeview.Heading", 
                        background="#202020", 
                        foreground="#aaaaaa", 
                        relief="flat", 
                        font=("Roboto", 9, "bold"))
        
        style.map("Treeview", background=[('selected', hl_color)])

    # --- UI BUILDERS (COLUMNS) ---

    def build_chains_column(self):
        lbl = ctk.CTkLabel(self.frame_chains, text="CHAINS / FORKS", font=("Roboto", 12, "bold"), text_color="#aaaaaa")
        lbl.pack(fill="x", pady=(15, 10), padx=10)
        
        tree_frame = ctk.CTkFrame(self.frame_chains, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True)

        self.tree_chains = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        self.tree_chains.pack(side="left", fill="both", expand=True)
        self.tree_chains.bind("<<TreeviewSelect>>", self.on_chain_select)
        
        # Scrollbar
        sb = ctk.CTkScrollbar(tree_frame, command=self.tree_chains.yview, width=16)
        sb.pack(side="right", fill="y")
        self.tree_chains.configure(yscrollcommand=sb.set)
        
        # Buttons
        btn_frame = ctk.CTkFrame(self.frame_chains, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", pady=10, padx=10)
        
        ctk.CTkButton(btn_frame, text="+ New Chain", height=35, command=self.action_new_chain).pack(fill="x", pady=5)
        ctk.CTkButton(btn_frame, text="⑂ Clone Chain", height=35, fg_color="#2d2d2d", hover_color="#3a3a3a").pack(fill="x")

    def build_blocks_column(self):
        lbl = ctk.CTkLabel(self.frame_blocks, text="BLOCK TIMELINE", font=("Roboto", 12, "bold"), text_color="#aaaaaa")
        lbl.pack(fill="x", pady=(15, 10), padx=10)

        tree_frame = ctk.CTkFrame(self.frame_blocks, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True)

        columns = ("status", "hash")
        self.tree_blocks = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        
        self.tree_blocks.heading("status", text="St")
        self.tree_blocks.column("status", width=40, anchor="center")
        self.tree_blocks.heading("hash", text="Block Hash / ID")
        self.tree_blocks.column("hash", width=220)
        
        self.tree_blocks.pack(side="left", fill="both", expand=True)
        
        # Scrollbar
        sb = ctk.CTkScrollbar(tree_frame, command=self.tree_blocks.yview, width=16)
        sb.pack(side="right", fill="y")
        self.tree_blocks.configure(yscrollcommand=sb.set)

    def build_right_header(self):
        # The Header Bar with separated System Buttons
        header = ctk.CTkFrame(self.frame_right, height=40, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))

        # Title
        ctk.CTkLabel(header, text="Active Workflow", font=("Roboto", 16, "bold")).pack(side="left")

        # Right side: System Buttons
        ctk.CTkFrame(header, width=20, height=1, fg_color="transparent").pack(side="right")
        
        # Config Button
        self.btn_cfg = ctk.CTkButton(header, text="⚙ Config", width=80, fg_color="#333", hover_color="#555", command=lambda: self.show_view("config"))
        self.btn_cfg.pack(side="right", padx=5)

        # Keystore Button
        self.btn_keys = ctk.CTkButton(header, text="🔑 Keystore", width=90, fg_color="#333", hover_color="#555", command=lambda: self.show_view("keystore"))
        self.btn_keys.pack(side="right", padx=5)
        
        # Workflow Button
        self.btn_work = ctk.CTkButton(header, text="🔨 Factories", width=90, fg_color="transparent", border_width=1, command=lambda: self.show_view("factories"))
        self.btn_work.pack(side="right", padx=5)

    # --- SWAPPABLE VIEWS ---

    def create_factories_view(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        
        tabs = ctk.CTkTabview(frame)
        tabs.pack(fill="both", expand=True)
        
        tabs.add("Payload Factory")
        tabs.add("Grind Factory")
        tabs.add("Network Factory")

        # Payload Tab
        p = tabs.tab("Payload Factory")
        ctk.CTkLabel(p, text="Step 1: Construct Block Data", font=("Roboto", 20, "bold")).pack(anchor="w", pady=(10, 20))
        
        # Examples
        f_ex = ctk.CTkFrame(p, fg_color="transparent")
        f_ex.pack(anchor="w", fill="x", pady=(0, 10))
        ctk.CTkLabel(f_ex, text="Load Example:", text_color="gray").pack(side="left", padx=(0, 10))
        ctk.CTkButton(f_ex, text="Hello World", height=24, width=80, fg_color="#333", hover_color="#444").pack(side="left", padx=5)
        ctk.CTkButton(f_ex, text="Small Image", height=24, width=80, fg_color="#333", hover_color="#444").pack(side="left", padx=5)

        self.txt_payload = ctk.CTkTextbox(p, font=("Consolas", 12))
        self.txt_payload.pack(fill="both", expand=True, pady=10)
        self.txt_payload.insert("0.0", "Enter your hex or text payload here...")
        
        ctk.CTkButton(p, text="COMPUTE HASH", height=50, font=("Roboto", 14, "bold"), fg_color="#1f538d").pack(fill="x", pady=10)

        # Grind Tab
        g = tabs.tab("Grind Factory")
        ctk.CTkLabel(g, text="Step 2: Generate Keys", font=("Roboto", 20, "bold")).pack(anchor="w", pady=(10, 20))
        
        f_cfg = ctk.CTkFrame(g)
        f_cfg.pack(fill="x", pady=10)
        ctk.CTkLabel(f_cfg, text="Difficulty (Bits per Key):").pack(side="left", padx=20)
        
        # The crucial slider for Piggyback vs Anchor
        ctk.CTkSlider(f_cfg, from_=1, to=32, number_of_steps=31).pack(side="left", fill="x", expand=True, padx=20)
        ctk.CTkLabel(f_cfg, text="(16=Piggyback, 32=Anchor)").pack(side="right", padx=20)
        
        ctk.CTkButton(g, text="▶ START GRINDER (xgrind)", height=60, font=("Roboto", 16, "bold"), fg_color="green", hover_color="darkgreen").pack(fill="x", pady=20)

        # Network Tab
        n = tabs.tab("Network Factory")
        ctk.CTkLabel(n, text="Step 3: Broadcast & Verify", font=("Roboto", 20, "bold")).pack(anchor="w", pady=(10, 20))
        ctk.CTkLabel(n, text="[TxID Linker Placeholder]").pack()

        return frame

    def create_config_view(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="#2b2b2b", corner_radius=10)
        
        ctk.CTkLabel(frame, text="System Configuration", font=("Roboto", 24, "bold")).pack(pady=20)
        
        form = ctk.CTkFrame(frame, fg_color="transparent")
        form.pack(pady=10)

        fields = [("RPC Host:", "127.0.0.1"), ("RPC Port:", "8332"), ("RPC User:", ""), ("RPC Password:", "")]
        for i, (label, default) in enumerate(fields):
            ctk.CTkLabel(form, text=label).grid(row=i, column=0, sticky="e", padx=10, pady=10)
            entry = ctk.CTkEntry(form, width=300)
            entry.insert(0, default)
            entry.grid(row=i, column=1, padx=10, pady=10)

        ctk.CTkLabel(form, text="Data Dir:").grid(row=4, column=0, sticky="e", padx=10, pady=10)
        default_path = os.path.join(os.getenv('APPDATA'), "Bitcoin") if os.name == 'nt' else ""
        e_dir = ctk.CTkEntry(form, width=300)
        e_dir.insert(0, default_path)
        e_dir.grid(row=4, column=1, padx=10, pady=10)
        
        ctk.CTkButton(frame, text="Save & Test Connection", width=200, height=40, fg_color="#1f538d").pack(pady=30)
        return frame

    def create_keystore_view(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="#2b2b2b", corner_radius=10)
        
        ctk.CTkLabel(frame, text="Secure Keystore", font=("Roboto", 24, "bold")).pack(pady=(20, 5))
        ctk.CTkLabel(frame, text="Manage exported private keys for your anchors.", text_color="gray").pack(pady=(0, 20))
        
        list_frame = ctk.CTkFrame(frame)
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        cols = ("filename", "size")
        tree = ttk.Treeview(list_frame, columns=cols, show="headings")
        tree.heading("filename", text="File Name")
        tree.heading("size", text="Size")
        tree.column("filename", width=400)
        tree.pack(side="left", fill="both", expand=True)
        
        # Load from backend
        files = self.data_manager.get_keystore_files()
        for f in files:
            tree.insert("", "end", values=(f, "Unknown"))
        
        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkButton(btn_row, text="Open Folder", fg_color="#444").pack(side="left", padx=5)
        ctk.CTkButton(btn_row, text="Delete Selected", fg_color="darkred").pack(side="right", padx=5)

        return frame

    def show_view(self, view_name):
        # Hide all
        self.view_factories.pack_forget()
        self.view_config.pack_forget()
        self.view_keystore.pack_forget()
        
        # Reset Header Colors
        self.btn_cfg.configure(fg_color="#333")
        self.btn_keys.configure(fg_color="#333")
        self.btn_work.configure(fg_color="transparent")

        # Show Selected
        if view_name == "factories":
            self.view_factories.pack(fill="both", expand=True)
            self.btn_work.configure(fg_color="#1f538d") # Highlight
        elif view_name == "config":
            self.view_config.pack(fill="both", expand=True)
            self.btn_cfg.configure(fg_color="#1f538d")
        elif view_name == "keystore":
            self.view_keystore.pack(fill="both", expand=True)
            self.btn_keys.configure(fg_color="#1f538d")

    # --- LOGIC & EVENTS ---

    def action_new_chain(self):
        dialog = ctk.CTkInputDialog(text="Enter name for new chain:", title="New Chain")
        name = dialog.get_input()
        if name:
            self.data_manager.create_new_chain(name)
            self.refresh_chain_list()

    def refresh_chain_list(self):
        for item in self.tree_chains.get_children():
            self.tree_chains.delete(item)
        
        chains = self.data_manager.get_chains()
        for c in chains:
            self.tree_chains.insert("", "end", text=f" {c}", values=(c,))

    def on_chain_select(self, event):
        # Auto-switch back to factories when a chain is clicked
        self.show_view("factories")
        
        selected = self.tree_chains.selection()
        if not selected: return
        
        chain_folder = self.tree_chains.item(selected)['values'][0]
        
        # Refresh Block List
        for item in self.tree_blocks.get_children():
            self.tree_blocks.delete(item)
            
        blocks = self.data_manager.load_blocks(chain_folder)
        for b in blocks:
            icon = "✅" if b.get('is_anchor') else "⚪"
            # Format hash safely
            h = b.get('block_hash', '????????')
            display_str = f"{b['index']:05d}_{h[:8]}..."
            self.tree_blocks.insert("", "end", values=(icon, display_str))

if __name__ == "__main__":
    app = ObscurityApp()
    app.mainloop()