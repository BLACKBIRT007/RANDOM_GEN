import argparse
import hashlib
import math
import secrets
import random
from fastapi import FastAPI, HTTPException, Request
import uvicorn
import requests

app = FastAPI()

API_KEY = "RANDOM_NUM"  # Replace with env var in production


# --- FastAPI endpoint to get a random seed --- #
@app.post("/random")
async def get_random_seed(request: Request):
    data = await request.json()
    key = data.get("key")
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    random_value = secrets.randbits(64)
    return {"random_value": random_value}


# --- Hashing utility using SHAKE --- #
def shake_hash(data: bytes, out_len_chars: int, alg: str = "shake_256") -> str:
    # out_len_chars is number of hex characters (each hex char = 4 bits)
    out_len_bytes = out_len_chars // 2
    if alg == "shake_128":
        return hashlib.shake_128(data).hexdigest(out_len_bytes)
    return hashlib.shake_256(data).hexdigest(out_len_bytes)


def remove_random_chars(s: str, n: int) -> str:
    lst = list(s)
    for _ in range(min(n, len(lst))):
        idx = secrets.randbelow(len(lst))
        lst.pop(idx)
    return "".join(lst)


def multiply_by_random(value: int, times: int) -> int:
    for _ in range(times):
        value *= secrets.randbelow(1 << 32) + 1
    return value


def add_random(value: int, times: int) -> int:
    for _ in range(times):
        value += secrets.randbelow(1 << 32)
    return value


def repeated_hashing(value: int, hash_len_chars: int, loops: int, alg="shake_256") -> int:
    for _ in range(loops):
        byte_len = max((value.bit_length() + 7) // 8, 1)
        h = shake_hash(value.to_bytes(byte_len, "big"), hash_len_chars, alg)
        value = int(h, 16)
    return value


def sqrt_and_divide(value: int, divisor: int) -> int:
    # Use integer square root (math.isqrt)
    # Avoid floating point overflow by dividing after sqrt
    root = math.isqrt(value)
    return root // divisor


def shuffle_string(s: str) -> str:
    lst = list(s)
    random.shuffle(lst)
    return "".join(lst)


def pipeline(
    initial_value: int,
    loops: int = 1,
    mul_times: int = 1,
    add_times: int = 1,
    hash1_len: int = 1024,
    hash1_loops: int = 10,
    hash2_len: int = 512,
    remove_chars: int = 10,
    hash4_len: int = 2048,
    final_div: int = 8,
) -> int:
    value = initial_value

    for _ in range(loops):
        # Multiply and add random
        value = multiply_by_random(value, mul_times)
        value = add_random(value, add_times)

        # Repeated hashing with shake_256
        value = repeated_hashing(value, hash1_len, hash1_loops, "shake_256")

        # One hash with shake_128
        value = repeated_hashing(value, hash2_len, 1, "shake_128")

        # Square root and divide
        value = sqrt_and_divide(value, 4)

        # Hash again, reverse hex, convert back to int
        byte_len = max((value.bit_length() + 7) // 8, 1)
        h3 = shake_hash(value.to_bytes(byte_len, "big"), hash1_len, "shake_256")
        h3_rev = h3[::-1]
        value = int(h3_rev, 16)

        # Hash again shake_256
        byte_len = max((value.bit_length() + 7) // 8, 1)
        h4 = shake_hash(value.to_bytes(byte_len, "big"), hash1_len, "shake_256")
        value = int(h4, 16)

        # Shuffle the hex string
        shuffled = shuffle_string(h4)

        # Hash the shuffled string bytes with shake_128
        # Convert shuffled string (hex) to bytes
        shuffled_bytes = bytes.fromhex(shuffled[:hash2_len * 2])  # *2 because hex chars to bytes
        h5 = shake_hash(shuffled_bytes, hash2_len, "shake_128")
        value = int(h5, 16)

        # Remove random chars from h5 string
        trimmed = remove_random_chars(h5, remove_chars)

        # Convert trimmed hex to int and multiply once by a random 16-bit int
        value = int(trimmed, 16) * (secrets.randbelow(1 << 16) + 1)

        # Final big hash to hash4_len chars
        byte_len = max((value.bit_length() + 7) // 8, 1)
        h6 = shake_hash(value.to_bytes(byte_len, "big"), hash4_len, "shake_256")
        value = int(h6, 16)

        # Divide final value
        value //= final_div

        # Truncate hex string to max 4096 chars, then convert back to int
        truncated_hex = h6[:4096]
        value = int(truncated_hex, 16)

        # Final modulo 256 to get a byte-sized result
        value = value % 256

    return value


def get_seed_from_api(url: str, api_key: str, timeout: int = 30) -> int:
    try:
        resp = requests.post(url, json={"key": api_key}, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return int(data["random_value"])
    except Exception as e:
        print(f"❌ Error fetching seed from API: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="Random pipeline CLI and API server")
    parser.add_argument("--initial", default="random", help="Initial seed integer or 'random' to fetch from API")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/random")
    parser.add_argument("--key", default=API_KEY)
    parser.add_argument("--loops", type=int, default=1)
    parser.add_argument("--mul-times", type=int, default=1)
    parser.add_argument("--add-times", type=int, default=1)
    parser.add_argument("--hash1-len", type=int, default=1024)
    parser.add_argument("--hash1-loops", type=int, default=10)
    parser.add_argument("--hash2-len", type=int, default=512)
    parser.add_argument("--remove-chars", type=int, default=10)
    parser.add_argument("--hash4-len", type=int, default=2048)
    parser.add_argument("--final-div", type=int, default=8)
    parser.add_argument("--serve", action="store_true", help="Run FastAPI server")
    args = parser.parse_args()

    if args.serve:
        print("🚀 Starting FastAPI server on http://127.0.0.1:8000")
        uvicorn.run("random_api:app", host="127.0.0.1", port=8000, reload=True)
        return

    # CLI mode
    if args.initial.lower() == "random":
        seed = get_seed_from_api(args.api_url, args.key)
    else:
        try:
            seed = int(args.initial)
        except ValueError:
            print("❌ Invalid initial seed input. Must be an integer or 'random'.")
            return

    result = pipeline(
        initial_value=seed,
        loops=args.loops,
        mul_times=args.mul_times,
        add_times=args.add_times,
        hash1_len=args.hash1_len,
        hash1_loops=args.hash1_loops,
        hash2_len=args.hash2_len,
        remove_chars=args.remove_chars,
        hash4_len=args.hash4_len,
        final_div=args.final_div,
    )
    print(f"▶ Final 0–255 result: {result}")


if __name__ == "__main__":
    main()
