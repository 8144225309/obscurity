import os
import json
import uuid
import time

# Constants
DATA_DIR = "obscurity_data"
CHAINS_DIR = os.path.join(DATA_DIR, "chains")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

class DataManager:
    def __init__(self):
        self.ensure_directories()

    def ensure_directories(self):
        """Creates the base folder structure if missing."""
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(CHAINS_DIR):
            os.makedirs(CHAINS_DIR)
        
        # Default Config
        if not os.path.exists(CONFIG_FILE):
            default_config = {
                "rpc_host": "127.0.0.1",
                "rpc_port": 8332,
                "rpc_user": "",
                "rpc_pass": "",
                "data_dir": os.path.join(os.getenv('APPDATA'), "Bitcoin") if os.name == 'nt' else ""
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(default_config, f, indent=4)

    def get_chains(self):
        """Returns a list of chain folders."""
        if not os.path.exists(CHAINS_DIR):
            return []
        # Return directory names in chains/
        return [d for d in os.listdir(CHAINS_DIR) if os.path.isdir(os.path.join(CHAINS_DIR, d))]

    def create_new_chain(self, name):
        """Creates a new chain folder, meta file, and anchor block."""
        # 1. Generate ID and folder name
        chain_id = str(uuid.uuid4())[:8]
        safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).strip()
        folder_name = f"{safe_name}_{chain_id}"
        chain_path = os.path.join(CHAINS_DIR, folder_name)
        
        os.makedirs(chain_path)
        os.makedirs(os.path.join(chain_path, "blocks"))

        # 2. Create Chain Meta
        meta = {
            "name": name,
            "id": chain_id,
            "created_at": time.time(),
            "fork_source": None
        }
        with open(os.path.join(chain_path, "chain_meta.json"), "w") as f:
            json.dump(meta, f, indent=4)

        # 3. Create Anchor Block (Index 0)
        anchor_block = {
            "index": 0,
            "is_anchor": True,
            "block_hash": "0000000000000000000000000000000000000000000000000000000000000000",
            "prev_hash": None,
            "payload": {"type": "text", "data": "Genesis Anchor"},
            "status": "unlinked"
        }
        with open(os.path.join(chain_path, "blocks", "00000_anchor.json"), "w") as f:
            json.dump(anchor_block, f, indent=4)
            
        return folder_name

    def load_blocks(self, chain_folder):
        """Reads all blocks for a given chain."""
        blocks_dir = os.path.join(CHAINS_DIR, chain_folder, "blocks")
        if not os.path.exists(blocks_dir):
            return []
        
        blocks = []
        files = sorted(os.listdir(blocks_dir))
        for filename in files:
            if filename.endswith(".json"):
                with open(os.path.join(blocks_dir, filename), "r") as f:
                    blocks.append(json.load(f))
        return blocks