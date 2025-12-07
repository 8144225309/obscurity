import os
import json
import uuid
import time
import hashlib
import requests
import secrets
import math
import shutil
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# --- INTEGRATION: IMPORT THE NEW MINER API ---
try:
    from xgrind_api import XGrindMiner
except ImportError:
    print("[WARNING] xgrind_api.py not found. Grinding will be disabled.")
    XGrindMiner = None

# --- CONSTANTS ---
DATA_DIR = "obscurity_data"
CHAINS_DIR = os.path.join(DATA_DIR, "chains")
KEYSTORE_DIR = os.path.join(DATA_DIR, "keystore")
LOCKBOX_DIR = os.path.join(DATA_DIR, "lockboxes") 
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

class DataManager:
    def __init__(self):
        self.ensure_directories()
        self.config = self.load_config()
        
        # Initialize Miner (Default 4 Workers for RTX 4090)
        self.miner = None
        self.miner_available = False
        if XGrindMiner:
            try:
                self.miner = XGrindMiner(num_workers=4)
                self.miner_available = True
            except Exception as e:
                print(f"[Warning] Miner binary problem: {e}")

    def ensure_directories(self):
        for d in [DATA_DIR, CHAINS_DIR, KEYSTORE_DIR, LOCKBOX_DIR]:
            if not os.path.exists(d): os.makedirs(d)
            if d == KEYSTORE_DIR and not os.path.exists(os.path.join(d, "README.txt")):
                 with open(os.path.join(d, "README.txt"), "w") as f:
                    f.write("Obscurity Key Storage (Raw).\n")

        if not os.path.exists(CONFIG_FILE):
            default_config = {
                "rpc_host": "127.0.0.1", "rpc_port": 8332, "rpc_user": "user", "rpc_pass": "pass",
                "data_dir": os.path.expanduser("~/.bitcoin")
            }
            with open(CONFIG_FILE, 'w') as f: json.dump(default_config, f, indent=4)

    def load_config(self):
        with open(CONFIG_FILE, 'r') as f: return json.load(f)

    def save_config(self, new_conf):
        self.config.update(new_conf)
        with open(CONFIG_FILE, 'w') as f: json.dump(self.config, f, indent=4)

    # --- ENCRYPTION ENGINE (AES-256-GCM) ---
    def _derive_key(self, password_str):
        return hashlib.sha256(password_str.encode()).digest()

    def encrypt_data(self, password, raw_bytes):
        key = self._derive_key(password)
        aesgcm = AESGCM(key)
        nonce = secrets.token_bytes(12) 
        ciphertext_with_tag = aesgcm.encrypt(nonce, raw_bytes, None)
        tag = ciphertext_with_tag[-16:]
        ciphertext = ciphertext_with_tag[:-16]
        return ciphertext.hex(), nonce.hex(), tag.hex()

    def decrypt_data(self, password, ciphertext_hex, nonce_hex, tag_hex):
        try:
            key = self._derive_key(password)
            aesgcm = AESGCM(key)
            nonce = bytes.fromhex(nonce_hex)
            ciphertext = bytes.fromhex(ciphertext_hex)
            tag = bytes.fromhex(tag_hex)
            data = aesgcm.decrypt(nonce, ciphertext + tag, None)
            return data
        except Exception as e:
            print(f"Decryption failed: {e}")
            return None

    # --- ANCHOR & FORK MANAGEMENT ---
    def get_chains(self):
        if not os.path.exists(CHAINS_DIR): return []
        chains = []
        for d in os.listdir(CHAINS_DIR):
            path = os.path.join(CHAINS_DIR, d)
            if os.path.isdir(path):
                meta_path = os.path.join(path, "chain_meta.json")
                if os.path.exists(meta_path):
                    with open(meta_path, 'r') as f:
                        meta = json.load(f)
                        meta['folder'] = d
                        chains.append(meta)
        return chains

    def create_anchor(self, name):
        chain_id = str(uuid.uuid4())[:8]
        safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).strip()
        folder_name = f"{safe_name}_{chain_id}"
        chain_path = os.path.join(CHAINS_DIR, folder_name)
        os.makedirs(os.path.join(chain_path, "blocks"))
        meta = {"name": name, "id": chain_id, "type": "anchor", "created_at": time.time()}
        with open(os.path.join(chain_path, "chain_meta.json"), "w") as f:
            json.dump(meta, f, indent=4)
        return folder_name

    def fork_chain(self, source_chain_folder, target_block_index, new_name):
        new_chain_id = str(uuid.uuid4())[:8]
        safe_name = "".join([c for c in new_name if c.isalnum() or c in (' ', '_', '-')]).strip()
        new_folder_name = f"{safe_name}_{new_chain_id}"
        new_chain_path = os.path.join(CHAINS_DIR, new_folder_name)
        os.makedirs(os.path.join(new_chain_path, "blocks"))
        
        source_blocks_dir = os.path.join(CHAINS_DIR, source_chain_folder, "blocks")
        for fname in sorted(os.listdir(source_blocks_dir)):
            if fname.endswith(".json"):
                try:
                    idx = int(fname.split("_")[0])
                    if idx <= target_block_index:
                        shutil.copy2(os.path.join(source_blocks_dir, fname), os.path.join(new_chain_path, "blocks", fname))
                except: continue

        meta = {"name": new_name, "id": new_chain_id, "type": "fork", "parent_chain": source_chain_folder, "fork_index": target_block_index, "created_at": time.time()}
        with open(os.path.join(new_chain_path, "chain_meta.json"), "w") as f:
            json.dump(meta, f, indent=4)
        return new_folder_name

    def load_blocks(self, chain_folder):
        blocks_dir = os.path.join(CHAINS_DIR, chain_folder, "blocks")
        if not os.path.exists(blocks_dir): return []
        data = []
        for fname in sorted(os.listdir(blocks_dir)):
            if fname.endswith(".json"):
                with open(os.path.join(blocks_dir, fname), "r") as f: data.append(json.load(f))
        return data

    # --- BLOCK FACTORY ---
    def commit_block(self, chain_folder, index, prev_hash, data_bytes, filename="data.bin"):
        chain_id = chain_folder.split('_')[-1]
        content_hash = hashlib.sha256(data_bytes).hexdigest()
        cipher_hex, nonce_hex, tag_hex = self.encrypt_data(chain_id, data_bytes)
        
        hasher = hashlib.sha256()
        hasher.update(str(index).encode())
        hasher.update(str(prev_hash).encode())
        hasher.update(bytes.fromhex(cipher_hex)) 
        block_hash = hasher.hexdigest()

        is_anchor = (index == 0)
        block_data = {
            "header": {
                "index": index,
                "is_anchor": is_anchor,
                "block_hash": block_hash,
                "prev_hash": prev_hash,
                "timestamp": time.time(),
                "status": "unlinked",
                "txid": None
            },
            "content": {
                "type": "file" if len(data_bytes) > 500 else "text",
                "filename": filename,
                "size_bytes": len(data_bytes),
                "content_hash_sha256": content_hash,
                "preview": data_bytes.decode('utf-8', errors='ignore') if len(data_bytes) < 200 else None
            },
            "encryption": {
                "algo": "AES-256-GCM",
                "ciphertext_hex": cipher_hex,
                "nonce_hex": nonce_hex,
                "tag_hex": tag_hex,
                "key_used": chain_id
            },
            "steganography": {
                "engine": "xgrind_4090",
                "status": "pending",
                "difficulty_bits": 0,
                "keys": [] 
            }
        }
        
        filename_json = f"{index:05d}_{block_hash[:8]}.json"
        path = os.path.join(CHAINS_DIR, chain_folder, "blocks", filename_json)
        with open(path, "w") as f: json.dump(block_data, f, indent=4)
        return block_data

    # --- GRINDER EXECUTION ---
    def run_grinder(self, chain_folder, block_index, difficulty_bits, num_workers, progress_callback):
        """
        Grinds keys and generates the .lockbox artifact.
        Now accepts 'num_workers' to tune 4090 usage.
        """
        if not self.miner_available:
            return False, "Miner binary missing."

        blocks_dir = os.path.join(CHAINS_DIR, chain_folder, "blocks")
        target_block = None
        target_fname = None
        
        for fname in os.listdir(blocks_dir):
            if fname.startswith(f"{block_index:05d}_"):
                target_fname = fname
                with open(os.path.join(blocks_dir, fname), "r") as f:
                    target_block = json.load(f)
                break
        
        if not target_block: return False, "Block not found"

        cipher_hex = target_block.get("encryption", {}).get("ciphertext_hex", "")
        if not cipher_hex: return False, "No encrypted payload found."
        
        full_payload = bytes.fromhex(cipher_hex)
        chunk_bytes = difficulty_bits // 8
        total_keys = math.ceil(len(full_payload) / chunk_bytes)
        
        def api_callback(msg_type, data):
            if msg_type == "success" and progress_callback:
                idx = data['index'] + 1
                gps_fmt = f"{data['gps']/1_000_000:.1f}M/s"
                msg = f"Key {idx}/{total_keys} (Worker {data['worker']} @ {gps_fmt})"
                progress_callback(idx, total_keys, msg)
            elif msg_type == "error":
                print(f"[API Error] {data}")

        # UPDATE MINER SETTINGS DYNAMICALLY
        self.miner.num_workers = num_workers
        self.miner.difficulty_bits = difficulty_bits
        self.miner.chunk_bytes = chunk_bytes

        try:
            final_keys = self.miner.grind(full_payload, api_callback)
            
            if not final_keys or None in final_keys:
                return False, "Grinding incomplete."

            target_block['steganography']['status'] = "complete"
            target_block['steganography']['difficulty_bits'] = difficulty_bits
            target_block['steganography']['total_chunks'] = len(final_keys)
            target_block['steganography']['keys'] = final_keys
            target_block['header']['status'] = "ready_to_link"
            
            with open(os.path.join(blocks_dir, target_fname), "w") as f:
                json.dump(target_block, f, indent=4)

            lockbox = {
                "version": 1,
                "chain_id": chain_folder.split('_')[-1],
                "block_index": block_index,
                "target_hash": target_block['header']['block_hash'],
                "encryption": target_block['encryption'],
                "keys": final_keys
            }
            lb_name = f"{chain_folder}_blk{block_index}.lockbox"
            with open(os.path.join(LOCKBOX_DIR, lb_name), "w") as f:
                json.dump(lockbox, f, indent=4)

            return True, f"Done. Lockbox saved: {lb_name}"

        except Exception as e:
            return False, f"Grinder Exception: {str(e)}"

    # --- BITCOIN RPC & VERIFICATION (REAL) ---
    def get_auth(self):
        user = self.config.get('rpc_user', '')
        passwd = self.config.get('rpc_pass', '')
        return (user, passwd)

    def rpc_call(self, method, params=[]):
        url = f"http://{self.config['rpc_host']}:{self.config['rpc_port']}"
        payload = {"method": method, "params": params, "jsonrpc": "2.0", "id": 0}
        try:
            return requests.post(url, data=json.dumps(payload), headers={'content-type': 'application/json'}, auth=self.get_auth(), timeout=5).json()
        except Exception as e: return {"error": str(e)}

    def verify_transaction_strict(self, txid, password, iv_hex, salt_tag_hex, difficulty_bits):
        res = self.rpc_call("getrawtransaction", [txid, True])
        if res.get('error'): return False, f"RPC Error: {res['error']}"
        tx = res.get('result')
        if not tx: return False, "Transaction not found on node."

        chunk_bytes = difficulty_bits // 8
        reconstructed_cipher = b""
        logs = [f"Checking TXID: {txid[:8]}..."]
        
        for vout in tx.get('vout', []):
            hex_spk = vout['scriptPubKey'].get('hex', '')
            if len(hex_spk) == 70 and hex_spk.startswith("21") and hex_spk.endswith("ac"):
                pubkey = hex_spk[2:68] 
                payload_chunk = pubkey[2 : 2 + (chunk_bytes * 2)] 
                reconstructed_cipher += bytes.fromhex(payload_chunk)
                logs.append(f"Out #{vout['n']}: {payload_chunk}")

        if not reconstructed_cipher: return False, "No P2PK outputs found."

        logs.append(f"Reconstructed {len(reconstructed_cipher)} bytes.")
        decrypted_data = self.decrypt_data(password, reconstructed_cipher.hex(), iv_hex, salt_tag_hex)

        if decrypted_data:
            return True, "\n".join(logs) + "\n\n[SUCCESS] DECRYPTION CONFIRMED.\nThe data on the blockchain matches your keys exactly."
        else:
            return False, "\n".join(logs) + "\n\n[FAIL] Decryption Failed.\nData mismatch or wrong password."