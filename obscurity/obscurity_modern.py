import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import math
import threading
import time
import hashlib  # <--- FIXED: Added missing import
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
        
        # Draft State
        self.draft_payload = None
        self.draft_filename = None
        
        # Window Setup
        self.title("Obscurity [Anchor System] // Hackathon Build v3.0")
        self.geometry("1100x750")
        self.center_window(1100, 750)
        
        # Safe Exit Handling
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # --- MAIN GRID ---
        self.grid_columnconfigure(0, weight=0, minsize=240) # Anchors
        self.grid_columnconfigure(1, weight=0, minsize=280) # History
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

        # 3. Right (Work Area - Scrollable)
        self.frame_right = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_right.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)
        
        self.build_right_header()
        
        self.container = ctk.CTkFrame(self.frame_right, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        self.view_tabs = self.create_main_view(self.container)
        
        self.style_legacy_widgets()
        self.refresh_chain_list()

    def on_closing(self):
        # Clean shutdown logic
        self.destroy()
        os._exit(0)

    def center_window(self, width, height):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width / 2) - (width / 2)
        y = (screen_height / 2) - (height / 2)
        self.geometry(f'{width}x{height}+{int(x)}+{int(y)}')

    def style_legacy_widgets(self):
        style = ttk.Style()
        style.theme_use("clam")
        bg = "#2b2b2b"
        fg = "#ffffff"
        hl = "#1f538d"
        style.configure("Treeview", background=bg, foreground=fg, fieldbackground=bg, borderwidth=0, rowheight=30, font=("Roboto Medium", 10))
        style.configure("Treeview.Heading", background="#202020", foreground="#aaaaaa", relief="flat", font=("Roboto", 9, "bold"))
        style.map("Treeview", background=[('selected', hl)])

    # --- LEFT COLUMN ---
    def build_hierarchy_column(self):
        ctk.CTkLabel(self.frame_left, text="TIMELINES", font=("Roboto", 14, "bold"), text_color="#aaaaaa").pack(pady=(15,5))
        
        tree_frame = ctk.CTkFrame(self.frame_left, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=5)

        self.tree_chains = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        self.tree_chains.pack(side="left", fill="both", expand=True)
        self.tree_chains.bind("<<TreeviewSelect>>", self.on_chain_select)
        
        btn_frame = ctk.CTkFrame(self.frame_left, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", pady=15, padx=10)
        
        self.btn_new_anchor = ctk.CTkButton(btn_frame, text="⚓ NEW ANCHOR", height=40, fg_color="#2ecc71", hover_color="#27ae60", command=self.action_new_anchor)
        self.btn_new_anchor.pack(fill="x", pady=4)
        
        self.btn_fork = ctk.CTkButton(btn_frame, text="⑂ FORK SELECTED", height=40, fg_color="#3498db", hover_color="#2980b9", command=self.action_fork_chain)
        self.btn_fork.pack(fill="x", pady=4)

    # --- MID COLUMN ---
    def build_history_column(self):
        ctk.CTkLabel(self.frame_mid, text="BLOCK HISTORY", font=("Roboto", 14, "bold"), text_color="#aaaaaa").pack(pady=(15,5))

        tree_frame = ctk.CTkFrame(self.frame_mid, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=5)

        cols = ("idx", "hash")
        self.tree_blocks = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self.tree_blocks.heading("idx", text="#")
        self.tree_blocks.column("idx", width=35, anchor="center")
        self.tree_blocks.heading("hash", text="Block ID / Status")
        self.tree_blocks.column("hash", width=180)
        self.tree_blocks.pack(side="left", fill="both", expand=True)
        self.tree_blocks.bind("<<TreeviewSelect>>", self.on_block_select)

        btn_frame = ctk.CTkFrame(self.frame_mid, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", pady=15, padx=10)
        self.btn_new_draft = ctk.CTkButton(btn_frame, text="+ New Block Draft", height=35, fg_color="#555", hover_color="#666", command=self.action_new_draft)
        self.btn_new_draft.pack(fill="x")

    def build_right_header(self):
        h = ctk.CTkFrame(self.frame_right, height=45, fg_color="transparent")
        h.pack(fill="x", pady=(0, 5))
        self.lbl_header = ctk.CTkLabel(h, text="Obscurity Workbench", font=("Roboto", 20, "bold"))
        self.lbl_header.pack(side="left")
        self.lbl_status = ctk.CTkLabel(h, text="System Ready", font=("Consolas", 11), text_color="#00ff00")
        self.lbl_status.pack(side="right", padx=10)

    # --- TABS ---
    def create_main_view(self, parent):
        self.tabs = ctk.CTkTabview(parent)
        self.tabs.pack(fill="both", expand=True)
        
        self.tab_maker = self.tabs.add("Block Maker")
        self.tab_grind = self.tabs.add("Pubkey Grinder")
        self.tab_verify = self.tabs.add("Verify Onchain")
        
        self.setup_block_maker(self.tab_maker)
        self.setup_pubkey_grinder(self.tab_grind)
        self.setup_verify_onchain(self.tab_verify)
        
        return self.tabs

    # --- TAB 1: BLOCK MAKER ---
    def setup_block_maker(self, parent):
        self.f_info = ctk.CTkFrame(parent, fg_color="transparent")
        self.f_info.pack(fill="x", pady=5)
        self.lbl_factory_mode = ctk.CTkLabel(self.f_info, text="MODE: VIEW ONLY", font=("Roboto", 12, "bold"), text_color="gray")
        self.lbl_factory_mode.pack(side="left", padx=5)
        
        # Content Container
        ctk.CTkLabel(parent, text="Payload Content:", anchor="w", font=("Roboto", 12)).pack(fill="x", padx=5)
        
        self.f_input_container = ctk.CTkFrame(parent, fg_color="#181818", corner_radius=6)
        self.f_input_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Text Input
        self.txt_content = ctk.CTkTextbox(self.f_input_container, wrap="word", font=("Consolas", 11))
        self.txt_content.pack(fill="both", expand=True, padx=2, pady=2)
        
        # File Input
        self.f_file_ui = ctk.CTkFrame(self.f_input_container, fg_color="transparent")
        self.btn_browse = ctk.CTkButton(self.f_file_ui, text="📂 Browse File...", width=140, command=self.action_browse_file)
        self.btn_browse.pack(side="left", padx=10)
        self.lbl_file_name = ctk.CTkLabel(self.f_file_ui, text="No file selected", text_color="gray")
        self.lbl_file_name.pack(side="left", padx=10)

        # Tools
        self.f_draft_tools = ctk.CTkFrame(parent, fg_color="transparent")
        self.var_input_type = ctk.StringVar(value="text")
        ctk.CTkRadioButton(self.f_draft_tools, text="Text", variable=self.var_input_type, value="text", command=self.toggle_draft_ui).pack(side="left", padx=10)
        ctk.CTkRadioButton(self.f_draft_tools, text="File", variable=self.var_input_type, value="file", command=self.toggle_draft_ui).pack(side="left", padx=10)
        
        self.btn_commit = ctk.CTkButton(parent, text="🔒 GENERATE HASH & COMMIT", height=45, fg_color="green", hover_color="darkgreen", font=("Roboto", 13, "bold"), command=self.action_commit_block)
        self.btn_commit.pack(fill="x", padx=10, pady=15)
        
        self.lbl_generated_hash = ctk.CTkLabel(parent, text="Hash: Pending...", font=("Consolas", 11), text_color="gray")
        self.lbl_generated_hash.pack(pady=5)

    def toggle_draft_ui(self):
        if self.var_input_type.get() == "text":
            self.f_file_ui.pack_forget()
            self.txt_content.pack(fill="both", expand=True, padx=2, pady=2)
        else:
            self.txt_content.pack_forget()
            self.f_file_ui.pack(fill="both", expand=True, padx=2, pady=2)

    # --- TAB 2: PUBKEY GRINDER ---
    def setup_pubkey_grinder(self, parent):
        # Target Info
        f_head = ctk.CTkFrame(parent, fg_color="#222")
        f_head.pack(fill="x", pady=10, padx=10)
        self.lbl_grind_target = ctk.CTkLabel(f_head, text="Target Payload Hash: [Waiting]", font=("Consolas", 12), text_color="cyan")
        self.lbl_grind_target.pack(padx=10, pady=5)

        # Inputs (Salt/Password) for Transparency
        f_inputs = ctk.CTkFrame(parent)
        f_inputs.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(f_inputs, text="Encryption Key Hint:", width=120).grid(row=0, column=0, padx=5, pady=5)
        self.entry_grind_key = ctk.CTkEntry(f_inputs, placeholder_text="Auto-filled from block")
        self.entry_grind_key.grid(row=0, column=1, sticky="ew", padx=5)
        
        ctk.CTkLabel(f_inputs, text="Salt / IV:", width=120).grid(row=1, column=0, padx=5, pady=5)
        self.entry_grind_iv = ctk.CTkEntry(f_inputs, placeholder_text="Auto-filled from block")
        self.entry_grind_iv.grid(row=1, column=1, sticky="ew", padx=5)
        f_inputs.grid_columnconfigure(1, weight=1)

        # Difficulty
        f_ctrl = ctk.CTkFrame(parent, fg_color="transparent")
        f_ctrl.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(f_ctrl, text="Difficulty (Bits):").pack(side="left", padx=5)
        self.slider_diff = ctk.CTkSlider(f_ctrl, from_=16, to=32, number_of_steps=16, width=150, command=lambda v: self.lbl_diff_display.configure(text=f"{int(v)}-bit"))
        self.slider_diff.set(32)
        self.slider_diff.pack(side="left", padx=10)
        self.lbl_diff_display = ctk.CTkLabel(f_ctrl, text="32-bit", width=40)
        self.lbl_diff_display.pack(side="left")

        # The Button
        self.btn_start_grind = ctk.CTkButton(parent, text="Start Grinding Spendable Pubkeys", height=45, fg_color="#e74c3c", hover_color="#c0392b", font=("Roboto", 13, "bold"), command=self.action_run_grinder)
        self.btn_start_grind.pack(fill="x", padx=20, pady=10)

        # Grid
        self.canvas_frame = ctk.CTkFrame(parent, fg_color="black")
        self.canvas_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.canvas = tk.Canvas(self.canvas_frame, bg="#050505", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # Stats
        self.lbl_grind_stats = ctk.CTkLabel(parent, text="Ready", font=("Consolas", 11))
        self.lbl_grind_stats.pack(side="left", padx=10, pady=5)

    # --- TAB 3: VERIFY ONCHAIN ---
    def setup_verify_onchain(self, parent):
        # 1. Inputs
        ctk.CTkLabel(parent, text="Step 1: Input Chain Data", font=("Roboto", 12, "bold")).pack(anchor="w", padx=20, pady=(15,5))
        
        f_form = ctk.CTkFrame(parent)
        f_form.pack(fill="x", padx=20)
        
        ctk.CTkLabel(f_form, text="Transaction ID:", width=100, anchor="e").grid(row=0, column=0, padx=10, pady=5)
        self.entry_verify_txid = ctk.CTkEntry(f_form, placeholder_text="Paste TXID here")
        self.entry_verify_txid.grid(row=0, column=1, sticky="ew", padx=10, pady=5)
        
        ctk.CTkLabel(f_form, text="Decryption Key:", width=100, anchor="e").grid(row=1, column=0, padx=10, pady=5)
        self.entry_verify_key = ctk.CTkEntry(f_form)
        self.entry_verify_key.grid(row=1, column=1, sticky="ew", padx=10, pady=5)

        ctk.CTkLabel(f_form, text="Salt / IV:", width=100, anchor="e").grid(row=2, column=0, padx=10, pady=5)
        self.entry_verify_iv = ctk.CTkEntry(f_form)
        self.entry_verify_iv.grid(row=2, column=1, sticky="ew", padx=10, pady=5)
        f_form.grid_columnconfigure(1, weight=1)

        # 2. Action
        self.btn_verify = ctk.CTkButton(parent, text="CONNECT NODE & VERIFY (STRICT 1:1)", height=45, fg_color="#f39c12", hover_color="#d35400", command=self.action_verify)
        self.btn_verify.pack(fill="x", padx=40, pady=20)

        # 3. Log
        ctk.CTkLabel(parent, text="Verification Log:", anchor="w").pack(fill="x", padx=20)
        self.txt_audit_log = ctk.CTkTextbox(parent, font=("Consolas", 10), height=150)
        self.txt_audit_log.pack(fill="both", expand=True, padx=20, pady=10)

    # --- ACTIONS ---
    def action_new_anchor(self):
        d = ctk.CTkInputDialog(text="Anchor Name:", title="New Anchor")
        name = d.get_input()
        if name:
            self.data_manager.create_anchor(name)
            self.refresh_chain_list()

    def action_fork_chain(self):
        if not self.current_chain or self.selected_block_index is None:
            messagebox.showwarning("Error", "Select a block to fork from.")
            return
        d = ctk.CTkInputDialog(text="Fork Name:", title="Create Fork")
        name = d.get_input()
        if name:
            self.data_manager.fork_chain(self.current_chain, self.selected_block_index, name)
            self.refresh_chain_list()

    def action_new_draft(self):
        if not self.current_chain: return
        self.tabs.set("Block Maker")
        
        self.lbl_factory_mode.configure(text="MODE: NEW DRAFT (Unsaved)", text_color="orange")
        self.btn_commit.configure(state="normal", text="🔒 GENERATE HASH & COMMIT")
        self.f_draft_tools.pack(fill="x", pady=5)
        
        self.txt_content.delete("0.0", "end")
        self.lbl_file_name.configure(text="No file selected")
        self.draft_payload = None
        self.lbl_generated_hash.configure(text="Hash: Pending...")
        self.selected_block_index = None

    def action_browse_file(self):
        path = filedialog.askopenfilename()
        if path:
            self.lbl_file_name.configure(text=os.path.basename(path))
            with open(path, "rb") as f:
                self.draft_payload = f.read()
            self.draft_filename = os.path.basename(path)
            # Safe Preview for Large Files
            preview_len = 512
            if len(self.draft_payload) > preview_len:
                self.toggle_draft_ui() # switch to text view to show truncation msg
                self.txt_content.insert("0.0", f"[PREVIEW TRUNCATED] First {preview_len} bytes:\n\n" + str(self.draft_payload[:preview_len]))
            self.toggle_draft_ui()

    def action_commit_block(self):
        if not self.current_chain: return
        
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

        blocks = self.data_manager.load_blocks(self.current_chain)
        prev = blocks[-1]['header']['block_hash'] if blocks else "0"*64
        idx = len(blocks)

        block = self.data_manager.commit_block(self.current_chain, idx, prev, data, filename)
        
        self.lbl_generated_hash.configure(text=f"Hash: {block['header']['block_hash']}")
        self.load_chain_blocks(self.current_chain)
        self.on_block_select(None) # Refresh to view mode
        messagebox.showinfo("Success", "Block committed to disk.")

    def action_run_grinder(self):
        if not self.current_chain or self.selected_block_index is None: return
        
        diff = int(self.slider_diff.get())
        self.btn_start_grind.configure(state="disabled", text="GRINDING...")
        self.canvas.delete("all")
        
        def worker():
            chain = self.current_chain
            idx = self.selected_block_index
            
            # Grid Setup
            grid_rects = []
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
                
                def update_ui():
                    self.lbl_grind_stats.configure(text=msg)
                    if curr-1 < len(grid_rects):
                        self.canvas.itemconfig(grid_rects[curr-1], fill="#00ff00", outline="")
                self.after(0, update_ui)

            success, msg = self.data_manager.run_grinder(chain, idx, diff, on_progress)
            
            def finish():
                self.btn_start_grind.configure(state="normal", text="Start Grinding Spendable Pubkeys")
                if success:
                    self.load_chain_blocks(chain)
                    messagebox.showinfo("Lockbox Created", f"{msg}")
                else:
                    messagebox.showerror("Error", msg)
            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def action_verify(self):
        txid = self.entry_verify_txid.get().strip()
        pw = self.entry_verify_key.get().strip()
        iv = self.entry_verify_iv.get().strip()
        
        if not txid or not pw:
            messagebox.showerror("Error", "Missing TXID or Key.")
            return

        self.txt_audit_log.delete("0.0", "end")
        self.txt_audit_log.insert("end", f"> Connecting to Node...\n> Verifying {txid}...\n")
        self.btn_verify.configure(state="disabled")

        def worker():
            diff = 32 
            success, msg = self.data_manager.verify_transaction_strict(txid, pw, iv, iv, diff)
            
            def finish():
                self.btn_verify.configure(state="normal")
                self.txt_audit_log.insert("end", msg + "\n")
                if success:
                    self.txt_audit_log.configure(text_color="#00ff00")
                else:
                    self.txt_audit_log.configure(text_color="orange")
            self.after(0, finish)
            
        threading.Thread(target=worker, daemon=True).start()

    # --- LISTS ---
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
            icon = "🔗" if st == "verified" else "✅" if st == "ready_to_link" else "📝"
            h = b['header']['block_hash']
            idx = b['header']['index']
            self.tree_blocks.insert("", "end", values=(idx, f"{icon} {h[:8]}..."))

    def on_block_select(self, event):
        if not event:
            if self.selected_block_index is None: return
        else:
            sel = self.tree_blocks.selection()
            if not sel: return
            idx = self.tree_blocks.item(sel)['values'][0]
            self.selected_block_index = idx
        
        blocks = self.data_manager.load_blocks(self.current_chain)
        block = next((b for b in blocks if b['header']['index'] == self.selected_block_index), None)
        
        if block:
            # 1. Block Maker (View)
            self.lbl_factory_mode.configure(text="MODE: VIEW ONLY (Saved)", text_color="gray")
            self.btn_commit.configure(state="disabled", text="BLOCK COMMITTED")
            self.f_draft_tools.pack_forget()
            
            preview = block['content'].get('preview')
            self.toggle_draft_ui() # Default to text view for metadata
            self.txt_content.delete("0.0", "end")
            
            if preview:
                self.txt_content.insert("0.0", preview)
            else:
                self.lbl_file_name.configure(text=f"{block['content']['filename']} (Encrypted)")
                self.txt_content.insert("0.0", f"[Binary File: {block['content']['filename']}]")

            self.lbl_generated_hash.configure(text=f"Hash: {block['header']['block_hash']}")
            
            # 2. Grinder
            enc_hash = hashlib.sha256(bytes.fromhex(block['encryption']['ciphertext_hex'])).hexdigest()[:16]
            self.lbl_grind_target.configure(text=f"Target Payload Hash: {enc_hash}...")
            
            # Fill transparency inputs
            self.entry_grind_key.delete(0, "end")
            self.entry_grind_key.insert(0, block['encryption']['key_used'])
            self.entry_grind_iv.delete(0, "end")
            self.entry_grind_iv.insert(0, f"{block['encryption']['nonce_hex']}")
            
            # 3. Verify
            self.entry_verify_key.delete(0, "end")
            self.entry_verify_key.insert(0, block['encryption']['key_used'])
            self.entry_verify_iv.delete(0, "end")
            self.entry_verify_iv.insert(0, block['encryption']['nonce_hex'])

if __name__ == "__main__":
    try:
        app = ObscurityApp()
        app.mainloop()
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        input("Press Enter to Exit...")