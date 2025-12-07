import subprocess
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
XGRIND_BIN = os.path.join(SCRIPT_DIR, "xgrind_gpu")

# Your example 32-byte block hash (actually 63 hex chars, we handle that)
BLOCK_HASH_HEX = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26"

CHUNK_BYTES = 3  # 3 bytes = 24 bits per chunk
HEXCHARS = "0123456789abcdefABCDEF"


def main():
    # 1. Check binary exists
    if not os.path.isfile(XGRIND_BIN):
        print(f"[ERROR] xgrind_gpu not found at {XGRIND_BIN}")
        input("Press Enter to exit...")
        return

    # 2. Make sure binary is executable (WSL/Linux)
    try:
        subprocess.run(["chmod", "+x", XGRIND_BIN], check=False)
    except Exception:
        pass

    print("=== xgrind block-hash driver ===")
    print(f"Block hash: {BLOCK_HASH_HEX}\n")

    # 3. Clean up the block hash string
    h = BLOCK_HASH_HEX.strip().replace(" ", "")
    if h.startswith(("0x", "0X")):
        h = h[2:]

    # Keep only hex digits
    clean = "".join(c for c in h if c in HEXCHARS)

    if len(clean) % 2 != 0:
        print(f"[WARN] Block hash has odd number of hex chars ({len(clean)}), "
              "dropping last nibble to make it even.")
        clean = clean[:-1]

    if len(clean) == 0:
        print("[ERROR] Block hash became empty after cleaning.")
        input("Press Enter to exit...")
        return

    # 4. Turn into bytes
    payload = bytes.fromhex(clean)
    print(f"Using {len(payload)} bytes, {CHUNK_BYTES} bytes per chunk\n")

    # 5. Start grinder: ./xgrind_gpu grind_stream
    try:
        proc = subprocess.Popen(
            [XGRIND_BIN, "grind_stream"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        print("[ERROR] Could not start xgrind_gpu")
        input("Press Enter to exit...")
        return

    try:
        chunk_idx = 0
        for i in range(0, len(payload), CHUNK_BYTES):
            chunk = payload[i: i + CHUNK_BYTES]
            if len(chunk) < CHUNK_BYTES:
                chunk = chunk.ljust(CHUNK_BYTES, b"\x00")

            hex_payload = chunk.hex()                  # e.g. "486163"
            target_hex = hex_payload.ljust(8, "0")[:8]  # pad/crop to 8 hex chars

            print(f"--- Chunk {chunk_idx} ---")
            print(f"raw bytes : {hex_payload}")
            print(f"target hex: {target_hex}")
            print("grinding...")

            # Send target to grinder
            proc.stdin.write(target_hex + "\n")
            proc.stdin.flush()

            # Read lines until we see something that looks like "priv pub attempts"
            while True:
                line = proc.stdout.readline()
                if not line:
                    print("[ERROR] Grinder gave no output")
                    return
                line = line.strip()
                if not line:
                    continue

                parts = line.split()
                # Heuristic: line with at least 3 parts and first 2 are hex-ish
                if len(parts) >= 3 and all(c in HEXCHARS for c in "".join(parts[0:2])):
                    priv, pub, attempts = parts[0], parts[1], parts[2]
                    print("result:")
                    print(f"  priv    = {priv}")
                    print(f"  pub     = {pub}")
                    print(f"  attempts= {attempts}\n")
                    break
                else:
                    # startup / log lines like "Increasing Stack Size..."
                    print(f"[log] {line}")

            chunk_idx += 1

    except KeyboardInterrupt:
        print("\n[INFO] Stopping on Ctrl+C...")
    finally:
        try:
            proc.terminate()
        except Exception:
            pass

    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
