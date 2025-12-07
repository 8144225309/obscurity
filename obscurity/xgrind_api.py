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
        # 1. Smart Path Discovery
        self.binary_path = self._find_binary(binary_path)
        self.num_workers = num_workers
        self.difficulty_bits = difficulty_bits
        self.chunk_bytes = difficulty_bits // 8
        
        # Ensure executable permissions
        subprocess.run(["chmod", "+x", self.binary_path], stderr=subprocess.DEVNULL)

    def _find_binary(self, user_path):
        if user_path and os.path.exists(user_path): return os.path.abspath(user_path)
        possible_paths = ["./xgrind_gpu", "./xgrind/xgrind_gpu", "../xgrind/xgrind_gpu", "xgrind_gpu"]
        for p in possible_paths:
            if os.path.exists(p): return os.path.abspath(p)
        raise FileNotFoundError(f"Binary 'xgrind_gpu' not found.")

    def _worker_process(self, worker_id, work_queue, result_dict, callback):
        try:
            # Start persistent C process
            proc = subprocess.Popen(
                [self.binary_path, "grind_stream", str(self.difficulty_bits)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, text=True, bufsize=1
            )
        except Exception as e:
            if callback: callback("error", f"Worker {worker_id} failed: {e}")
            return

        while True:
            try:
                task = work_queue.get(timeout=0.5) 
                if task is None: break 
                
                idx, chunk_data = task
                
                # Padding & Formatting
                if len(chunk_data) < self.chunk_bytes:
                    chunk_data = chunk_data + b'\x00' * (self.chunk_bytes - len(chunk_data))
                hex_payload = binascii.hexlify(chunk_data).decode('utf-8')
                target_hex = hex_payload.ljust(8, '0')

                # Benchmark
                start_t = time.time()
                proc.stdin.write(target_hex + "\n")
                proc.stdin.flush()

                # Read Result (Blocking)
                line = proc.stdout.readline().strip()
                duration = time.time() - start_t
                
                if line:
                    parts = line.split()
                    if len(parts) >= 3:
                        priv, pub, attempts = parts[0], parts[1], int(parts[2])
                        
                        # Calculate Hashrate (Guesses per Second)
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
        
        # Calculate chunks
        total_chunks = (len(data_bytes) + self.chunk_bytes - 1) // self.chunk_bytes
        if status_callback: status_callback("info", f"Grinding {len(data_bytes)} bytes ({total_chunks} keys)...")

        # Fill Queue
        for i in range(0, len(data_bytes), self.chunk_bytes):
            work_queue.put((i // self.chunk_bytes, data_bytes[i : i + self.chunk_bytes]))

        # Launch Workers
        threads = []
        for i in range(self.num_workers):
            t = threading.Thread(target=self._worker_process, args=(i, work_queue, results, status_callback))
            t.start(); threads.append(t)

        work_queue.join()
        for _ in range(self.num_workers): work_queue.put(None)
        for t in threads: t.join()

        # Order results
        return [results[i] for i in range(total_chunks) if i in results]

# --- CLI EXECUTION ---
if __name__ == "__main__":
    # Namecoin Block #19200
    DEFAULT_HASH = "d8a7c3e01e1e95bcee015e6fcc7583a2ca60b79e5a3aa0a171eddd344ada903d"
    
    target_hex = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HASH
    target_hex = target_hex.replace("0x", "").replace(" ", "").strip()
    
    # Pretty Logger
    def console_logger(msg_type, data):
        if msg_type == "success":
            mkeys = data['gps'] / 1_000_000
            print(f"[+] Key {data['index']+1} (Worker {data['worker']}): {data['duration']}s | {data['attempts']} guesses | Speed: {mkeys:.2f} M/s")
        elif msg_type == "info":
            print(f"[*] {data}")
        elif msg_type == "error":
            print(f"[!] {data}")

    print(f"--- XGRIND 4090 NITRO DRIVER ---")
    print(f"Target: {target_hex[:16]}...")
    print(f"Config: 4 Workers | 32 Bits | Auto-Balancing")
    print("="*60)
    
    miner = XGrindMiner()
    start = time.time()
    keys = miner.grind(binascii.unhexlify(target_hex), console_logger)
    total = time.time() - start
    
    print("="*60)
    print(f"[*] DONE in {total:.2f} seconds")
    print("="*60)
    print(json.dumps(keys, indent=2))