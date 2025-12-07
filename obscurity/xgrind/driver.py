import subprocess
import binascii
import sys
import os

# --- CONFIG ---
# Ensure this matches your binary name
XGRIND_BIN = os.path.abspath("./xgrind_gpu") 
DIFFICULTY_BITS = 24  # 24 bits = 3 bytes (Fast)
CHUNK_BYTES = DIFFICULTY_BITS // 8 

def main():
    # 1. Make binary executable just in case
    subprocess.run(["chmod", "+x", XGRIND_BIN])

    # 2. Start GPU Process
    print(f"[*] Starting GPU Grinder (Targeting {DIFFICULTY_BITS} bits)...")
    proc = subprocess.Popen(
        [XGRIND_BIN, "grind_stream", str(DIFFICULTY_BITS)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True,
        bufsize=1  # Line buffered
    )

    # 3. Your Data (The "Stamp")
    payload = b"HackThePlanet2025" 
    print(f"[*] Payload: {payload}")

    try:
        for i in range(0, len(payload), CHUNK_BYTES):
            # Get 3-byte chunk
            chunk = payload[i : i + CHUNK_BYTES]
            
            # Pad if this is the last short chunk
            if len(chunk) < CHUNK_BYTES:
                chunk = chunk + b'\x00' * (CHUNK_BYTES - len(chunk))

            # --- THE MAGIC FIX ---
            # Pad to 8 chars (32 bits) so C reads it into the TOP bits
            hex_payload = binascii.hexlify(chunk).decode('utf-8')
            target_hex = hex_payload.ljust(8, '0') 

            # Send to GPU
            proc.stdin.write(target_hex + "\n")
            proc.stdin.flush()

            # Read Result
            line = proc.stdout.readline().strip()
            if not line: break
            
            # Output: priv pub attempts
            parts = line.split()
            print(f"Chunk {i//CHUNK_BYTES}: {hex_payload} -> PubKey: {parts[1]}")

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        proc.terminate()

if __name__ == "__main__":
    main()