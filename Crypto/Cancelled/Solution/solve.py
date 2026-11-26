#!/usr/bin/env python3
"""
Solve script for "Cancelled" crypto/audio steganography challenge.

The challenge provides two WAV files. The solution involves:
1. Loading both WAV files
2. Inverting one channel and adding to the other (cancelling common audio)
3. Generating a spectrogram of the result
4. The flag appears visually in the spectrogram

"""

import numpy as np
import scipy.io.wavfile as wavfile
import scipy.signal as signal
import matplotlib.pyplot as plt
from pathlib import Path


def load_wav(filepath):
    """Load a WAV file and return sample rate and normalized audio data."""
    sample_rate, data = wavfile.read(filepath)

    # Convert to mono if stereo (take first channel)
    if len(data.shape) > 1:
        data = data[:, 0]

    # Normalize to float32 in range [-1, 1]
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    elif data.dtype == np.uint8:
        data = (data.astype(np.float32) - 128) / 128.0

    return sample_rate, data


def cancel_audio(data1, data2, gain=1.0):
    """
    Cancel common audio by inverting one and adding.
    This is equivalent to data1 - data2 (or data2 - data1).

    Args:
        data1: First audio signal
        data2: Second audio signal
        gain: Gain factor to apply to the cancelled signal (default 1.0)
    """
    # Ensure same length
    min_len = min(len(data1), len(data2))
    data1 = data1[:min_len]
    data2 = data2[:min_len]

    # Invert data2 and add to data1 (cancels common signal)
    cancelled = data1 - data2

    # Apply gain
    cancelled = cancelled * gain

    return cancelled


def generate_spectrogram(audio_data, sample_rate, output_path,
                         freq_range=(0, 20000), window_size=32768,
                         clamp_high=-18, clamp_high_to=0,
                         clamp_low=-100, clamp_low_to=-140):
    """
    Generate and save a spectrogram of the cancelled audio with intensity clamping.

    Args:
        audio_data: The cancelled audio signal
        sample_rate: Sample rate of the audio
        output_path: Path to save the spectrogram image
        freq_range: Frequency range to display (default 0-20kHz)
        window_size: FFT window size (default 32768)
        clamp_high: Intensity values above this (in dB) are clamped to clamp_high_to
        clamp_high_to: Value to clamp high intensities to (in dB)
        clamp_low: Intensity values below this (in dB) are clamped to clamp_low_to
        clamp_low_to: Value to clamp low intensities to (in dB)
    """
    plt.figure(figsize=(16, 9))

    # Compute spectrogram using scipy for full control over data
    freqs, times, Sxx = signal.spectrogram(
        audio_data,
        fs=sample_rate,
        window='hann',
        nperseg=window_size,
        noverlap=window_size // 2,
        mode='magnitude'
    )

    # Convert to dB scale (20*log10 for magnitude, avoid log10(0))
    Sxx_db = 20 * np.log10(np.maximum(Sxx, 1e-20))

    # Apply intensity clamping on dB scale
    # Values above clamp_high -> clamp_high_to
    # Values below clamp_low -> clamp_low_to
    mask_high = Sxx_db > clamp_high
    mask_low = Sxx_db < clamp_low
    mask_mid = ~(mask_high | mask_low)

    Sxx_transformed = np.zeros_like(Sxx_db)
    Sxx_transformed[mask_high] = clamp_high_to
    Sxx_transformed[mask_low] = clamp_low_to

    # Linear mapping for middle values
    if np.any(mask_mid):
        # Map [clamp_low, clamp_high] -> [clamp_low_to, clamp_high_to]
        Sxx_transformed[mask_mid] = clamp_low_to + (Sxx_db[mask_mid] - clamp_low) * \
            (clamp_high_to - clamp_low_to) / (clamp_high - clamp_low)

    # Frequency mask for display range
    freq_mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
    freqs_display = freqs[freq_mask]
    Sxx_display = Sxx_transformed[freq_mask, :]

    # Plot using pcolormesh
    plt.pcolormesh(times, freqs_display, Sxx_display,
                   shading='gouraud', cmap='inferno')
    plt.colorbar(label='Intensity (dB)')

    # Set frequency range
    plt.ylim(freq_range)

    # Labels and title
    plt.xlabel('Time (s)')
    plt.ylabel('Frequency (Hz)')
    plt.title('Cancelled Audio Spectrogram')

    # Save
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"Spectrogram saved to: {output_path}")


