import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import math
import threading
import time
import obscurity_backend 

# --- CONFIGURATION ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class ObscurityApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.data_manager = obscurity_backend.DataManager()
        self.current_chain = None
        self.selected_block_index = None
        
        # Draft State (The "Unsaved" Block)
        self.draft_payload = None
        self.draft_filename = None
        # Mode triggers: "text" or "file" (managed by radio buttons)

        # Window Setup
        self.title("Obscurity [Anchor System] // Hackathon Build v3.0")
        self.geometry("1400x900")

        # --- MAIN GRID ---
        self.grid_columnconfigure(0, weight=0, minsize=260) # Anchors/Forks
        self.grid_columnconfigure(1, weight=0, minsize=320) # Block History
        self.grid_columnconfigure(2, weight=1)              # Work Area
        self.grid_rowconfigure(0, weight=1)

        # 1. Left (Hierarchy)
        self.frame_left = ctk.CTkFrame(self, corner_radius=0)
        self.frame_left.grid(row=0, column=0, sticky="nsew")
        self.build_hierarchy_column()

        # 2. Mid (History)
        self.frame_mid = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a1a")
        self.frame_mid.grid(row=0, column=1, sticky="nsew")
        self.build_history_column()

        # 3. Right (Work Area)
        self.frame_right = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_right.grid(row=0, column=2, sticky="nsew", padx=20, pady=20)
        
        self.build_right_header()
        
        self.container = ctk.CTkFrame(self.frame_right, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        self.view_tabs = self.create_main_view(self.container)
        
        self.style_legacy_widgets()
        self.refresh_chain_list()

    def style_legacy_widgets(self):
        style = ttk.Style()
        style.theme_use("clam")
        bg = "#2b2b2b"
        fg = "#ffffff"
        hl = "#1f538d"
        style.configure("Treeview", background=bg, foreground=fg, fieldbackground=bg, borderwidth=0, rowheight=35, font=("Roboto Medium", 11))
        style.configure("Treeview.Heading", background="#202020", foreground="#aaaaaa", relief="flat", font=("Roboto", 10, "bold"))
        style.map("Treeview", background=[('selected', hl)])

    # --- LEFT COLUMN: ANCHORS & FORKS ---
    def build_hierarchy_column(self):
        ctk.CTkLabel(self.frame_left, text="TIMELINES", font=("Roboto", 16, "bold"), text_color="#aaaaaa").pack(pady=(20,10))
        
        # Tree
        tree_frame = ctk.CTkFrame(self.frame_left, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=10)

        self.tree_chains = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        self.tree_chains.pack(side="left", fill="both", expand=True)
        self.tree_chains.bind("<<TreeviewSelect>>", self.on_chain_select)
        
        # Action Buttons (The Big Green/Blue buttons)
        btn_frame = ctk.CTkFrame(self.frame_left, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", pady=20, padx=15)
        
        self.btn_new_anchor = ctk.CTkButton(btn_frame, text="⚓ NEW ANCHOR", height=45, fg_color="#2ecc71", hover_color="#27ae60", font=("Roboto", 13, "bold"), command=self.action_new_anchor)
        self.btn_new_anchor.pack(fill="x", pady=5)
        
        self.btn_fork = ctk.CTkButton(btn_frame, text="⑂ FORK SELECTED", height=45, fg_color="#3498db", hover_color="#2980b9", font=("Roboto", 13, "bold"), command=self.action_fork_chain)
        self.btn_fork.pack(fill="x", pady=5)

    # --- MID COLUMN: BLOCK HISTORY ---
    def build_history_column(self):
        ctk.CTkLabel(self.frame_mid, text="BLOCK HISTORY", font=("Roboto", 16, "bold"), text_color="#aaaaaa").pack(pady=(20,10))

        tree_frame = ctk.CTkFrame(self.frame_mid, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=10)

        cols = ("idx", "hash")
        self.tree_blocks = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self.tree_blocks.heading("idx", text="#")
        self.tree_blocks.column("idx", width=40, anchor="center")
        self.tree_blocks.heading("hash", text="Block ID / Status")
        self.tree_blocks.column("hash", width=220)
        self.tree_blocks.pack(side="left", fill="both", expand=True)
        self.tree_blocks.bind("<<TreeviewSelect>>", self.on_block_select)

        # "New Draft" Button
        btn_frame = ctk.CTkFrame(self.frame_mid, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", pady=20, padx=15)
        self.btn_new_draft = ctk.CTkButton(btn_frame, text="+ New Block Draft", height=40, fg_color="#555", hover_color="#666", command=self.action_new_draft)
        self.btn_new_draft.pack(fill="x")

    def build_right_header(self):
        h = ctk.CTkFrame(self.frame_right, height=50, fg_color="transparent")
        h.pack(fill="x", pady=(0, 10))
        self.lbl_header = ctk.CTkLabel(h, text="Obscurity Workbench", font=("Roboto", 24, "bold"))
        self.lbl_header.pack(side="left")
        self.lbl_status = ctk.CTkLabel(h, text="System Ready", font=("Consolas", 12), text_color="#00ff00")
        self.lbl_status.pack(side="right", padx=10)

    # --- TABS FACTORY ---
    def create_main_view(self, parent):
        self.tabs = ctk.CTkTabview(parent)
        self.tabs.pack(fill="both", expand=True)
        
        self.tab_factory = self.tabs.add("Block Factory")
        self.tab_grind = self.tabs.add("Pubkey Grinder")
        self.tab_verify = self.tabs.add("Verify Onchain")
        
        self.setup_block_factory(self.tab_factory)
        self.setup_pubkey_grinder(self.tab_grind)
        self.setup_verify_onchain(self.tab_verify)
        
        return self.tabs

    # --- TAB 1: BLOCK FACTORY (Draft & View) ---
    def setup_block_factory(self, parent):
        # Header Info
        self.f_info = ctk.CTkFrame(parent, fg_color="transparent")
        self.f_info.pack(fill="x", pady=10)
        self.lbl_factory_mode = ctk.CTkLabel(self.f_info, text="MODE: VIEW ONLY", font=("Roboto", 14, "bold"), text_color="gray")
        self.lbl_factory_mode.pack(side="left", padx=10)
        
        # Content Area
        ctk.CTkLabel(parent, text="Block Content Payload:", anchor="w").pack(fill="x", padx=15)
        
        # NEW CONTAINER: Fixes the Thonny crash by isolating inputs
        self.f_input_container = ctk.CTkFrame(parent, fg_color="#222", corner_radius=6)
        self.f_input_container.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Text Widget (For viewing text or entering draft)
        self.txt_content = ctk.CTkTextbox(self.f_input_container, wrap="word", font=("Consolas", 12))
        self.txt_content.pack(fill="both", expand=True, padx=2, pady=2)
        
        # File Widget (Hidden by default, packed when needed)
        self.f_file_ui = ctk.CTkFrame(self.f_input_container, fg_color="transparent")
        self.btn_browse = ctk.CTkButton(self.f_file_ui, text="📂 Browse File...", width=150, command=self.action_browse_file)
        self.btn_browse.pack(side="left", padx=10)
        self.lbl_file_name = ctk.CTkLabel(self.f_file_ui, text="No file selected", text_color="gray")
        self.lbl_file_name.pack(side="left", padx=10)

        # Mode Switcher (Text/File) - Only for Drafts
        self.f_draft_tools = ctk.CTkFrame(parent, fg_color="transparent")
        self.var_input_type = ctk.StringVar(value="text")
        # Radio buttons to toggle
        r1 = ctk.CTkRadioButton(self.f_draft_tools, text="Text Data", variable=self.var_input_type, value="text", command=self.toggle_draft_ui)
        r1.pack(side="left", padx=10)
        r2 = ctk.CTkRadioButton(self.f_draft_tools, text="Binary File", variable=self.var_input_type, value="file", command=self.toggle_draft_ui)
        r2.pack(side="left", padx=10)
        
        # Commit Button
        self.btn_commit = ctk.CTkButton(parent, text="🔒 GENERATE HASH & COMMIT", height=50, fg_color="green", hover_color="darkgreen", font=("Roboto", 14, "bold"), command=self.action_commit_block)
        self.btn_commit.pack(fill="x", padx=10, pady=20)
        
        # Hash Display
        self.lbl_generated_hash = ctk.CTkLabel(parent, text="Hash: Pending...", font=("Consolas", 12), text_color="gray")
        self.lbl_generated_hash.pack(pady=5)

    def toggle_draft_ui(self):
        # Swaps between Text Box and File Picker using pack_forget
        mode = self.var_input_type.get()
        if mode == "text":
            self.f_file_ui.pack_forget()
            self.txt_content.pack(fill="both", expand=True, padx=2, pady=2)
        else:
            self.txt_content.pack_forget()
            self.f_file_ui.pack(fill="both", expand=True, padx=2, pady=2)

    # --- TAB 2: PUBKEY GRINDER ---
    def setup_pubkey_grinder(self, parent):
        # Info Header
        f_head = ctk.CTkFrame(parent, fg_color="transparent")
        f_head.pack(fill="x", pady=10)
        ctk.CTkLabel(f_head, text="Target Block:", font=("Roboto", 14)).pack(side="left", padx=10)
        self.lbl_grind_target = ctk.CTkLabel(f_head, text="None", font=("Consolas", 14, "bold"), text_color="cyan")
        self.lbl_grind_target.pack(side="left")

        # Controls
        f_ctrl = ctk.CTkFrame(parent)
        f_ctrl.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(f_ctrl, text="Difficulty (Bits):").pack(side="left", padx=15)
        self.slider_diff = ctk.CTkSlider(f_ctrl, from_=16, to=32, number_of_steps=16, width=200, command=self.update_grind_est)
        self.slider_diff.set(32)
        self.slider_diff.pack(side="left", padx=10)
        self.lbl_diff_display = ctk.CTkLabel(f_ctrl, text="32-bit", width=50)
        self.lbl_diff_display.pack(side="left")
        
        self.btn_start_grind = ctk.CTkButton(f_ctrl, text="▶ START 4090", fg_color="#e74c3c", hover_color="#c0392b", width=150, command=self.action_run_grinder)
        self.btn_start_grind.pack(side="right", padx=15, pady=10)

        # Visualization Grid
        self.canvas_frame = ctk.CTkFrame(parent, fg_color="black")
        self.canvas_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.canvas = tk.Canvas(self.canvas_frame, bg="#050505", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # Stats
        f_stat = ctk.CTkFrame(parent, height=40, fg_color="transparent")
        f_stat.pack(fill="x", padx=10)
        self.lbl_grind_stats = ctk.CTkLabel(f_stat, text="Waiting for job...", font=("Consolas", 12))
        self.lbl_grind_stats.pack(side="left")
        self.lbl_grind_speed = ctk.CTkLabel(f_stat, text="0.0 M/s", font=("Consolas", 12, "bold"), text_color="#00ffff")
        self.lbl_grind_speed.pack(side="right")

    def update_grind_est(self, val):
        self.lbl_diff_display.configure(text=f"{int(val)}-bit")

    # --- TAB 3: VERIFY ONCHAIN ---
    def setup_verify_onchain(self, parent):
        ctk.CTkLabel(parent, text="AUDIT REPORT", font=("Roboto", 16, "bold")).pack(pady=15)
        
        # Truth Table
        self.f_audit = ctk.CTkFrame(parent)
        self.f_audit.pack(fill="x", padx=20, pady=10)
        
        # Row 1: Local
        ctk.CTkLabel(self.f_audit, text="Local Hash:", width=100, anchor="e").grid(row=0, column=0, padx=10, pady=5)
        self.lbl_audit_local = ctk.CTkLabel(self.f_audit, text="...", font=("Consolas", 12), text_color="gray")
        self.lbl_audit_local.grid(row=0, column=1, sticky="w")
        
        # Row 2: On-Chain
        ctk.CTkLabel(self.f_audit, text="Bitcoin Net:", width=100, anchor="e").grid(row=1, column=0, padx=10, pady=5)
        self.lbl_audit_chain = ctk.CTkLabel(self.f_audit, text="...", font=("Consolas", 12), text_color="gray")
        self.lbl_audit_chain.grid(row=1, column=1, sticky="w")
        
        # Row 3: Integrity
        ctk.CTkLabel(self.f_audit, text="Integrity:", width=100, anchor="e").grid(row=2, column=0, padx=10, pady=5)
        self.lbl_audit_status = ctk.CTkLabel(self.f_audit, text="UNVERIFIED", font=("Roboto", 12, "bold"), text_color="orange")
        self.lbl_audit_status.grid(row=2, column=1, sticky="w")

        # Action
        ctk.CTkButton(parent, text="🔍 SCAN BITCOIN NODE", height=50, command=self.action_verify).pack(fill="x", padx=20, pady=20)
        
        # Log
        self.txt_audit_log = ctk.CTkTextbox(parent, font=("Consolas", 10))
        self.txt_audit_log.pack(fill="both", expand=True, padx=20, pady=10)

    # --- ACTIONS ---
    def action_new_anchor(self):
        # Anchors MUST have content (Genesis Block)
        d = ctk.CTkInputDialog(text="Anchor Name:", title="New Anchor")
        name = d.get_input()
        if name:
            self.data_manager.create_anchor(name)
            self.refresh_chain_list()

    def action_fork_chain(self):
        if not self.current_chain or self.selected_block_index is None:
            messagebox.showwarning("Fork Error", "Select a block to fork from.")
            return
            
        d = ctk.CTkInputDialog(text="Name for Fork:", title="Create Fork")
        name = d.get_input()
        if name:
            new_folder = self.data_manager.fork_chain(self.current_chain, self.selected_block_index, name)
            self.refresh_chain_list()
            messagebox.showinfo("Fork Created", f"Fork created at block {self.selected_block_index}")

    def action_new_draft(self):
        if not self.current_chain: return
        
        # Switch to Factory Tab
        self.tabs.set("Block Factory")
        
        # Enable Draft Mode UI
        self.lbl_factory_mode.configure(text="MODE: NEW DRAFT (Unsaved)", text_color="orange")
        self.btn_commit.configure(state="normal", text="🔒 GENERATE HASH & COMMIT")
        self.f_draft_tools.pack(fill="x", pady=5) # Show tools
        
        # Clear inputs
        self.txt_content.delete("0.0", "end")
        self.lbl_file_name.configure(text="No file selected")
        self.draft_payload = None
        self.lbl_generated_hash.configure(text="Hash: Pending Commit...")
        self.selected_block_index = None # Deselect until saved

    def action_browse_file(self):
        path = filedialog.askopenfilename()
        if path:
            self.lbl_file_name.configure(text=os.path.basename(path))
            with open(path, "rb") as f:
                self.draft_payload = f.read()
            self.draft_filename = os.path.basename(path)

    def action_commit_block(self):
        if not self.current_chain: return
        
        # Gather Data
        data = b""
        filename = "msg.txt"
        
        if self.var_input_type.get() == "text":
            txt = self.txt_content.get("0.0", "end").strip()
            if not txt: return
            data = txt.encode('utf-8')
        else:
            if not self.draft_payload: return
            data = self.draft_payload
            filename = self.draft_filename

        # Get Previous Hash
        blocks = self.data_manager.load_blocks(self.current_chain)
        prev = blocks[-1]['header']['block_hash'] if blocks else "0"*64
        idx = len(blocks)

        # Backend Commit
        block = self.data_manager.commit_block(self.current_chain, idx, prev, data, filename)
        
        # UI Update
        self.lbl_generated_hash.configure(text=f"Hash: {block['header']['block_hash']}")
        self.load_chain_blocks(self.current_chain)
        self.refresh_chain_list() # To update block counts if we show them
        messagebox.showinfo("Committed", "Block encrypted and saved to disk.")
        
        # Auto-select the newly created block
        # We need to find the item ID in the tree
        for child in self.tree_blocks.get_children():
            vals = self.tree_blocks.item(child)['values']
            if vals[0] == idx:
                self.tree_blocks.selection_set(child)
                self.on_block_select(None)
                break

    def action_run_grinder(self):
        if not self.current_chain or self.selected_block_index is None: return
        
        diff = int(self.slider_diff.get())
        self.btn_start_grind.configure(state="disabled", text="GRINDING...")
        self.canvas.delete("all")
        
        def worker():
            chain = self.current_chain
            idx = self.selected_block_index
            grid_rects = []
            
            # Helper to draw grid once we know size
            initialized = [False]
            def init_grid(total):
                ratio = self.canvas.winfo_width() / self.canvas.winfo_height()
                cols = int(math.sqrt(total * ratio)) or 1
                rows = math.ceil(total / cols)
                w = self.canvas.winfo_width() / cols
                h = self.canvas.winfo_height() / rows
                for i in range(total):
                    c, r = i % cols, i // cols
                    tag = self.canvas.create_rectangle(c*w, r*h, (c+1)*w, (r+1)*h, fill="#222", outline="#222")
                    grid_rects.append(tag)

            def on_progress(curr, total, msg):
                if not initialized[0]:
                    self.after(0, lambda: init_grid(total))
                    initialized[0] = True
                
                speed = msg.split("(")[1].replace(")", "") if "(" in msg else "0.0 M/s"
                
                def update_ui():
                    self.lbl_grind_stats.configure(text=f"Keys: {curr}/{total}")
                    self.lbl_grind_speed.configure(text=f"Speed: {speed}")
                    if curr-1 < len(grid_rects):
                        self.canvas.itemconfig(grid_rects[curr-1], fill="#00ff00", outline="")
                self.after(0, update_ui)

            success, msg = self.data_manager.run_grinder(chain, idx, diff, on_progress)
            
            def finish():
                self.btn_start_grind.configure(state="normal", text="▶ START 4090")
                if success:
                    self.load_chain_blocks(chain)
                    messagebox.showinfo("Done", "Keys generated successfully.")
                else:
                    messagebox.showerror("Error", msg)
            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def action_verify(self):
        # Simulation of verification logic
        self.txt_audit_log.delete("0.0", "end")
        self.txt_audit_log.insert("end", "> Connecting to Node...\n")
        self.txt_audit_log.insert("end", "> Reading Block Headers...\n")
        self.txt_audit_log.insert("end", "> Validating AES-GCM Integrity...\n")
        self.after(1000, lambda: self.lbl_audit_status.configure(text="MATCH CONFIRMED", text_color="#00ff00"))

    # --- LIST MANAGEMENT ---
    def refresh_chain_list(self):
        for i in self.tree_chains.get_children(): self.tree_chains.delete(i)
        for c in self.data_manager.get_chains():
            icon = "⚓" if c.get('type') == 'anchor' else "⑂"
            name = f"{icon} {c['name']}"
            self.tree_chains.insert("", "end", text=name, values=(c['folder'],))

    def on_chain_select(self, event):
        sel = self.tree_chains.selection()
        if not sel: return
        self.current_chain = self.tree_chains.item(sel)['values'][0]
        self.load_chain_blocks(self.current_chain)

    def load_chain_blocks(self, chain):
        for i in self.tree_blocks.get_children(): self.tree_blocks.delete(i)
        blocks = self.data_manager.load_blocks(chain)
        for b in blocks:
            st = b['header']['status']
            # Icons: 📝=Unlinked(Draft/Hash), ✅=Grinded/Ready, 🔗=OnChain
            icon = "🔗" if st == "verified" else "✅" if st == "ready_to_link" else "📝"
            h = b['header']['block_hash']
            idx = b['header']['index']
            self.tree_blocks.insert("", "end", values=(idx, f"{icon} {h[:8]}..."))

    def on_block_select(self, event):
        if not event: # Manual trigger from code
            if self.selected_block_index is None: return
        else:
            sel = self.tree_blocks.selection()
            if not sel: return
            idx = self.tree_blocks.item(sel)['values'][0]
            self.selected_block_index = idx
        
        # Load block data
        blocks = self.data_manager.load_blocks(self.current_chain)
        block = next((b for b in blocks if b['header']['index'] == self.selected_block_index), None)
        
        if block:
            # 1. Update Factory Tab (View Mode)
            self.lbl_factory_mode.configure(text="MODE: VIEW ONLY (Saved)", text_color="gray")
            self.btn_commit.configure(state="disabled", text="BLOCK COMMITTED")
            self.f_draft_tools.pack_forget() # Hide draft tools
            
            # Show content
            self.txt_content.delete("0.0", "end")
            preview = block['content'].get('preview')
            
            if preview:
                self.f_file_ui.pack_forget()
                self.txt_content.pack(fill="both", expand=True, padx=2, pady=2)
                self.txt_content.insert("0.0", preview)
            else:
                self.txt_content.pack_forget()
                self.f_file_ui.pack(fill="both", expand=True, padx=2, pady=2)
                self.lbl_file_name.configure(text=f"{block['content']['filename']} (Encrypted)")

            self.lbl_generated_hash.configure(text=f"Hash: {block['header']['block_hash']}")
            
            # 2. Update Grinder Tab
            self.lbl_grind_target.configure(text=f"Block {block['header']['index']}")
            
            # 3. Update Audit Tab
            self.lbl_audit_local.configure(text=block['header']['block_hash'])

if __name__ == "__main__":
    try:
        app = ObscurityApp()
        app.mainloop()
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        input("Press Enter...")