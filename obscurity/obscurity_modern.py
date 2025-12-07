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
        
        self.data_manager = obscurity_backend.DataManager()
        self.current_chain = None

        # Window Setup
        self.title("Obscurity [Fork-Aware] // Hackathon Build v0.6")
        self.geometry("1300x850")

        # --- MAIN GRID ---
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

        # 3. Right (Factories)
        self.frame_right = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_right.grid(row=0, column=2, sticky="nsew", padx=20, pady=20)
        
        self.build_right_header()
        
        self.container = ctk.CTkFrame(self.frame_right, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        self.view_factories = self.create_factories_view(self.container)
        self.view_config = self.create_config_view(self.container)
        self.view_keystore = self.create_keystore_view(self.container)

        self.show_view("factories")
        self.style_legacy_widgets()
        self.refresh_chain_list()

    def style_legacy_widgets(self):
        style = ttk.Style()
        style.theme_use("clam")
        bg_color, fg_color, hl_color = "#2b2b2b", "#ffffff", "#1f538d"
        style.configure("Treeview", background=bg_color, foreground=fg_color, fieldbackground=bg_color, borderwidth=0, rowheight=30, font=("Roboto Medium", 10))
        style.configure("Treeview.Heading", background="#202020", foreground="#aaaaaa", relief="flat", font=("Roboto", 9, "bold"))
        style.map("Treeview", background=[('selected', hl_color)])

    # --- BUILDERS ---
    def build_chains_column(self):
        lbl = ctk.CTkLabel(self.frame_chains, text="CHAINS / FORKS", font=("Roboto", 12, "bold"), text_color="#aaaaaa")
        lbl.pack(fill="x", pady=(15, 10), padx=10)
        
        tree_frame = ctk.CTkFrame(self.frame_chains, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True)

        self.tree_chains = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        self.tree_chains.pack(side="left", fill="both", expand=True)
        self.tree_chains.bind("<<TreeviewSelect>>", self.on_chain_select)
        
        sb = ctk.CTkScrollbar(tree_frame, command=self.tree_chains.yview, width=16)
        sb.pack(side="right", fill="y")
        self.tree_chains.configure(yscrollcommand=sb.set)
        
        btn_frame = ctk.CTkFrame(self.frame_chains, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", pady=10, padx=10)
        
        ctk.CTkButton(btn_frame, text="+ New Chain", height=35, command=self.action_new_chain).pack(fill="x", pady=5)
        # Added Load Examples Button
        ctk.CTkButton(btn_frame, text="Load Example Data", height=25, fg_color="#333", hover_color="#444", command=self.action_load_examples).pack(fill="x", pady=(5,0))
        ctk.CTkButton(btn_frame, text="⑂ Clone Chain", height=35, fg_color="#2d2d2d", hover_color="#3a3a3a").pack(fill="x", pady=(5,0))

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
        self.tree_blocks.bind("<<TreeviewSelect>>", self.on_block_select)
        
        sb = ctk.CTkScrollbar(tree_frame, command=self.tree_blocks.yview, width=16)
        sb.pack(side="right", fill="y")
        self.tree_blocks.configure(yscrollcommand=sb.set)

        btn_frame = ctk.CTkFrame(self.frame_blocks, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", pady=10, padx=10)
        
        ctk.CTkButton(btn_frame, text="+ New Block", height=35, fg_color="#1f538d", hover_color="#3a7ebf", command=self.action_new_block).pack(fill="x", pady=5)
        
        sub_row = ctk.CTkFrame(btn_frame, fg_color="transparent")
        sub_row.pack(fill="x")
        ctk.CTkButton(sub_row, text="Verify", width=120, fg_color="#333", hover_color="#444", command=lambda: self.tabs.set("Network Factory")).pack(side="left", padx=(0,5))
        ctk.CTkButton(sub_row, text="Delete", width=80, fg_color="#800000", hover_color="#a00000").pack(side="right")

    def build_right_header(self):
        header = ctk.CTkFrame(self.frame_right, height=40, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(header, text="Active Workflow", font=("Roboto", 16, "bold")).pack(side="left")
        ctk.CTkFrame(header, width=20, height=1, fg_color="transparent").pack(side="right")
        self.btn_cfg = ctk.CTkButton(header, text="⚙ Config", width=80, fg_color="#333", hover_color="#555", command=lambda: self.show_view("config"))
        self.btn_cfg.pack(side="right", padx=5)
        self.btn_keys = ctk.CTkButton(header, text="🔑 Keystore", width=90, fg_color="#333", hover_color="#555", command=lambda: self.show_view("keystore"))
        self.btn_keys.pack(side="right", padx=5)
        self.btn_work = ctk.CTkButton(header, text="🔨 Factories", width=90, fg_color="transparent", border_width=1, command=lambda: self.show_view("factories"))
        self.btn_work.pack(side="right", padx=5)

    # --- VIEWS ---
    def create_factories_view(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.tabs = ctk.CTkTabview(frame)
        self.tabs.pack(fill="both", expand=True)
        self.tabs.add("Payload Factory")
        self.tabs.add("Grind Factory")
        self.tabs.add("Network Factory")

        p = self.tabs.tab("Payload Factory")
        ctk.CTkLabel(p, text="Step 1: Construct Block Data", font=("Roboto", 20, "bold")).pack(anchor="w", pady=(10, 20))
        f_ex = ctk.CTkFrame(p, fg_color="transparent")
        f_ex.pack(anchor="w", fill="x", pady=(0, 10))
        ctk.CTkLabel(f_ex, text="Load Example:", text_color="gray").pack(side="left", padx=(0, 10))
        ctk.CTkButton(f_ex, text="Hello World", height=24, width=80, fg_color="#333", hover_color="#444").pack(side="left", padx=5)
        ctk.CTkButton(f_ex, text="Small Image", height=24, width=80, fg_color="#333", hover_color="#444").pack(side="left", padx=5)
        self.txt_payload = ctk.CTkTextbox(p, font=("Consolas", 12))
        self.txt_payload.pack(fill="both", expand=True, pady=10)
        self.txt_payload.insert("0.0", "Type data here...")
        ctk.CTkButton(p, text="COMPUTE HASH", height=50, fg_color="#1f538d", command=self.action_compute_hash).pack(fill="x", pady=10)
        self.lbl_hash_res = ctk.CTkLabel(p, text="Hash: <Pending>", font=("Consolas", 12), text_color="gray")
        self.lbl_hash_res.pack(pady=5)

        g = self.tabs.tab("Grind Factory")
        ctk.CTkLabel(g, text="Step 2: Generate Keys", font=("Roboto", 20, "bold")).pack(anchor="w", pady=(10, 20))
        ctk.CTkLabel(g, text="Target Hash:", anchor="w").pack(fill="x")
        self.lbl_grind_target = ctk.CTkLabel(g, text="<Select Block>", font=("Consolas", 14), text_color="#1f538d")
        self.lbl_grind_target.pack(pady=5)
        ctk.CTkButton(g, text="▶ START GRINDER (Simulated)", height=60, fg_color="green", hover_color="darkgreen").pack(fill="x", pady=20)

        n = self.tabs.tab("Network Factory")
        ctk.CTkLabel(n, text="Step 3: Broadcast & Verify", font=("Roboto", 20, "bold")).pack(anchor="w", pady=(10, 20))
        f_link = ctk.CTkFrame(n, fg_color="#2b2b2b")
        f_link.pack(fill="x", pady=10, padx=5)
        ctk.CTkLabel(f_link, text="Link Transaction", font=("Roboto", 14, "bold")).pack(anchor="w", padx=10, pady=10)
        f_tx_row = ctk.CTkFrame(f_link, fg_color="transparent")
        f_tx_row.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkLabel(f_tx_row, text="TxID:", width=40).pack(side="left")
        self.ent_txid = ctk.CTkEntry(f_tx_row, placeholder_text="Enter TxID...")
        self.ent_txid.pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkButton(f_tx_row, text="Link", width=80, fg_color="#333", command=self.action_link_tx).pack(side="right")

        f_ver = ctk.CTkFrame(n, fg_color="transparent")
        f_ver.pack(fill="both", expand=True, pady=10)
        ctk.CTkButton(f_ver, text="✅ FETCH & VERIFY ON NODE", height=50, fg_color="#1f538d", hover_color="#3a7ebf", command=self.action_verify).pack(fill="x", pady=10)
        self.txt_ver_log = ctk.CTkTextbox(f_ver, font=("Consolas", 10), height=150)
        self.txt_ver_log.pack(fill="both", expand=True)
        return frame

    def create_config_view(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="#2b2b2b", corner_radius=10)
        ctk.CTkLabel(frame, text="System Configuration", font=("Roboto", 24, "bold")).pack(pady=20)
        form = ctk.CTkFrame(frame, fg_color="transparent")
        form.pack(pady=10)
        self.entries = {}
        fields = [("RPC Host", "rpc_host"), ("RPC Port", "rpc_port"), ("RPC User", "rpc_user"), ("RPC Pass", "rpc_pass")]
        curr_conf = self.data_manager.load_config()
        for i, (label, key) in enumerate(fields):
            ctk.CTkLabel(form, text=label+":").grid(row=i, column=0, sticky="e", padx=10, pady=10)
            e = ctk.CTkEntry(form, width=300)
            e.insert(0, str(curr_conf.get(key, "")))
            e.grid(row=i, column=1, padx=10, pady=10)
            self.entries[key] = e
        ctk.CTkLabel(form, text="Data Dir:").grid(row=4, column=0, sticky="e", padx=10, pady=10)
        e_dir = ctk.CTkEntry(form, width=300)
        e_dir.insert(0, str(curr_conf.get("data_dir", "")))
        e_dir.grid(row=4, column=1, padx=10, pady=10)
        self.entries["data_dir"] = e_dir

        tk.Label(form, text="--- ZMQ Settings (Scanning) ---", bg="#2b2b2b", fg="gray").grid(row=5, column=1, pady=10)
        ctk.CTkLabel(form, text="ZMQ Host:", text_color="gray").grid(row=6, column=0, sticky="e", padx=10)
        e_zmq_h = ctk.CTkEntry(form, width=300, text_color="gray"); e_zmq_h.insert(0, "127.0.0.1"); e_zmq_h.configure(state="disabled"); e_zmq_h.grid(row=6, column=1, padx=10, pady=5)
        ctk.CTkLabel(form, text="ZMQ Port:", text_color="gray").grid(row=7, column=0, sticky="e", padx=10)
        e_zmq_p = ctk.CTkEntry(form, width=300, text_color="gray"); e_zmq_p.insert(0, "28332"); e_zmq_p.configure(state="disabled"); e_zmq_p.grid(row=7, column=1, padx=10, pady=5)

        ctk.CTkButton(frame, text="Save Config", width=200, height=40, fg_color="#1f538d", command=self.action_save_config).pack(pady=(30, 10))
        ctk.CTkButton(frame, text="Test RPC Connection", width=200, height=30, fg_color="transparent", border_width=1, command=self.action_test_connection).pack(pady=10)
        return frame

    def create_keystore_view(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="#2b2b2b")
        ctk.CTkLabel(frame, text="Secure Keystore", font=("Roboto", 24, "bold")).pack(pady=(20, 5))
        ctk.CTkLabel(frame, text="⚠️ Proper wallet implementation soon.", text_color="orange").pack(pady=(0, 20))
        return frame

    def show_view(self, view_name):
        self.view_factories.pack_forget(); self.view_config.pack_forget(); self.view_keystore.pack_forget()
        self.btn_cfg.configure(fg_color="#333"); self.btn_keys.configure(fg_color="#333"); self.btn_work.configure(fg_color="transparent")
        if view_name == "factories": self.view_factories.pack(fill="both", expand=True); self.btn_work.configure(fg_color="#1f538d")
        elif view_name == "config": self.view_config.pack(fill="both", expand=True); self.btn_cfg.configure(fg_color="#1f538d")
        elif view_name == "keystore": self.view_keystore.pack(fill="both", expand=True); self.btn_keys.configure(fg_color="#1f538d")

    # --- ACTIONS ---
    def action_new_chain(self):
        d = ctk.CTkInputDialog(text="Name:", title="New Chain"); name = d.get_input()
        if name:
            folder = self.data_manager.create_new_chain(name)
            self.refresh_chain_list()
            # AUTO-SELECT LOGIC
            for item in self.tree_chains.get_children():
                if self.tree_chains.item(item)['values'][0] == folder:
                    self.tree_chains.selection_set(item)
                    self.on_chain_select(None)
                    break
    
    def action_load_examples(self):
        folder = self.data_manager.create_example_chains()
        self.refresh_chain_list()
        # AUTO-SELECT LOGIC for Examples
        for item in self.tree_chains.get_children():
            if self.tree_chains.item(item)['values'][0] == folder:
                self.tree_chains.selection_set(item)
                self.on_chain_select(None)
                break

    def action_new_block(self):
        if not self.current_chain: return
        blocks = self.data_manager.load_blocks(self.current_chain)
        idx = len(blocks)
        prev = blocks[-1]['block_hash'] if blocks else None
        self.data_manager.create_block(self.current_chain, idx, prev, "Empty Payload")
        self.load_chain_blocks(self.current_chain)

    def action_compute_hash(self):
        if not self.current_chain: return
        sel = self.tree_blocks.selection()
        if not sel: return
        txt = self.tree_blocks.item(sel)['values'][1]
        idx = int(txt.split('_')[0])
        blocks = self.data_manager.load_blocks(self.current_chain)
        prev = blocks[idx-1]['block_hash'] if idx > 0 else None
        payload = self.txt_payload.get("0.0", "end").strip()
        data = self.data_manager.create_block(self.current_chain, idx, prev, payload, is_anchor=(idx==0))
        self.lbl_hash_res.configure(text=f"Hash: {data['block_hash']}")
        self.load_chain_blocks(self.current_chain)

    def action_link_tx(self):
        txid = self.ent_txid.get().strip()
        if not self.current_chain or not txid: return
        sel = self.tree_blocks.selection()
        if not sel: return
        txt = self.tree_blocks.item(sel)['values'][1]
        idx = int(txt.split('_')[0])
        self.data_manager.update_block_status(self.current_chain, idx, txid=txid, status="linked")
        self.load_chain_blocks(self.current_chain)
        self.txt_ver_log.insert("end", f"Linked TxID: {txid}\n")

    def action_verify(self):
        txid = self.ent_txid.get().strip()
        if not txid: self.txt_ver_log.insert("end", "Error: No TxID linked.\n"); return
        sel = self.tree_blocks.selection()
        if not sel: return
        txt = self.tree_blocks.item(sel)['values'][1]
        idx = int(txt.split('_')[0])
        block_data = self.data_manager.update_block_status(self.current_chain, idx)
        expected = block_data['block_hash']
        self.txt_ver_log.insert("end", f"Verifying {expected} against {txid}...\n")
        self.txt_ver_log.see("end")
        success, log = self.data_manager.verify_on_chain(txid, expected)
        self.txt_ver_log.insert("end", log + "\n----------------\n")
        self.txt_ver_log.see("end")
        if success:
            self.data_manager.update_block_status(self.current_chain, idx, status="verified")
            self.load_chain_blocks(self.current_chain)

    def action_save_config(self):
        new_conf = {k: v.get() for k, v in self.entries.items()}
        self.data_manager.save_config(new_conf)

    def action_test_connection(self):
        self.action_save_config()
        success, msg = self.data_manager.test_rpc_connection()
        if success: tk.messagebox.showinfo("Success", msg)
        else: tk.messagebox.showerror("Connection Failed", msg)

    # --- LIST LOGIC ---
    def refresh_chain_list(self):
        for i in self.tree_chains.get_children(): self.tree_chains.delete(i)
        for c in self.data_manager.get_chains(): self.tree_chains.insert("", "end", text=f" {c}", values=(c,))

    def on_chain_select(self, event):
        sel = self.tree_chains.selection()
        if not sel: return
        self.current_chain = self.tree_chains.item(sel)['values'][0]
        self.load_chain_blocks(self.current_chain)
        self.show_view("factories")

    def load_chain_blocks(self, chain):
        for i in self.tree_blocks.get_children(): self.tree_blocks.delete(i)
        blocks = self.data_manager.load_blocks(chain)
        for b in blocks:
            st = b.get('status', 'unlinked')
            icon = "✅" if st == "verified" else "🔵" if st == "linked" else "⚪"
            h = b.get('block_hash', '????????')
            self.tree_blocks.insert("", "end", values=(icon, f"{b['index']:05d}_{h[:8]}..."))

    def on_block_select(self, event):
        sel = self.tree_blocks.selection()
        if not sel: return
        txt = self.tree_blocks.item(sel)['values'][1]
        self.lbl_grind_target.configure(text=f"Target: {txt}")

if __name__ == "__main__":
    app = ObscurityApp()
    app.mainloop()