def generate_spectrogram_lowfreq(audio_data, sample_rate, output_path,
                                  clamp_high=-18, clamp_high_to=0,
                                  clamp_low=-100, clamp_low_to=-140,
                                  window_size=65536):
    """
    Generate a single spectrogram of the 0-20 Hz range where the flag appears.

    Args:
        audio_data: The cancelled audio signal
        sample_rate: Sample rate of the audio
        output_path: Path to save the spectrogram image
        clamp_high: Intensity values above this are clamped to clamp_high_to
        clamp_high_to: Value to clamp high intensities to
        clamp_low: Intensity values below this are clamped to clamp_low_to
        clamp_low_to: Value to clamp low intensities to
        window_size: FFT window size (default 65536 for better low-freq resolution)
    """
    generate_spectrogram(audio_data, sample_rate, output_path, freq_range=(0, 20),
                         window_size=window_size,
                         clamp_high=clamp_high, clamp_high_to=clamp_high_to,
                         clamp_low=clamp_low, clamp_low_to=clamp_low_to)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Solve the Cancelled crypto/audio steganography challenge")
    parser.add_argument("--audio-gain", type=float, default=0.8,
                        help="Audio gain for cancellation (default: 0.8)")
    parser.add_argument("--clamp-high", type=float, default=-18,
                        help="Clamp intensity values above this (dB, default: -18)")
    parser.add_argument("--clamp-high-to", type=float, default=0,
                        help="Value to clamp high intensities to (dB, default: 0)")
    parser.add_argument("--clamp-low", type=float, default=-100,
                        help="Clamp intensity values below this (dB, default: -100)")
    parser.add_argument("--clamp-low-to", type=float, default=-140,
                        help="Value to clamp low intensities to (dB, default: -140)")
    parser.add_argument("--window-size", type=int, default=65536,
                        help="FFT window size for spectrogram (default: 65536)")
    args = parser.parse_args()

    challenge_dir = Path(__file__).parent.parent
    solution_dir = Path(__file__).parent

    # Find WAV files
    wav_files = list(challenge_dir.glob("*.wav"))
    if len(wav_files) < 2:
        raise SystemExit("Error: Could not find 2 WAV files in challenge directory")

    print(f"Found WAV files:")
    for f in wav_files:
        print(f"  - {f.name}")

    # Load both WAV files
    print("\nLoading WAV files...")
    sr1, data1 = load_wav(wav_files[0])
    sr2, data2 = load_wav(wav_files[1])

    print(f"File 1: {sr1} Hz, {len(data1)} samples, duration: {len(data1)/sr1:.2f}s")
    print(f"File 2: {sr2} Hz, {len(data2)} samples, duration: {len(data2)/sr2:.2f}s")

    if sr1 != sr2:
        print(f"Warning: Sample rates differ ({sr1} vs {sr2})")

    # Cancel the audio
    print(f"\nCancelling common audio (inverting one and adding) with audio gain={args.audio_gain}...")
    cancelled = cancel_audio(data1, data2, gain=args.audio_gain)

    # Save cancelled audio for manual inspection
    cancelled_path = solution_dir / "cancelled_audio.wav"
    # Normalize and convert back to int16
    cancelled_normalized = np.clip(cancelled, -1, 1)
    cancelled_int16 = (cancelled_normalized * 32767).astype(np.int16)
    wavfile.write(cancelled_path, sr1, cancelled_int16)
    print(f"Cancelled audio saved to: {cancelled_path}")

    # Generate spectrogram (0-20 Hz range where flag appears)
    # Apply intensity clamping on dB scale
    print(f"\nGenerating spectrogram (0-20 Hz) with dB clamping...")
    print(f"  High: >{args.clamp_high} dB -> {args.clamp_high_to} dB")
    print(f"  Low: <{args.clamp_low} dB -> {args.clamp_low_to} dB")
    print(f"  Window size: {args.window_size}")
    spectrogram_path = solution_dir / "spectrogram.png"
    generate_spectrogram_lowfreq(cancelled, sr1, spectrogram_path,
                                  clamp_high=args.clamp_high,
                                  clamp_high_to=args.clamp_high_to,
                                  clamp_low=args.clamp_low,
                                  clamp_low_to=args.clamp_low_to,
                                  window_size=args.window_size)

    print("\n" + "="*60)
    print("SPECTROGRAM GENERATED")
    print("="*60)
    print(f"\nCheck the generated spectrogram image in: {solution_dir}")
    print("Inspect the 0-20 Hz spectrogram; this script does not verify its text.")


if __name__ == "__main__":
    main()
