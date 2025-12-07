import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import os

# Import our new backend logic
import obscurity_backend 

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class ObscurityApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # --- BACKEND INIT ---
        self.data_manager = obscurity_backend.DataManager()

        # Window Setup
        self.title("Obscurity [Fork-Aware] // Modern UI")
        self.geometry("1300x850")

        # --- LAYOUT GRID ---
        self.grid_columnconfigure(0, weight=0, minsize=220) # Chains
        self.grid_columnconfigure(1, weight=0, minsize=300) # Blocks
        self.grid_columnconfigure(2, weight=1)              # Factories
        self.grid_rowconfigure(0, weight=1)

        # --- COL 1: CHAINS SELECTOR ---
        self.frame_chains = ctk.CTkFrame(self, corner_radius=0)
        self.frame_chains.grid(row=0, column=0, sticky="nsew")
        self.build_chains_column()

        # --- COL 2: BLOCKS LIST ---
        self.frame_blocks = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a1a")
        self.frame_blocks.grid(row=0, column=1, sticky="nsew")
        self.build_blocks_column()

        # --- COL 3: FACTORIES (RIGHT) ---
        self.frame_factories = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_factories.grid(row=0, column=2, sticky="nsew", padx=20, pady=20)
        self.build_factories_area()

        # Style fixes
        self.style_legacy_widgets()
        
        # Initial Load
        self.refresh_chain_list()

    def style_legacy_widgets(self):
        # ... (Same styling logic as before) ...
        style = ttk.Style()
        style.theme_use("clam")
        bg_color, fg_color, hl_color = "#2b2b2b", "#ffffff", "#1f538d"
        style.configure("Treeview", background=bg_color, foreground=fg_color, fieldbackground=bg_color, borderwidth=0, rowheight=30, font=("Roboto Medium", 10))
        style.configure("Treeview.Heading", background="#202020", foreground="#aaaaaa", relief="flat", font=("Roboto", 9, "bold"))
        style.map("Treeview", background=[('selected', hl_color)])

    def build_chains_column(self):
        lbl = ctk.CTkLabel(self.frame_chains, text="CHAINS / FORKS", font=("Roboto", 12, "bold"), text_color="#aaaaaa")
        lbl.pack(fill="x", pady=(15, 10), padx=10)
        
        tree_frame = ctk.CTkFrame(self.frame_chains, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True)

        self.tree_chains = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        self.tree_chains.pack(side="left", fill="both", expand=True)
        self.tree_chains.bind("<<TreeviewSelect>>", self.on_chain_select) # Hook up selection
        
        sb = ctk.CTkScrollbar(tree_frame, command=self.tree_chains.yview, width=16)
        sb.pack(side="right", fill="y")
        self.tree_chains.configure(yscrollcommand=sb.set)
        
        btn_frame = ctk.CTkFrame(self.frame_chains, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", pady=10, padx=10)
        
        # NEW CHAIN BUTTON
        self.btn_new_chain = ctk.CTkButton(btn_frame, text="+ New Chain", height=35, command=self.action_new_chain)
        self.btn_new_chain.pack(fill="x", pady=5)
        
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
        
        sb = ctk.CTkScrollbar(tree_frame, command=self.tree_blocks.yview, width=16)
        sb.pack(side="right", fill="y")
        self.tree_blocks.configure(yscrollcommand=sb.set)
        self.tree_blocks.pack(side="left", fill="both", expand=True)

    def build_factories_area(self):
        # --- HEADER WITH CONFIG BUTTON ---
        header_frame = ctk.CTkFrame(self.frame_factories, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(header_frame, text="Active Workflow", font=("Roboto", 16, "bold")).pack(side="left")
        
        # The separated Config Button (Pushed to the right)
        self.btn_config = ctk.CTkButton(header_frame, text="⚙ Settings", width=80, fg_color="#333", hover_color="#555", command=self.open_settings_modal)
        self.btn_config.pack(side="right")

        # --- TABS ---
        self.tabs = ctk.CTkTabview(self.frame_factories)
        self.tabs.pack(fill="both", expand=True)
        
        self.tabs.add("Payload Factory")
        self.tabs.add("Grind Factory")
        self.tabs.add("Network Factory")

        self.build_tab_payload(self.tabs.tab("Payload Factory"))
        self.build_tab_grind(self.tabs.tab("Grind Factory"))
        self.build_tab_network(self.tabs.tab("Network Factory"))

    def build_tab_payload(self, parent):
        # ... (Same payload UI) ...
        ctk.CTkLabel(parent, text="Step 1: Construct Block Data", font=("Roboto", 20, "bold")).pack(anchor="w", pady=(10, 20))
        self.txt_payload = ctk.CTkTextbox(parent, font=("Consolas", 12))
        self.txt_payload.pack(fill="both", expand=True, pady=10)
        ctk.CTkButton(parent, text="COMPUTE HASH", height=50, font=("Roboto", 14, "bold"), fg_color="#1f538d").pack(fill="x", pady=10)

    def build_tab_grind(self, parent):
        # ... (Same grind UI) ...
        ctk.CTkLabel(parent, text="Step 2: Generate Keys", font=("Roboto", 20, "bold")).pack(anchor="w", pady=(10, 20))
        ctk.CTkButton(parent, text="▶ START GRINDER (xgrind)", height=60, font=("Roboto", 16, "bold"), fg_color="green", hover_color="darkgreen").pack(fill="x", pady=20)

    def build_tab_network(self, parent):
        ctk.CTkLabel(parent, text="Step 3: Broadcast & Verify", font=("Roboto", 20, "bold")).pack(anchor="w", pady=(10, 20))
        ctk.CTkLabel(parent, text="[Network actions placeholder]").pack()

    # --- LOGIC & ACTIONS ---

    def action_new_chain(self):
        # Pop up a dialog to ask for name
        dialog = ctk.CTkInputDialog(text="Enter name for new chain:", title="New Chain")
        name = dialog.get_input()
        if name:
            folder = self.data_manager.create_new_chain(name)
            self.refresh_chain_list()
            print(f"Created chain: {folder}")

    def refresh_chain_list(self):
        # Clear existing
        for item in self.tree_chains.get_children():
            self.tree_chains.delete(item)
        
        # Load from folder
        chains = self.data_manager.get_chains()
        for c in chains:
            self.tree_chains.insert("", "end", text=f" {c}", values=(c,))

    def on_chain_select(self, event):
        selected_item = self.tree_chains.selection()
        if not selected_item: return
        
        chain_folder = self.tree_chains.item(selected_item)['values'][0]
        
        # Clear blocks
        for item in self.tree_blocks.get_children():
            self.tree_blocks.delete(item)

        # Load blocks from backend
        blocks = self.data_manager.load_blocks(chain_folder)
        for b in blocks:
            # Visual logic: Green check if anchor, else ...
            status_icon = "✅" if b.get('is_anchor') else "⚪"
            display_hash = f"{b['index']:05d}_{b['block_hash'][:8]}..."
            self.tree_blocks.insert("", "end", values=(status_icon, display_hash))

    def open_settings_modal(self):
        # This would open a TopLevel window with config fields
        print("Settings clicked - Placeholder for Modal")

if __name__ == "__main__":
    app = ObscurityApp()
    app.mainloop()