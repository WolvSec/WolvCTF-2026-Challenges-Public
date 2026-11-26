Players receive wav1.wav and wav2.wav. Convert both to floating-point samples and subtract one from the other to cancel the common audio. File order only changes the sign.

The verified Python path is to run `python3 Solution/solve.py` in an organizer checkout with NumPy, SciPy, and Matplotlib installed. It saves `Solution/spectrogram.png` using a Hann window of 65536 samples, 50% overlap, and a 0–20 Hz view. Read the upper row of letters, then the lower row, to get the flag. The same settings work when plotting the magnitude of the samplewise difference yourself.
