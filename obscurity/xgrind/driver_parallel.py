import subprocess
import binascii
import sys
import os
import time
import threading
from datetime import datetime

# --- CONFIG ---
XGRIND_BIN = os.path.abspath("./xgrind_gpu") 
DIFFICULTY_BITS = 32  # 32 bits = 4 bytes
CHUNK_BYTES = 4       # Must match difficulty (32 bits / 8 = 4 bytes)

# The Namecoin Hash
REAL_HASH_HEX = "d8a7c3e01e1e95bcee015e6fcc7583a2ca60b79e5a3aa0a171eddd344ada903d"

# Shared results dictionary to store keys in order
final_results = {}
print_lock = threading.Lock()

def grind_worker(worker_id, start_index, data_chunk):
    """
    Runs a dedicated instance of xgrind_gpu for a specific subset of data.
    """
    global final_results
    
    # Start a dedicated process for this worker
    proc = subprocess.Popen(
        [XGRIND_BIN, "grind_stream", str(DIFFICULTY_BITS)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr, # Let stderr go to console so you see C++ logs
        text=True,
        bufsize=1
    )

    local_results = []
    
    try:
        # Loop through this worker's assigned data chunk
        for i in range(0, len(data_chunk), CHUNK_BYTES):
            # Calculate the global key index (e.g., Key 0, 1... or Key 4, 5...)
            global_key_idx = start_index + (i // CHUNK_BYTES)
            
            chunk = data_chunk[i : i + CHUNK_BYTES]
            
            # Pad if needed
            if len(chunk) < CHUNK_BYTES:
                chunk = chunk + b'\x00' * (CHUNK_BYTES - len(chunk))

            # Hex encoding
            hex_payload = binascii.hexlify(chunk).decode('utf-8')
            target_hex = hex_payload.ljust(8, '0') 

            # Timing
            key_start = time.time()

            # SEND TO GPU
            proc.stdin.write(target_hex + "\n")
            proc.stdin.flush()

            # READ FROM GPU
            line = proc.stdout.readline().strip()
            if not line: break
            
            parts = line.split()
            if len(parts) >= 2:
                pub_key = parts[1]
                elapsed = time.time() - key_start
                
                # Save to shared dict
                final_results[global_key_idx] = pub_key
                
                with print_lock:
                    print(f"[Worker {worker_id}] Found Key {global_key_idx+1}/8: {hex_payload} -> {pub_key} ({elapsed:.2f}s)")

    except Exception as e:
        with print_lock:
            print(f"[Worker {worker_id}] Error: {e}")
    finally:
        # Clean up process
        if proc.poll() is None:
            proc.terminate()

def main():
    if not os.path.exists(XGRIND_BIN):
        print(f"[!] Error: Binary not found at {XGRIND_BIN}")
        return
    subprocess.run(["chmod", "+x", XGRIND_BIN])

    payload = binascii.unhexlify(REAL_HASH_HEX)
    total_len = len(payload)
    half_len = total_len // 2

    # Split payload into two halves
    part1 = payload[:half_len] # First 16 bytes (Keys 1-4)
    part2 = payload[half_len:] # Last 16 bytes (Keys 5-8)

    print("="*60)
    print(f"[*] PARALLEL NITRO GRINDER: 2 Workers x 4 Keys")
    print(f"[*] Target Hash: {REAL_HASH_HEX}")
    print("="*60)

    start_time = time.time()

    # Create Threads
    t1 = threading.Thread(target=grind_worker, args=(1, 0, part1))
    t2 = threading.Thread(target=grind_worker, args=(2, 4, part2))

    # Launch!
    t1.start()
    t2.start()

    # Wait for both to finish
    t1.join()
    t2.join()

    total_time = time.time() - start_time

    print("\n" + "="*60)
    print(f"[*] DONE! Total Time: {total_time:.2f} seconds")
    print("="*60)
    
    # Print in correct order
    print("\n[+] FINAL MERGE MINE PAYLOAD:")
    keys_found = sorted(final_results.keys())
    for k in keys_found:
        print(final_results[k])

if __name__ == "__main__":
    main()