import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import os

# --- CONFIGURATION ---
ctk.set_appearance_mode("Dark")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("dark-blue")  # Themes: "blue" (standard), "green", "dark-blue"

class ObscurityApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Setup
        self.title("Obscurity [Fork-Aware] // Modern UI")
        self.geometry("1300x850")

        # --- LAYOUT GRID ---
        # We need 3 main vertical columns.
        # Col 0: Chains (Left)
        # Col 1: Blocks (Mid)
        # Col 2: Factories (Right, main workspace)
        self.grid_columnconfigure(0, weight=0, minsize=220) # Chains
        self.grid_columnconfigure(1, weight=0, minsize=300) # Blocks
        self.grid_columnconfigure(2, weight=1)              # Factories
        self.grid_rowconfigure(0, weight=1)

        # --- COL 1: CHAINS SELECTOR ---
        self.frame_chains = ctk.CTkFrame(self, corner_radius=0)
        self.frame_chains.grid(row=0, column=0, sticky="nsew")
        self.build_chains_column()

        # --- COL 2: BLOCKS LIST ---
        self.frame_blocks = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a1a") # Slightly darker
        self.frame_blocks.grid(row=0, column=1, sticky="nsew")
        self.build_blocks_column()

        # --- COL 3: FACTORIES (RIGHT) ---
        self.frame_factories = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_factories.grid(row=0, column=2, sticky="nsew", padx=20, pady=20)
        self.build_factories_area()

        # --- HACK: STYLE THE LEGACY TREEVIEWS ---
        # CustomTkinter doesn't have a Treeview, so we style the standard one to fit Dark Mode
        self.style_legacy_widgets()

    def style_legacy_widgets(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Dark Treeview Colors
        bg_color = "#2b2b2b"
        fg_color = "#ffffff"
        hl_color = "#1f538d" # Selection color
        
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

    def build_chains_column(self):
        # Header
        lbl = ctk.CTkLabel(self.frame_chains, text="CHAINS / FORKS", font=("Roboto", 12, "bold"), text_color="#aaaaaa")
        lbl.pack(fill="x", pady=(15, 10), padx=10)
        
        # We wrap standard Treeview in a CTK frame for borders
        tree_frame = ctk.CTkFrame(self.frame_chains, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=0, pady=0)

        self.tree_chains = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        self.tree_chains.pack(side="left", fill="both", expand=True)
        
        # Custom Scrollbar
        sb = ctk.CTkScrollbar(tree_frame, command=self.tree_chains.yview, width=16)
        sb.pack(side="right", fill="y")
        self.tree_chains.configure(yscrollcommand=sb.set)
        
        # Data
        folder1 = self.tree_chains.insert("", "end", text=" Project Alpha (Main)", open=True)
        self.tree_chains.insert(folder1, "end", text=" ↳ Alpha - Fork A")
        self.tree_chains.insert(folder1, "end", text=" ↳ Alpha - Fork B (Orphaned)")
        folder2 = self.tree_chains.insert("", "end", text=" Project Satoshi", open=True)

        # Buttons
        btn_frame = ctk.CTkFrame(self.frame_chains, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", pady=10, padx=10)
        
        ctk.CTkButton(btn_frame, text="+ New Chain", height=35).pack(fill="x", pady=5)
        ctk.CTkButton(btn_frame, text="⑂ Clone Chain", height=35, fg_color="#2d2d2d", hover_color="#3a3a3a").pack(fill="x")

    def build_blocks_column(self):
        # Header
        lbl = ctk.CTkLabel(self.frame_blocks, text="BLOCK TIMELINE", font=("Roboto", 12, "bold"), text_color="#aaaaaa")
        lbl.pack(fill="x", pady=(15, 10), padx=10)

        # Container
        tree_frame = ctk.CTkFrame(self.frame_blocks, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True)

        columns = ("status", "hash")
        self.tree_blocks = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        
        self.tree_blocks.heading("status", text="St")
        self.tree_blocks.column("status", width=40, anchor="center")
        self.tree_blocks.heading("hash", text="Block Hash / ID")
        self.tree_blocks.column("hash", width=220)
        
        # Scrollbar
        sb = ctk.CTkScrollbar(tree_frame, command=self.tree_blocks.yview, width=16)
        sb.pack(side="right", fill="y")
        self.tree_blocks.configure(yscrollcommand=sb.set)
        self.tree_blocks.pack(side="left", fill="both", expand=True)

        # Data Logic (Top -> Down)
        self.tree_blocks.insert("", "end", values=("✅", "00000_Anchor"))
        self.tree_blocks.insert("", "end", values=("✅", "00001_DataBlock"))
        self.tree_blocks.insert("", "end", values=("✅", "00002_ImgPayload"))
        self.tree_blocks.insert("", "end", values=("❌", "00003_OrphanedFork"))
        self.tree_blocks.insert("", "end", values=("✅", "00003_CorrectChain"))
        self.tree_blocks.insert("", "end", values=("⏳", "00004_Draft (Local)"))
        self.tree_blocks.insert("", "end", values=("📝", "00005_New (Editing)"))

    def build_factories_area(self):
        # TabView (Modern Notebook)
        self.tabs = ctk.CTkTabview(self.frame_factories)
        self.tabs.pack(fill="both", expand=True)
        
        self.tabs.add("Payload Factory")
        self.tabs.add("Grind Factory")
        self.tabs.add("Network Factory")
        self.tabs.add("Config")

        # --- TAB 1: PAYLOAD ---
        self.build_tab_payload(self.tabs.tab("Payload Factory"))

        # --- TAB 2: GRIND ---
        self.build_tab_grind(self.tabs.tab("Grind Factory"))

        # --- TAB 4: CONFIG ---
        self.build_tab_config(self.tabs.tab("Config"))

    def build_tab_payload(self, parent):
        ctk.CTkLabel(parent, text="Step 1: Construct Block Data", font=("Roboto", 20, "bold")).pack(anchor="w", pady=(10, 20))
        
        # Example Buttons
        f_ex = ctk.CTkFrame(parent, fg_color="transparent")
        f_ex.pack(anchor="w", fill="x", pady=(0, 10))
        ctk.CTkLabel(f_ex, text="Load Example:", text_color="gray").pack(side="left", padx=(0, 10))
        ctk.CTkButton(f_ex, text="Hello World", height=24, width=80, fg_color="#333", hover_color="#444").pack(side="left", padx=5)
        ctk.CTkButton(f_ex, text="Small Image", height=24, width=80, fg_color="#333", hover_color="#444").pack(side="left", padx=5)
        
        # Main Text Input
        self.txt_payload = ctk.CTkTextbox(parent, font=("Consolas", 12))
        self.txt_payload.pack(fill="both", expand=True, pady=10)
        self.txt_payload.insert("0.0", "Enter your hex or text payload here...")

        # Action
        ctk.CTkButton(parent, text="COMPUTE HASH", height=50, font=("Roboto", 14, "bold"), fg_color="#1f538d").pack(fill="x", pady=10)

    def build_tab_grind(self, parent):
        ctk.CTkLabel(parent, text="Step 2: Generate Keys", font=("Roboto", 20, "bold")).pack(anchor="w", pady=(10, 20))
        
        # Config Area
        f_cfg = ctk.CTkFrame(parent)
        f_cfg.pack(fill="x", pady=10)
        
        ctk.CTkLabel(f_cfg, text="Difficulty (Bits per Key):").grid(row=0, column=0, padx=20, pady=20)
        slider = ctk.CTkSlider(f_cfg, from_=1, to=32, number_of_steps=31)
        slider.grid(row=0, column=1, padx=20, sticky="ew")
        slider.set(16) # Default to piggyback mode
        
        ctk.CTkLabel(f_cfg, text="(16 = Piggyback, 32 = Anchor)").grid(row=0, column=2, padx=20)

        # Big Start Button
        ctk.CTkButton(parent, text="▶ START GRINDER (xgrind)", height=60, font=("Roboto", 16, "bold"), fg_color="green", hover_color="darkgreen").pack(fill="x", pady=20)
        
        # Progress
        ctk.CTkProgressBar(parent).pack(fill="x", pady=10)
        ctk.CTkLabel(parent, text="Worker Status: Idle").pack()

    def build_tab_config(self, parent):
        ctk.CTkLabel(parent, text="Bitcoin Core Connection", font=("Roboto", 20, "bold")).pack(anchor="w", pady=(10, 20))
        
        # Grid Form
        f_form = ctk.CTkFrame(parent, fg_color="transparent")
        f_form.pack(fill="x", anchor="w")

        ctk.CTkLabel(f_form, text="RPC Host:").grid(row=0, column=0, sticky="w", pady=5)
        ctk.CTkEntry(f_form, width=300, placeholder_text="127.0.0.1").grid(row=0, column=1, padx=10)
        
        ctk.CTkLabel(f_form, text="RPC Port:").grid(row=1, column=0, sticky="w", pady=5)
        ctk.CTkEntry(f_form, width=100, placeholder_text="8332").grid(row=1, column=1, sticky="w", padx=10)

        ctk.CTkLabel(f_form, text="RPC User:").grid(row=2, column=0, sticky="w", pady=5)
        ctk.CTkEntry(f_form, width=300).grid(row=2, column=1, padx=10)

        ctk.CTkLabel(f_form, text="Data Dir:").grid(row=3, column=0, sticky="w", pady=5)
        
        # Windows Default
        default_path = os.path.join(os.getenv('APPDATA'), "Bitcoin") if os.name == 'nt' else "~/Library/Application Support/Bitcoin"
        e_dir = ctk.CTkEntry(f_form, width=400)
        e_dir.grid(row=3, column=1, padx=10, pady=5)
        e_dir.insert(0, default_path)
        
        ctk.CTkButton(f_form, text="Test Connection", width=200).grid(row=4, column=1, sticky="w", padx=10, pady=20)

if __name__ == "__main__":
    app = ObscurityApp()
    app.mainloop()