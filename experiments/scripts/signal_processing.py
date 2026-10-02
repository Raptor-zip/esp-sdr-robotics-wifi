"""FFT normalization and C5 RF axis used in the measured figures."""
import numpy as np

def spectra(iq, fs, nfft):
    z = (iq[..., 0].astype(np.float64) + 1j * iq[..., 1]) / 128
    blocks = z.shape[1] // nfft
    z = z[:, :blocks * nfft].reshape(z.shape[0], blocks, nfft)
    z -= z.mean(axis=-1, keepdims=True)
    window = np.hanning(nfft)
    fft = np.fft.fftshift(np.fft.fft(z * window, axis=-1), axes=-1)
    power = (np.abs(fft) ** 2 / window.sum() ** 2).mean(axis=1)
    # C5 convention: I+jQ corresponds to LO-RF. Reverse the frequency axis.
    baseband = -np.fft.fftshift(np.fft.fftfreq(nfft, 1 / fs))
    order = np.argsort(baseband)
    return baseband[order], power[:, order]
