#I ran this with python 3.12
import string
from collections import Counter
import matplotlib.pyplot as plt
from numpy.fft import fft, ifft
import numpy as np
import numpy as _np


def get_index_of_coincidence(m, ct):
    # Build counters for each residue class modulo m in one pass
    counters = [{} for _ in range(m)]
    for idx, b in enumerate(ct):
        counters[idx % m][b] = counters[idx % m].get(b, 0) + 1

    # Compute average index of coincidence from counters without building byte strings
    total = 0.0
    for cnt in counters:
        n = sum(cnt.values())
        if n < 2:
            continue
        same_pairs = 0
        for v in cnt.values():
            same_pairs += v * (v - 1)
        total += same_pairs / (n * (n - 1))

    return total / m

def get_index_of_coincidence_proxy(m, ct):
    cnt = 0
    for i in range(m):
        if ct[i] == ct[i+m]:
            cnt += 1
    return cnt / m

def guess_key_stupid(ct, key_len):
    key = b""
    for i in range(key_len):
        text = b""
        for j in range(i, len(ct), key_len):
            text += ct[j:j+1]
        letter_counts = Counter(text)
        
        #0x00 has got to be the most common byte in firmware, right?
        most_common = letter_counts.most_common(1)[0][0]
        
        #I wanted this to be more interesting, but this kinda just works perfectly.
        
        key_char = most_common
        key += bytes([key_char])
    return key
 
def decrypt(ct, key):
    ct_arr = np.frombuffer(ct, dtype=np.uint8)
    key_arr = np.frombuffer(key, dtype=np.uint8)
    if key_arr.size == 1:
        return (np.bitwise_xor(ct_arr, key_arr[0])).tobytes()
    key_stream = np.resize(key_arr, ct_arr.shape)
    return (np.bitwise_xor(ct_arr, key_stream)).tobytes()
    
def main(ct):
    max_coincidence = 0
    best_len = 0
    second_best_len = 0
    second_best_coincidence = 0

    i=1
    while i < 0xffff:
        coincidence = get_index_of_coincidence_proxy(i, ct[:0x20000])
        
        if coincidence < .01:
            i+=1
            continue
        coincidence = get_index_of_coincidence(i, ct[:0x20000])
        
        print("len:", i, "coincidence:", coincidence)
        
        if coincidence > max_coincidence:
            print("is a new best")
            second_best_len = best_len
            second_best_coincidence = max_coincidence
            max_coincidence = coincidence
            best_len = i
        i+=1
            
    print("best len:", best_len, "with coincidence:", max_coincidence)
    print("second best len:", second_best_len, "with coincidence:", second_best_coincidence)
    guessed_key = guess_key_stupid(ct, best_len)
    with open("decrypted.bin", "wb") as d:
        d.write(decrypt(ct, guessed_key))

with open(r"encrypted.bin", "rb") as f:
    data = f.read()
    main(data)