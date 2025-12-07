import os
import json
import uuid
import time
import hashlib
import requests
import secrets
import subprocess
import sys

# --- CONSTANTS ---
DATA_DIR = "obscurity_data"
CHAINS_DIR = os.path.join(DATA_DIR, "chains")
KEYSTORE_DIR = os.path.join(DATA_DIR, "keystore")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

# Path to the compiled binary (Windows path style for Python, pointing to the moved file)
# We check a few common locations to be safe
POSSIBLE_BINS = [
    os.path.join("obscurity", "keygrinder", "xgrind_gpu"),
    os.path.join("keygrinder", "xgrind_gpu"),
    os.path.join("xgrind", "xgrind_gpu"),
    "xgrind_gpu" # If in PATH
]

# --- OBSCURITY PROTOCOL V1 CONSTANTS ---
PROTOCOL_TAG = b"OBSCURITY_V1"
PROTOCOL_VERSION = 0x01

class DataManager:
    def __init__(self):
        self.ensure_directories()
        self.config = self.load_config()

    def ensure_directories(self):
        for d in [DATA_DIR, CHAINS_DIR, KEYSTORE_DIR]:
            if not os.path.exists(d): os.makedirs(d)
            if d == KEYSTORE_DIR and not os.path.exists(os.path.join(d, "README.txt")):
                 with open(os.path.join(d, "README.txt"), "w") as f:
                    f.write("Obscurity Key Storage.\nWARNING: Handle with care.\n")

        if not os.path.exists(CONFIG_FILE):
            if os.name == 'nt':
                default_data = os.path.join(os.getenv('APPDATA'), "Bitcoin")
            else:
                default_data = os.path.expanduser("~/.bitcoin")
            
            default_config = {
                "rpc_host": "127.0.0.1", "rpc_port": 8332, "rpc_user": "", "rpc_pass": "",
                "data_dir": default_data, "zmq_host": "127.0.0.1", "zmq_port": 28332
            }
            with open(CONFIG_FILE, 'w') as f: json.dump(default_config, f, indent=4)

    def load_config(self):
        with open(CONFIG_FILE, 'r') as f: return json.load(f)

    def save_config(self, new_conf):
        self.config.update(new_conf)
        with open(CONFIG_FILE, 'w') as f: json.dump(self.config, f, indent=4)

    # --- CRYPTO PRIMITIVES (SCRAMBLE V1) ---
    def _compute_mask(self, salt_bytes, block_hash_bytes):
        hasher = hashlib.sha256()
        hasher.update(PROTOCOL_TAG)
        hasher.update(bytes([PROTOCOL_VERSION]))
        hasher.update(salt_bytes)
        hasher.update(block_hash_bytes)
        return hasher.digest()

    def scramble_payload(self, block_hash_hex):
        block_bytes = bytes.fromhex(block_hash_hex)
        salt_bytes = secrets.token_bytes(4) 
        mask_bytes = self._compute_mask(salt_bytes, block_bytes)
        
        int_block = int.from_bytes(block_bytes, "big")
        int_mask = int.from_bytes(mask_bytes, "big")
        int_payload = int_block ^ int_mask
        
        payload_bytes = int_payload.to_bytes(32, "big")
        return payload_bytes.hex(), salt_bytes.hex()

    def unscramble_payload(self, payload_hex, salt_hex, block_hash_hex):
        payload_bytes = bytes.fromhex(payload_hex)
        salt_bytes = bytes.fromhex(salt_hex)
        expected_block_bytes = bytes.fromhex(block_hash_hex)
        
        mask_bytes = self._compute_mask(salt_bytes, expected_block_bytes)
        
        int_payload = int.from_bytes(payload_bytes, "big")
        int_mask = int.from_bytes(mask_bytes, "big")
        int_recovered = int_payload ^ int_mask
        
        recovered_bytes = int_recovered.to_bytes(32, "big")
        return recovered_bytes == expected_block_bytes

    # --- GRINDER ENGINE ---
    def run_grinder(self, chain_folder, block_index, difficulty_bits, progress_callback):
        """
        Drives the xgrind_gpu binary.
        difficulty_bits: Integer (1-32) from the UI slider.
        """
        # 1. Locate Binary
        grinder_bin = None
        for p in POSSIBLE_BINS:
            if os.path.exists(p):
                grinder_bin = p
                break
        
        if not grinder_bin:
            return False, f"Binary not found. Looked in: {POSSIBLE_BINS}"

        # 2. Load Block Targets
        blocks_dir = os.path.join(CHAINS_DIR, chain_folder, "blocks")
        target_block = None
        target_fname = None
        
        for fname in os.listdir(blocks_dir):
            if fname.startswith(f"{block_index:05d}_"):
                target_fname = fname
                with open(os.path.join(blocks_dir, fname), "r") as f:
                    target_block = json.load(f)
                break
        
        if not target_block:
            return False, "Block not found"

        chunks = target_block.get("scramble_v1", {}).get("chunks", [])
        if not chunks:
            return False, "No scramble data found. Compute hash first."

        # 3. Prepare Keystore
        keystore_filename = f"{chain_folder}_blk{block_index}_keys.txt"
        keystore_path = os.path.join(KEYSTORE_DIR, keystore_filename)

        # 4. Launch Process
        # Note: We pass the difficulty bits as a command line argument
        cmd = [grinder_bin, "grind_stream", str(difficulty_bits)]
        
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, # Capture stderr to ignore status messages
                text=True,
                bufsize=1 
            )
        except Exception as e:
            return False, f"Failed to start process: {e}"

        pubkeys = []
        
        # 5. Stream Loop
        try:
            with open(keystore_path, "w") as f_keys:
                f_keys.write(f"# Keystore for {chain_folder} Block {block_index}\n")
                f_keys.write(f"# Difficulty: {difficulty_bits} bits\n")
                f_keys.write(f"# Format: ChunkIndex PrivKey PubKey Attempts\n")
                
                for i, chunk in enumerate(chunks):
                    if progress_callback:
                        progress_callback(i, 8, f"Grinding chunk {i+1}/8: {chunk}...")

                    # Send to GPU
                    proc.stdin.write(f"{chunk}\n")
                    proc.stdin.flush()

                    # Read Result
                    line = proc.stdout.readline()
                    if not line:
                        # Check stderr if stdout died
                        err = proc.stderr.read()
                        raise Exception(f"Grinder died. Error: {err}")
                    
                    parts = line.strip().split()
                    if len(parts) < 2:
                        raise Exception(f"Malformed output: {line}")

                    priv_hex = parts[0]
                    pub_hex = parts[1]
                    attempts = parts[2] if len(parts) > 2 else "0"

                    # SECURE WRITE
                    f_keys.write(f"{i} {priv_hex} {pub_hex} {attempts}\n")
                    f_keys.flush()

                    pubkeys.append(pub_hex)

            proc.terminate()
            
            # Save PubKeys to Block
            target_block['grind_data'] = pubkeys
            target_block['grind_difficulty'] = difficulty_bits
            target_block['status'] = "ready_to_link"
            with open(os.path.join(blocks_dir, target_fname), "w") as f:
                json.dump(target_block, f, indent=4)

            return True, "Grinding Complete. Keys saved."

        except Exception as e:
            proc.kill()
            return False, str(e)

    # --- CHAIN MANAGEMENT ---
    def get_chains(self):
        if not os.path.exists(CHAINS_DIR): return []
        return [d for d in os.listdir(CHAINS_DIR) if os.path.isdir(os.path.join(CHAINS_DIR, d))]

    def create_new_chain(self, name):
        chain_id = str(uuid.uuid4())[:8]
        safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).strip()
        folder_name = f"{safe_name}_{chain_id}"
        chain_path = os.path.join(CHAINS_DIR, folder_name)
        os.makedirs(os.path.join(chain_path, "blocks"))
        
        meta = {"name": name, "id": chain_id, "created_at": time.time()}
        with open(os.path.join(chain_path, "chain_meta.json"), "w") as f:
            json.dump(meta, f, indent=4)

        self.create_block(folder_name, 0, None, "Genesis Anchor", is_anchor=True)
        return folder_name

    def create_example_chains(self):
        name = "Demo_Chain_Alpha"
        folder = self.create_new_chain(name)
        b0 = self.load_blocks(folder)[0]
        self.create_block(folder, 1, b0['block_hash'], "Hello Hackathon Judges!", is_anchor=False)
        return folder

    def create_block(self, chain_folder, index, prev_hash, payload_data, is_anchor=False):
        hasher = hashlib.sha256()
        hasher.update(str(index).encode())
        hasher.update(str(prev_hash).encode())
        hasher.update(str(payload_data).encode())
        block_hash = hasher.hexdigest()

        scrambled_payload, salt = self.scramble_payload(block_hash)

        block_data = {
            "index": index,
            "is_anchor": is_anchor,
            "block_hash": block_hash,
            "prev_hash": prev_hash,
            "payload": payload_data,
            "scramble_v1": {
                "salt": salt,
                "scrambled_hex": scrambled_payload,
                "chunks": [scrambled_payload[i:i+8] for i in range(0, 64, 8)]
            },
            "status": "unlinked",
            "txid": None,
            "grind_data": []
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
                with open(os.path.join(blocks_dir, fname), "r") as f: data.append(json.load(f))
        return data

    def update_block_status(self, chain_folder, block_index, txid=None, status=None):
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

    # --- BITCOIN RPC ---
    def get_auth(self):
        user = self.config.get('rpc_user', '')
        passwd = self.config.get('rpc_pass', '')
        if user and passwd: return (user, passwd)
        datadir = self.config.get('data_dir', '')
        cookie_path = os.path.join(datadir, ".cookie")
        if os.path.exists(cookie_path):
            try:
                with open(cookie_path, 'r') as f:
                    c = f.read().strip()
                if ':' in c: return c.split(':', 1)
            except: pass
        return None

    def rpc_call(self, method, params=[]):
        url = f"http://{self.config['rpc_host']}:{self.config['rpc_port']}"
        payload = {"method": method, "params": params, "jsonrpc": "2.0", "id": 0}
        try:
            return requests.post(url, data=json.dumps(payload), headers={'content-type': 'application/json'}, auth=self.get_auth(), timeout=5).json()
        except Exception as e: return {"error": str(e)}

    def test_rpc_connection(self):
        res = self.rpc_call("getblockchaininfo", [])
        if 'error' in res and res['error']: return False, f"RPC Error: {res['error']}"
        if 'result' in res: return True, f"Connected! Chain: {res['result'].get('chain')}"
        return False, "Connection failed"

    def verify_on_chain(self, txid, expected_hash, salt_hex):
        res = self.rpc_call("getrawtransaction", [txid, True])
        if res.get('error'): return False, f"RPC Error: {res['error']}"
        tx = res.get('result')
        if not tx: return False, "Tx not found."
        
        extracted_hex = ""
        logs = []
        
        for vout in tx.get('vout', []):
            hex_spk = vout['scriptPubKey'].get('hex', '')
            if len(hex_spk) == 70 and hex_spk.startswith("21") and hex_spk.endswith("ac"):
                pubkey = hex_spk[2:68]
                payload_chunk = pubkey[2:10] 
                extracted_hex += payload_chunk
                logs.append(f"Out #{vout['n']}: {payload_chunk}")

        if len(extracted_hex) < 64:
             return False, "\n".join(logs) + f"\n\nFAIL: Insufficient P2PK outputs."

        candidate_payload = extracted_hex[:64]
        is_valid = self.unscramble_payload(candidate_payload, salt_hex, expected_hash)
        
        if is_valid:
            return True, "\n".join(logs) + "\n\nSUCCESS: On-chain data unscrambles to match Block Hash!"
        else:
            return False, "\n".join(logs) + f"\n\nFAIL: Unscramble mismatch."

    def get_keystore_files(self):
        if not os.path.exists(KEYSTORE_DIR): return []
        return sorted([f for f in os.listdir(KEYSTORE_DIR)])