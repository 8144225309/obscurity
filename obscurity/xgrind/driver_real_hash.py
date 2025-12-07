import subprocess
import binascii
import sys
import os
import time

# --- CONFIG ---
XGRIND_BIN = os.path.abspath("./xgrind_gpu") 
# BUMPING DIFFICULTY TO 32 BITS (4 BYTES)
# This is 256x harder than before, but the 4090 eats it for breakfast.
DIFFICULTY_BITS = 32  
CHUNK_BYTES = DIFFICULTY_BITS // 8 

def main():
    if not os.path.exists(XGRIND_BIN):
        print(f"[!] Error: Binary not found at {XGRIND_BIN}")
        return
    subprocess.run(["chmod", "+x", XGRIND_BIN])

    print(f"[*] Starting GPU Grinder (Targeting {DIFFICULTY_BITS} bits / 4 bytes per key)...")
    
    # Start the C binary in stream mode
    proc = subprocess.Popen(
        [XGRIND_BIN, "grind_stream", str(DIFFICULTY_BITS)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr, 
        text=True,
        bufsize=1
    )

    # --- REAL NAMECOIN BLOCK HASH ---
    # This is the hash of Namecoin Block #19200 (First AuxPOW block)
    # Hex: d8a7c3e01e1e95bcee015e6fcc7583a2ca60b79e5a3aa0a171eddd344ada903d
    # 64 hex chars = 32 bytes
    real_hash_hex = "d8a7c3e01e1e95bcee015e6fcc7583a2ca60b79e5a3aa0a171eddd344ada903d"
    payload = binascii.unhexlify(real_hash_hex)

    print(f"[*] Target Hash: {real_hash_hex}")
    print(f"[*] Size: {len(payload)} bytes")
    print(f"[*] Expected Keys: {len(payload)} / {CHUNK_BYTES} = {len(payload)//CHUNK_BYTES} keys")
    print("---------------------------------------------")

    results = []
    start_time = time.time()

    try:
        for i in range(0, len(payload), CHUNK_BYTES):
            chunk_start = time.time()
            
            # Get 4-byte chunk
            chunk = payload[i : i + CHUNK_BYTES]
            
            # Pad if necessary (though a 32-byte hash fits perfectly into 4-byte chunks)
            if len(chunk) < CHUNK_BYTES:
                chunk = chunk + b'\x00' * (CHUNK_BYTES - len(chunk))

            # Convert to hex for the C program
            hex_payload = binascii.hexlify(chunk).decode('utf-8')
            # Pad to 8 chars (32 bits) for alignment
            target_hex = hex_payload.ljust(8, '0') 

            # Send to GPU
            proc.stdin.write(target_hex + "\n")
            proc.stdin.flush()

            # Wait for GPU
            line = proc.stdout.readline().strip()
            if not line: break
            
            parts = line.split()
            if len(parts) < 2: continue

            pub_key = parts[1]
            elapsed = time.time() - chunk_start
            
            print(f"Key {i//CHUNK_BYTES + 1}/8 [{hex_payload}] -> {pub_key} ({elapsed:.2f}s)")
            results.append(pub_key)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        if proc.poll() is None:
            proc.terminate()
            
    total_time = time.time() - start_time
    print("\n[+] MERGE MINE READY")
    print(f"[+] Generated 8 keys in {total_time:.2f} seconds")
    print("---------------------------------------------")
    # Print raw list for easy copying
    for k in results:
        print(k)

if __name__ == "__main__":
    main()