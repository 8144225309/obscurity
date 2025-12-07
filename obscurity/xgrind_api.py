import subprocess
import binascii
import sys
import os
import time
import threading
import json
from queue import Queue

# --- CONFIG ---
# Default settings optimized for RTX 4090
DEFAULT_WORKERS = 4 
DEFAULT_DIFFICULTY = 32 

class XGrindMiner:
    def __init__(self, binary_path=None, num_workers=DEFAULT_WORKERS, difficulty_bits=DEFAULT_DIFFICULTY):
        self.num_workers = num_workers
        self.difficulty_bits = difficulty_bits
        self.chunk_bytes = difficulty_bits // 8
        
        # 1. Find the binary (even if it's a Linux file on Windows)
        self.binary_path = self._find_binary(binary_path)
        
        # 2. Determine execution mode
        self.use_wsl = False
        if os.name == 'nt':
            # On Windows, we assume the binary is a Linux executable run via WSL
            self.use_wsl = True
            print(f"[INFO] Windows detected. Bridging to WSL to run: {self.binary_path}")
        else:
            # On Linux, just ensure it's executable
            subprocess.run(["chmod", "+x", self.binary_path], stderr=subprocess.DEVNULL)

    def _find_binary(self, user_path):
        # Trust user path if given
        if user_path and os.path.exists(user_path): 
            return os.path.abspath(user_path)

        # Standard locations
        current_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths = [
            os.path.join(current_dir, "xgrind", "xgrind_gpu"),      # ./xgrind/xgrind_gpu
            os.path.join(current_dir, "xgrind_gpu"),                # ./xgrind_gpu
            os.path.join(current_dir, "..", "xgrind", "xgrind_gpu"),# ../xgrind/xgrind_gpu
            "xgrind_gpu"
        ]

        for p in possible_paths:
            if os.path.exists(p): 
                return p # Return the path even if Windows thinks it's not executable
        
        # If we are on Windows, check for .exe too (just in case you actually compiled for Windows)
        if os.name == 'nt':
            for p in possible_paths:
                if os.path.exists(p + ".exe"): return p + ".exe"

        raise FileNotFoundError(f"Binary 'xgrind_gpu' not found. Checked: {possible_paths}")

    def _worker_process(self, worker_id, work_queue, result_dict, callback):
        try:
            # Build Command
            cmd = []
            if self.use_wsl:
                # Convert Windows path to WSL friendly relative path if possible, 
                # or just rely on WSL preserving CWD.
                # Simplest strategy: Use 'wsl' + 'relative path to binary'
                # We assume xgrind_api.py is in the same project root as the binary folder
                
                # Make path relative to CWD to avoid /mnt/c/... confusion if possible
                try:
                    rel_path = os.path.relpath(self.binary_path)
                    # Force forward slashes for Linux
                    linux_path = "./" + rel_path.replace("\\", "/")
                    cmd = ["wsl", linux_path]
                except:
                    # Fallback to just passing the filename and hoping it's in path? 
                    # No, let's try just calling wsl with the absolute path converted
                    cmd = ["wsl", self.binary_path.replace("\\", "/")]
            else:
                cmd = [self.binary_path]

            # Add Arguments
            cmd.extend(["grind_stream", str(self.difficulty_bits)])

            # Start persistent process
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=sys.stderr, 
                text=True, 
                bufsize=1
            )
        except Exception as e:
            if callback: callback("error", f"Worker {worker_id} failed start: {e}")
            return

        while True:
            try:
                task = work_queue.get(timeout=0.5) 
                if task is None: break 
                
                idx, chunk_data = task
                
                # Padding
                if len(chunk_data) < self.chunk_bytes:
                    chunk_data = chunk_data + b'\x00' * (self.chunk_bytes - len(chunk_data))
                
                hex_payload = binascii.hexlify(chunk_data).decode('utf-8')
                target_hex = hex_payload.ljust(8, '0')

                # Send to GPU
                start_t = time.time()
                proc.stdin.write(target_hex + "\n")
                proc.stdin.flush()

                # Read Result
                line = proc.stdout.readline().strip()
                duration = time.time() - start_t
                
                if line:
                    parts = line.split()
                    if len(parts) >= 3:
                        priv, pub, attempts = parts[0], parts[1], int(parts[2])
                        gps = attempts / duration if duration > 0 else 0
                        
                        result_dict[idx] = pub
                        if callback:
                            callback("success", {
                                "worker": worker_id,
                                "index": idx,
                                "payload": hex_payload,
                                "pubkey": pub,
                                "duration": round(duration, 2),
                                "attempts": attempts,
                                "gps": int(gps)
                            })
                work_queue.task_done()
            except:
                if work_queue.empty(): break

        if proc.poll() is None: proc.terminate()

    def grind(self, data_bytes, status_callback=None):
        results = {}
        work_queue = Queue()
        
        total_chunks = (len(data_bytes) + self.chunk_bytes - 1) // self.chunk_bytes
        if status_callback: status_callback("info", f"Grinding {len(data_bytes)} bytes ({total_chunks} keys)...")

        for i in range(0, len(data_bytes), self.chunk_bytes):
            work_queue.put((i // self.chunk_bytes, data_bytes[i : i + self.chunk_bytes]))

        threads = []
        for i in range(self.num_workers):
            t = threading.Thread(target=self._worker_process, args=(i, work_queue, results, status_callback))
            t.start(); threads.append(t)

        work_queue.join()
        for _ in range(self.num_workers): work_queue.put(None)
        for t in threads: t.join()

        return [results[i] for i in range(total_chunks) if i in results]

# --- CLI EXECUTION ---
if __name__ == "__main__":
    DEFAULT_HASH = "d8a7c3e01e1e95bcee015e6fcc7583a2ca60b79e5a3aa0a171eddd344ada903d"
    target_hex = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HASH
    target_hex = target_hex.replace("0x", "").replace(" ", "").strip()
    
    def console_logger(msg_type, data):
        if msg_type == "success":
            mkeys = data['gps'] / 1_000_000
            print(f"[+] Key {data['index']+1} (Worker {data['worker']}): {data['duration']}s | Speed: {mkeys:.2f} M/s")
        elif msg_type == "error":
            print(f"[!] {data}")

    print(f"--- XGRIND API DRIVER ---")
    try:
        miner = XGrindMiner()
        print(f"[*] Binary Found: {miner.binary_path}")
        print(f"[*] Mode: {'WSL Bridge' if miner.use_wsl else 'Native'}")
        miner.grind(binascii.unhexlify(target_hex), console_logger)
    except Exception as e:
        print(f"[FATAL] {e}")