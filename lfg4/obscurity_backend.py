import os
import json
import uuid
import time
import hashlib
import binascii
import requests
import base64

# --- CONSTANTS ---
DATA_DIR = "obscurity_data"
CHAINS_DIR = os.path.join(DATA_DIR, "chains")
KEYSTORE_DIR = os.path.join(DATA_DIR, "keystore")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

class DataManager:
    def __init__(self):
        self.ensure_directories()
        self.config = self.load_config()

    def ensure_directories(self):
        for d in [DATA_DIR, CHAINS_DIR, KEYSTORE_DIR]:
            if not os.path.exists(d): os.makedirs(d)
        
        if not os.path.exists(CONFIG_FILE):
            default_config = {
                "rpc_host": "127.0.0.1",
                "rpc_port": 8332,
                "rpc_user": "user",
                "rpc_pass": "pass",
                "zmq_host": "127.0.0.1",
                "zmq_port": 28332,
                "data_dir": os.path.join(os.getenv('APPDATA'), "Bitcoin") if os.name == 'nt' else ""
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(default_config, f, indent=4)

    def load_config(self):
        with open(CONFIG_FILE, 'r') as f: return json.load(f)

    def save_config(self, new_conf):
        self.config.update(new_conf)
        with open(CONFIG_FILE, 'w') as f: json.dump(self.config, f, indent=4)

    # --- CHAIN MANAGEMENT ---
    def get_chains(self):
        if not os.path.exists(CHAINS_DIR): return []
        return [d for d in os.listdir(CHAINS_DIR) if os.path.isdir(os.path.join(CHAINS_DIR, d))]

    def create_new_chain(self, name):
        chain_id = str(uuid.uuid4())[:8]
        safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).strip()
        folder_name = f"{safe_name}_{chain_id}"
        chain_path = os.path.join(CHAINS_DIR, folder_name)
        
        os.makedirs(chain_path)
        os.makedirs(os.path.join(chain_path, "blocks"))

        meta = {"name": name, "id": chain_id, "created_at": time.time()}
        with open(os.path.join(chain_path, "chain_meta.json"), "w") as f:
            json.dump(meta, f, indent=4)

        # Create Anchor (Index 0)
        self.create_block(folder_name, 0, None, "Genesis Anchor", is_anchor=True)
        return folder_name

    def create_block(self, chain_folder, index, prev_hash, payload_data, is_anchor=False):
        # 1. Compute Hash
        hasher = hashlib.sha256()
        hasher.update(str(index).encode())
        hasher.update(str(prev_hash).encode())
        hasher.update(str(payload_data).encode())
        block_hash = hasher.hexdigest()

        block_data = {
            "index": index,
            "is_anchor": is_anchor,
            "block_hash": block_hash,
            "prev_hash": prev_hash,
            "payload": payload_data,
            "status": "unlinked", # unlinked, linked, verified
            "txid": None,
            "grind_data": [] # Will store keys later
        }
        
        filename = f"{index:05d}_{block_hash[:8]}.json"
        path = os.path.join(CHAINS_DIR, chain_folder, "blocks", filename)
        with open(path, "w") as f: json.dump(block_data, f, indent=4)
        return block_data

    def load_blocks(self, chain_folder):
        blocks_dir = os.path.join(CHAINS_DIR, chain_folder, "blocks")
        if not os.path.exists(blocks_dir): return []
        
        data = []
        for fname in sorted(os.listdir(blocks_dir)):
            if fname.endswith(".json"):
                with open(os.path.join(blocks_dir, fname), "r") as f:
                    data.append(json.load(f))
        return data

    def update_block_status(self, chain_folder, block_index, txid=None, status=None):
        # Find file by index
        blocks_dir = os.path.join(CHAINS_DIR, chain_folder, "blocks")
        for fname in os.listdir(blocks_dir):
            if fname.startswith(f"{block_index:05d}_"):
                path = os.path.join(blocks_dir, fname)
                with open(path, "r") as f: block = json.load(f)
                
                if txid: block['txid'] = txid
                if status: block['status'] = status
                
                with open(path, "w") as f: json.dump(block, f, indent=4)
                return block
        return None

    # --- BITCOIN RPC LOGIC ---
    def rpc_call(self, method, params=[]):
        url = f"http://{self.config['rpc_host']}:{self.config['rpc_port']}"
        headers = {'content-type': 'application/json'}
        payload = {
            "method": method,
            "params": params,
            "jsonrpc": "2.0",
            "id": 0,
        }
        auth = (self.config['rpc_user'], self.config['rpc_pass'])
        
        try:
            response = requests.post(url, data=json.dumps(payload), headers=headers, auth=auth, timeout=5)
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def verify_on_chain(self, txid, expected_hash):
        """
        1. Fetch Tx
        2. Extract Pubkeys from P2PK outputs
        3. Reassemble bits (simulated for now based on xgrind spec)
        4. Compare to expected_hash
        """
        # 1. Get Transaction
        res = self.rpc_call("getrawtransaction", [txid, True]) # verbose=True
        if res.get('error'): return False, f"RPC Error: {res['error']}"
        
        tx = res['result']
        if not tx: return False, "Tx not found in node mempool/blocks."
        
        # 2. Extract Data (Obscurity Logic)
        # We assume 1-input, 8-outputs P2PK.
        # We look for outputs with scriptPubKey type 'pubkey' or just grab raw hex
        
        extracted_bits = ""
        logs = []
        
        for vout in tx.get('vout', []):
            spk = vout['scriptPubKey']
            # P2PK asm format: "PUSH <pubkey> OP_CHECKSIG"
            # raw hex format: 21<33-byte-key>ac
            
            hex_spk = spk.get('hex', '')
            
            # Simple heuristic for P2PK compressed key (35 bytes: 21 + 33bytes + ac)
            if len(hex_spk) == 70 and hex_spk.startswith("21") and hex_spk.endswith("ac"):
                pubkey = hex_spk[2:68] # Extract 33 bytes (66 hex chars)
                
                # RECOVERY LOGIC (xgrind style):
                # Take bytes 1-5 (4 bytes) of the pubkey.
                # pubkey hex: 02/03 + X(32bytes).
                # Indices: 0-2 prefix, 2-10 is the first 4 bytes of X.
                payload_chunk = pubkey[2:10] 
                extracted_bits += payload_chunk
                logs.append(f"Out #{vout['n']}: Found key {pubkey[:10]}... -> Chunk: {payload_chunk}")
        
        # 3. Compare
        # Note: In a real run, we'd need exact ordering mapping. 
        # For Hackathon, we check if the expected hash is IN the extracted stream.
        
        if expected_hash in extracted_bits:
            return True, "\n".join(logs) + "\n\nSUCCESS: Block Hash found in Transaction outputs!"
        else:
            # Fallback for demo if you aren't actually mining:
            # If the Tx exists, we might just say "Linked" for the demo unless you actually grinded.
            return False, "\n".join(logs) + f"\n\nFAIL: Reconstructed {extracted_bits[:16]}... != {expected_hash[:16]}..."

    def get_keystore_files(self):
        if not os.path.exists(KEYSTORE_DIR): return []
        return sorted([f for f in os.listdir(KEYSTORE_DIR)])