import sys
import os

key = os.urandom(0xc0de)

def encrypt(data):
    encrypted = bytearray()
    for i in range(len(data)):
        encrypted.append(data[i] ^ key[i % len(key)])
    return encrypted

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 crypt.py <input_file> <output_file> <output_key_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    key_file = sys.argv[3]

    with open(input_file, "rb") as f:
        data = f.read()

    encrypted_data = encrypt(data)
    
    with open(key_file, "wb") as f:
        f.write(b"\xde\xc0" + key)

    with open(output_file, "wb") as f:
        f.write(encrypted_data)