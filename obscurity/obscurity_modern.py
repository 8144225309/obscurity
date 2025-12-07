import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import math
import threading
import time
import hashlib
import json
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
        
        # Auto-Scan State
        self.auto_scan_active = False
        
        # Window Setup
        self.title("Obscurity [Anchor System] // Hackathon Build v3.6")
        self.geometry("1200x800")
        self.center_window(1200, 800)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # --- MAIN GRID ---
        self.grid_columnconfigure(0, weight=0, minsize=240)
        self.grid_columnconfigure(1, weight=0, minsize=280)
        self.grid_columnconfigure(2, weight=1)
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
        self.frame_right.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)
        self.build_right_header()
        
        self.container = ctk.CTkFrame(self.frame_right, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        self.view_tabs = self.create_main_view(self.container)
        
        self.style_legacy_widgets()
        self.refresh_chain_list()

    def on_closing(self):
        self.auto_scan_active = False
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

    # --- LEFT COLUMN (HIERARCHY) ---
    def build_hierarchy_column(self):
        ctk.CTkLabel(self.frame_left, text="TIMELINES", font=("Roboto", 14, "bold"), text_color="#aaaaaa").pack(pady=(15,5))
        tree_frame = ctk.CTkFrame(self.frame_left, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=5)
        self.tree_chains = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        self.tree_chains.pack(side="left", fill="both", expand=True)
        self.tree_chains.bind("<<TreeviewSelect>>", self.on_chain_select)
        
        # Buttons Frame
        btn_frame = ctk.CTkFrame(self.frame_left, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", pady=15, padx=10)
        
        self.btn_new_anchor = ctk.CTkButton(btn_frame, text="⚓ NEW ANCHOR", height=40, fg_color="#2ecc71", hover_color="#27ae60", command=self.action_new_anchor)
        self.btn_new_anchor.pack(fill="x", pady=4)
        self.btn_fork = ctk.CTkButton(btn_frame, text="⑂ FORK SELECTED", height=40, fg_color="#3498db", hover_color="#2980b9", command=self.action_fork_chain)
        self.btn_fork.pack(fill="x", pady=4)
        
        ctk.CTkFrame(btn_frame, height=2, fg_color="#333").pack(fill="x", pady=10) 
        
        # RESTORED: KEYSTORE BUTTON
        self.btn_keystore = ctk.CTkButton(btn_frame, text="🔑 KEYSTORE", height=30, fg_color="#444", hover_color="#555", command=self.action_open_keystore)
        self.btn_keystore.pack(fill="x", pady=4)

        self.btn_settings = ctk.CTkButton(btn_frame, text="⚙️ SETTINGS", height=30, fg_color="transparent", border_width=1, text_color="#aaa", hover_color="#333", command=self.action_open_settings)
        self.btn_settings.pack(fill="x", pady=4)

    # --- MID COLUMN (HISTORY) ---
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
        ctk.CTkLabel(parent, text="Payload Content:", anchor="w", font=("Roboto", 12)).pack(fill="x", padx=5)
        
        self.f_input_container = ctk.CTkFrame(parent, fg_color="#181818", corner_radius=6)
        self.f_input_container.pack(fill="both", expand=True, padx=5, pady=5)
        self.txt_content = ctk.CTkTextbox(self.f_input_container, wrap="word", font=("Consolas", 11))
        self.txt_content.pack(fill="both", expand=True, padx=2, pady=2)
        
        self.f_file_ui = ctk.CTkFrame(self.f_input_container, fg_color="transparent")
        self.btn_browse = ctk.CTkButton(self.f_file_ui, text="📂 Browse File...", width=140, command=self.action_browse_file)
        self.btn_browse.pack(side="left", padx=10)
        self.lbl_file_name = ctk.CTkLabel(self.f_file_ui, text="No file selected", text_color="gray")
        self.lbl_file_name.pack(side="left", padx=10)

        self.f_draft_tools = ctk.CTkFrame(parent, fg_color="transparent")
        self.var_input_type = ctk.StringVar(value="text")
        ctk.CTkRadioButton(self.f_draft_tools, text="Text (AES-GCM)", variable=self.var_input_type, value="text", command=self.toggle_draft_ui).pack(side="left", padx=10)
        ctk.CTkRadioButton(self.f_draft_tools, text="File (AES-CTR Hash)", variable=self.var_input_type, value="file", command=self.toggle_draft_ui).pack(side="left", padx=10)
        
        self.btn_commit = ctk.CTkButton(parent, text="🔒 GENERATE HASH & COMMIT", height=45, fg_color="green", hover_color="darkgreen", font=("Roboto", 13, "bold"), command=self.action_commit_block)
        self.btn_commit.pack(fill="x", padx=10, pady=15)
        self.lbl_generated_hash = ctk.CTkLabel(parent, text="Hash: Pending...", font=("Consolas", 11), text_color="gray")
        self.lbl_generated_hash.pack(pady=5)

    def toggle_draft_ui(self):
        if self.var_input_type.get() == "text":
            self.f_file_ui.pack_forget()
            self.txt_content.pack(fill="both", expand=True, padx=2, pady=2)
            self.update_key_estimate(self.slider_diff.get()) 
        else:
            self.txt_content.pack_forget()
            self.f_file_ui.pack(fill="both", expand=True, padx=2, pady=2)
            self.update_key_estimate(self.slider_diff.get())

    # --- TAB 2: PUBKEY GRINDER (STATISTICS VIEW) ---
    def setup_pubkey_grinder(self, parent):
        f_head = ctk.CTkFrame(parent, fg_color="#222")
        f_head.pack(fill="x", pady=10, padx=10)
        self.lbl_grind_target = ctk.CTkLabel(f_head, text="Target Payload Hash: [Waiting]", font=("Consolas", 12), text_color="cyan")
        self.lbl_grind_target.pack(padx=10, pady=5)

        f_inputs = ctk.CTkFrame(parent)
        f_inputs.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_inputs, text="Encryption Key Hint:", width=120).grid(row=0, column=0, padx=5, pady=5)
        self.entry_grind_key = ctk.CTkEntry(f_inputs, placeholder_text="Auto-filled from block")
        self.entry_grind_key.grid(row=0, column=1, sticky="ew", padx=5)
        ctk.CTkLabel(f_inputs, text="Salt / IV:", width=120).grid(row=1, column=0, padx=5, pady=5)
        self.entry_grind_iv = ctk.CTkEntry(f_inputs, placeholder_text="Auto-filled from block")
        self.entry_grind_iv.grid(row=1, column=1, sticky="ew", padx=5)
        f_inputs.grid_columnconfigure(1, weight=1)

        f_ctrl = ctk.CTkFrame(parent, fg_color="transparent")
        f_ctrl.pack(fill="x", padx=10, pady=10)
        
        # Difficulty Slider (MAX 256 for 1 Key)
        ctk.CTkLabel(f_ctrl, text="Density (Bits/Key):").pack(side="left", padx=5)
        self.slider_diff = ctk.CTkSlider(f_ctrl, from_=16, to=256, number_of_steps=240, width=150, command=self.update_key_estimate)
        self.slider_diff.set(32) 
        self.slider_diff.pack(side="left", padx=5)
        self.lbl_diff_display = ctk.CTkLabel(f_ctrl, text="32", width=30)
        self.lbl_diff_display.pack(side="left")

        # ESTIMATOR LABEL
        self.lbl_key_estimate = ctk.CTkLabel(f_ctrl, text="Est. Keys: --", text_color="#F39C12", font=("Roboto", 11, "bold"))
        self.lbl_key_estimate.pack(side="left", padx=15)

        # Worker Slider
        ctk.CTkLabel(f_ctrl, text="Workers:").pack(side="left", padx=(20, 5))
        self.slider_workers = ctk.CTkSlider(f_ctrl, from_=1, to=16, number_of_steps=15, width=100, command=lambda v: self.lbl_workers_display.configure(text=f"{int(v)}"))
        self.slider_workers.set(4)
        self.slider_workers.pack(side="left", padx=5)
        self.lbl_workers_display = ctk.CTkLabel(f_ctrl, text="4", width=30)
        self.lbl_workers_display.pack(side="left")

        self.btn_start_grind = ctk.CTkButton(parent, text="START GRINDING SEQUENCE", height=45, fg_color="#e74c3c", hover_color="#c0392b", font=("Roboto", 13, "bold"), command=self.action_run_grinder)
        self.btn_start_grind.pack(fill="x", padx=20, pady=10)

        # STATISTICAL DASHBOARD
        self.f_stats = ctk.CTkFrame(parent, fg_color="#111", corner_radius=10)
        self.f_stats.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.lbl_stat_status = ctk.CTkLabel(self.f_stats, text="STATUS: IDLE", font=("Roboto", 16, "bold"), text_color="#777")
        self.lbl_stat_status.pack(pady=(20, 10))
        
        self.progress_bar = ctk.CTkProgressBar(self.f_stats, orientation="horizontal", height=20)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=40, pady=10)
        
        f_metrics = ctk.CTkFrame(self.f_stats, fg_color="transparent")
        f_metrics.pack(fill="x", padx=40, pady=10)
        
        self.lbl_stat_keys = ctk.CTkLabel(f_metrics, text="Keys Found: 0 / 0", font=("Consolas", 14))
        self.lbl_stat_keys.pack(side="left", expand=True)
        
        self.lbl_stat_speed = ctk.CTkLabel(f_metrics, text="Speed: 0.00 M/s", font=("Consolas", 14), text_color="cyan")
        self.lbl_stat_speed.pack(side="right", expand=True)

    # --- ESTIMATOR LOGIC (CALIBRATED) ---
    def update_key_estimate(self, value):
        val = int(value)
        self.lbl_diff_display.configure(text=f"{val}")
        
        payload_size = 0
        
        # 1. Check Mode
        if self.var_input_type.get() == "file" or (self.selected_block_index is not None and self.lbl_file_name.cget("text") != "No file selected"):
             # AES-CTR Hash Payload is ALWAYS 32 Bytes
             payload_size = 32
        else:
            # AES-GCM Text Payload = Text Length + 16 Bytes (Tag)
            txt = self.txt_content.get("0.0", "end").strip().encode('utf-8')
            payload_size = len(txt) + 16 

        # 2. Math: Payload_Bytes / (Bits_Per_Key / 8)
        bytes_per_key = val / 8
        if bytes_per_key > 0:
            num_keys = math.ceil(payload_size / bytes_per_key)
            self.lbl_key_estimate.configure(text=f"Est. Keys: ~{num_keys}")

    # --- TAB 3: VERIFY ONCHAIN ---
    def setup_verify_onchain(self, parent):
        # 1. WATCHLIST SECTION
        ctk.CTkLabel(parent, text="Pending Watchlist (Ready for Chain):", font=("Roboto", 12, "bold"), text_color="orange").pack(anchor="w", padx=20, pady=(15,5))
        
        wl_frame = ctk.CTkFrame(parent, height=150)
        wl_frame.pack(fill="x", padx=20)
        
        cols = ("chain", "block", "status")
        self.tree_watchlist = ttk.Treeview(wl_frame, columns=cols, show="headings", height=5)
        self.tree_watchlist.heading("chain", text="Chain")
        self.tree_watchlist.heading("block", text="Block #")
        self.tree_watchlist.heading("status", text="First Key (Prefix)")
        self.tree_watchlist.column("chain", width=150)
        self.tree_watchlist.column("block", width=60, anchor="center")
        self.tree_watchlist.pack(side="left", fill="both", expand=True)
        self.tree_watchlist.bind("<<TreeviewSelect>>", self.on_watchlist_select)
        
        # Watchlist Toolbar
        wl_tools = ctk.CTkFrame(parent, fg_color="transparent")
        wl_tools.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkButton(wl_tools, text="↻ Refresh List", width=100, command=self.refresh_watchlist).pack(side="left")
        self.switch_autoscan = ctk.CTkSwitch(wl_tools, text="AUTO-SCAN NETWORK (Every 60s)", command=self.toggle_auto_scan)
        self.switch_autoscan.pack(side="right")

        # 2. MANUAL VERIFY
        ctk.CTkLabel(parent, text="Manual Verification:", font=("Roboto", 12, "bold")).pack(anchor="w", padx=20, pady=(20,5))
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

        self.btn_verify = ctk.CTkButton(parent, text="CONNECT NODE & VERIFY", height=45, fg_color="#f39c12", hover_color="#d35400", command=self.action_verify)
        self.btn_verify.pack(fill="x", padx=40, pady=20)
        
        ctk.CTkLabel(parent, text="Verification Log:", anchor="w").pack(fill="x", padx=20)
        self.txt_audit_log = ctk.CTkTextbox(parent, font=("Consolas", 10), height=100)
        self.txt_audit_log.pack(fill="both", expand=True, padx=20, pady=10)

        self.refresh_watchlist()

    # --- RESTORED: KEYSTORE MANAGER ---
    def action_open_keystore(self):
        toplevel = ctk.CTkToplevel(self)
        toplevel.title("Keystore Manager")
        toplevel.geometry("800x600")
        
        ctk.CTkLabel(toplevel, text="Generated Key Repository", font=("Roboto", 16, "bold")).pack(pady=10)
        
        # Keystore Tree
        cols = ("chain", "idx", "status", "keys_count", "first_key")
        ks_tree = ttk.Treeview(toplevel, columns=cols, show="headings", height=20)
        ks_tree.heading("chain", text="Chain")
        ks_tree.heading("idx", text="#")
        ks_tree.heading("status", text="Status")
        ks_tree.heading("keys_count", text="Keys")
        ks_tree.heading("first_key", text="First Key (Preview)")
        ks_tree.column("idx", width=50)
        ks_tree.column("keys_count", width=50)
        ks_tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Populate
        all_blocks = []
        for c in self.data_manager.get_chains():
            blocks = self.data_manager.load_blocks(c['folder'])
            for b in blocks:
                keys = b.get('steganography', {}).get('keys', [])
                if keys:
                    ks_tree.insert("", "end", values=(
                        c['name'], 
                        b['header']['index'], 
                        b['header']['status'].upper(), 
                        len(keys), 
                        keys[0][:20] + "..."
                    ))
        
        ctk.CTkButton(toplevel, text="EXPORT RAW JSON", command=lambda: messagebox.showinfo("Info", "Export feature coming soon.")).pack(pady=10)

    # --- SETTINGS MODAL (WITH TOGGLE) ---
    def action_open_settings(self):
        toplevel = ctk.CTkToplevel(self)
        toplevel.title("Settings")
        toplevel.geometry("500x500")
        
        curr = self.data_manager.config
        
        # Node Config
        ctk.CTkLabel(toplevel, text="Bitcoin Node Configuration", font=("Roboto", 14, "bold")).pack(pady=(20,10))
        f = ctk.CTkFrame(toplevel)
        f.pack(fill="x", padx=20)
        
        ctk.CTkLabel(f, text="RPC Host:").grid(row=0, column=0, padx=10, pady=5)
        e_ip = ctk.CTkEntry(f); e_ip.insert(0, curr.get("rpc_host", "127.0.0.1")); e_ip.grid(row=0, column=1, sticky="ew")
        
        ctk.CTkLabel(f, text="RPC Port:").grid(row=1, column=0, padx=10, pady=5)
        e_port = ctk.CTkEntry(f); e_port.insert(0, str(curr.get("rpc_port", 8332))); e_port.grid(row=1, column=1, sticky="ew")

        ctk.CTkLabel(f, text="User:").grid(row=2, column=0, padx=10, pady=5)
        e_user = ctk.CTkEntry(f); e_user.insert(0, curr.get("rpc_user", "")); e_user.grid(row=2, column=1, sticky="ew")

        ctk.CTkLabel(f, text="Pass:").grid(row=3, column=0, padx=10, pady=5)
        e_pass = ctk.CTkEntry(f, show="*"); e_pass.insert(0, curr.get("rpc_pass", "")); e_pass.grid(row=3, column=1, sticky="ew")
        f.grid_columnconfigure(1, weight=1)

        # SECURITY TOGGLES
        ctk.CTkLabel(toplevel, text="Security Preferences", font=("Roboto", 14, "bold")).pack(pady=(20,10))
        
        # This checkbox implies logic that would exist in a full persistent backend
        var_plaintext = ctk.IntVar(value=0) # Default Off
        chk_plaintext = ctk.CTkCheckBox(toplevel, text="Store Keystore in Plaintext (Unsafe/Recovery Mode)", variable=var_plaintext, text_color="orange")
        chk_plaintext.pack(pady=10)

        def save():
            conf = {
                "rpc_host": e_ip.get(), "rpc_port": int(e_port.get()),
                "rpc_user": e_user.get(), "rpc_pass": e_pass.get(),
                "plaintext_keystore": bool(var_plaintext.get())
            }
            self.data_manager.save_config(conf)
            messagebox.showinfo("Saved", "Settings updated.")
            toplevel.destroy()

        ctk.CTkButton(toplevel, text="SAVE SETTINGS", command=save, fg_color="#3498db").pack(pady=20)

    # --- MAIN UI LOGIC ---
    def refresh_watchlist(self):
        for i in self.tree_watchlist.get_children(): self.tree_watchlist.delete(i)
        items = self.data_manager.get_pending_broadcasts()
        for item in items:
            key_preview = item['first_key'][:16] + "..."
            self.tree_watchlist.insert("", "end", values=(item['chain_folder'], item['block_index'], key_preview))

    def on_watchlist_select(self, event):
        sel = self.tree_watchlist.selection()
        if not sel: return
        item_vals = self.tree_watchlist.item(sel)['values']
        all_pending = self.data_manager.get_pending_broadcasts()
        target = next((x for x in all_pending if x['chain_folder'] == item_vals[0] and str(x['block_index']) == str(item_vals[1])), None)
        if target:
            self.entry_verify_key.delete(0, "end")
            self.entry_verify_key.insert(0, target['pw'])
            self.entry_verify_iv.delete(0, "end")
            self.entry_verify_iv.insert(0, target['iv'])
            self.txt_audit_log.insert("end", f"> Autofilled keys for Block {target['block_index']}\n")

    def toggle_auto_scan(self):
        if self.switch_autoscan.get() == 1:
            if not self.auto_scan_active:
                self.auto_scan_active = True
                self.lbl_status.configure(text="AUTO-SCAN: ACTIVE", text_color="#00ff00")
                threading.Thread(target=self.auto_scan_loop, daemon=True).start()
        else:
            self.auto_scan_active = False
            self.lbl_status.configure(text="System Ready", text_color="#00ff00")

    def auto_scan_loop(self):
        while self.auto_scan_active:
            results = self.data_manager.auto_scan_network(lookback=3)
            if results:
                def notify():
                    self.refresh_watchlist() 
                    self.refresh_chain_list() 
                    for r in results:
                        self.txt_audit_log.insert("end", f"[AUTO] {r}\n")
                        messagebox.showinfo("BLOCK VERIFIED!", r)
                self.after(0, notify)
            for _ in range(60):
                if not self.auto_scan_active: break
                time.sleep(1)

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

        self.entry_grind_key.delete(0, "end")
        self.entry_grind_iv.delete(0, "end")
        self.entry_verify_key.delete(0, "end")
        self.entry_verify_iv.delete(0, "end")
        self.lbl_grind_target.configure(text="Target Payload Hash: [Waiting]")
        
        self.lbl_stat_status.configure(text="STATUS: IDLE", text_color="#777")
        self.progress_bar.set(0)
        self.lbl_stat_keys.configure(text="Keys Found: 0 / 0")
        self.lbl_stat_speed.configure(text="Speed: 0.00 M/s")

    def action_browse_file(self):
        path = filedialog.askopenfilename()
        if path:
            self.lbl_file_name.configure(text=os.path.basename(path))
            with open(path, "rb") as f:
                self.draft_payload = f.read()
            self.draft_filename = os.path.basename(path)
            preview_len = 512
            if len(self.draft_payload) > preview_len:
                self.toggle_draft_ui()
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
        self.on_block_select(None)
        messagebox.showinfo("Success", "Block committed to disk.")

    def action_run_grinder(self):
        if not self.current_chain or self.selected_block_index is None: return
        diff = int(self.slider_diff.get())
        workers = int(self.slider_workers.get())
        self.btn_start_grind.configure(state="disabled", text="GRINDING IN PROGRESS...")
        self.lbl_stat_status.configure(text="STATUS: RUNNING", text_color="#00ff00")
        
        def on_progress(msg_type, data, total_keys):
            def update_ui():
                if msg_type == "success":
                    idx = data['index'] + 1
                    gps_fmt = f"{data['gps']/1_000_000:.1f} M/s"
                    progress = idx / total_keys
                    self.progress_bar.set(progress)
                    self.lbl_stat_keys.configure(text=f"Keys Found: {idx} / {total_keys}")
                    self.lbl_stat_speed.configure(text=f"Speed: {gps_fmt}")
            self.after(0, update_ui)

        def worker():
            chain = self.current_chain
            idx = self.selected_block_index
            success, msg = self.data_manager.run_grinder(chain, idx, diff, workers, on_progress)
            def finish():
                self.btn_start_grind.configure(state="normal", text="START GRINDING SEQUENCE")
                if success:
                    self.lbl_stat_status.configure(text="STATUS: COMPLETE", text_color="cyan")
                    self.progress_bar.set(1)
                    self.load_chain_blocks(chain)
                    self.refresh_watchlist() 
                    messagebox.showinfo("Lockbox Created", f"{msg}")
                else:
                    self.lbl_stat_status.configure(text="STATUS: FAILED", text_color="red")
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
            diff = int(self.slider_diff.get())
            success, msg = self.data_manager.verify_transaction_strict(txid, pw, iv, "", diff, "AES-256-CTR") # Default to CTR verify if ambiguous, or handled by backend logic
            # Note: Backend verify_transaction_strict now takes 'algo'. 
            # We can try to infer or pass a default. The backend 'auto_scan' logic knows the algo from the block file.
            # For MANUAL verification, we might need a dropdown or just let the backend failover.
            # Updated Backend verify handles GCM vs CTR.
            # Let's rely on the backend's auto-detection or 'tag' presence logic if possible, 
            # OR pass the algo based on what the user thinks it is.
            # For now, let's assume the user is verifying what they just built.
            algo = "AES-256-CTR" if self.var_input_type.get() == "file" else "AES-256-GCM"
            
            # Actually, the backend's verify function signature in File 1 was updated to take 'algo'.
            # We should probably pass that if we know it.
            # If manually verifying, we don't have the block metadata easily unless we looked it up.
            # Let's just pass "AES-256-CTR" for file mode context or GCM for text.
            
            success, msg = self.data_manager.verify_transaction_strict(txid, pw, iv, "", diff, algo)
            
            def finish():
                self.btn_verify.configure(state="normal")
                self.txt_audit_log.insert("end", msg + "\n")
                if success:
                    self.txt_audit_log.configure(text_color="#00ff00")
                else:
                    self.txt_audit_log.configure(text_color="orange")
            self.after(0, finish)
        threading.Thread(target=worker, daemon=True).start()

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
            self.lbl_factory_mode.configure(text="MODE: VIEW ONLY (Saved)", text_color="gray")
            self.btn_commit.configure(state="disabled", text="BLOCK COMMITTED")
            self.f_draft_tools.pack_forget()
            preview = block['content'].get('preview')
            self.toggle_draft_ui()
            self.txt_content.delete("0.0", "end")
            if preview:
                self.txt_content.insert("0.0", preview)
            else:
                self.lbl_file_name.configure(text=f"{block['content']['original_filename']} (Encrypted Hash)")
                self.txt_content.insert("0.0", f"[File Hash]: {block['content']['content_hash_sha256']}")
            self.lbl_generated_hash.configure(text=f"Hash: {block['header']['block_hash']}")
            enc_hash = hashlib.sha256(bytes.fromhex(block['encryption']['ciphertext_hex'])).hexdigest()[:16]
            self.lbl_grind_target.configure(text=f"Target Payload Hash: {enc_hash}...")
            self.entry_grind_key.delete(0, "end")
            self.entry_grind_key.insert(0, block['encryption']['key_used'])
            self.entry_grind_iv.delete(0, "end")
            self.entry_grind_iv.insert(0, f"{block['encryption']['nonce_hex']}")
            self.entry_verify_key.delete(0, "end")
            self.entry_verify_key.insert(0, block['encryption']['key_used'])
            self.entry_verify_iv.delete(0, "end")
            self.entry_verify_iv.insert(0, block['encryption']['nonce_hex'])
            self.update_key_estimate(self.slider_diff.get())

    def load_chain_blocks(self, chain):
        for i in self.tree_blocks.get_children(): self.tree_blocks.delete(i)
        blocks = self.data_manager.load_blocks(chain)
        for b in blocks:
            st = b['header']['status']
            icon = "🔗" if st == "verified" else "✅" if st == "ready_to_link" else "📝"
            h = b['header']['block_hash']
            idx = b['header']['index']
            self.tree_blocks.insert("", "end", values=(idx, f"{icon} {h[:8]}..."))

if __name__ == "__main__":
    try:
        app = ObscurityApp()
        app.mainloop()
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        input("Press Enter to Exit...")