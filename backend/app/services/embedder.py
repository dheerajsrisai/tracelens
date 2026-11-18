"""
Appearance descriptors used to recognise the same person/vehicle in different cameras.

* "histogram" (default): colour layout descriptor. Persons are split into an upper-body and a lower-body
  region (clothing colours), vehicles use the body colour. The vector is sqrt(colour histogram), L2-normalised,
  so the dot product of two descriptors approximates the Bhattacharyya coefficient (1.0 = identical colours).
  It needs no extra model download, runs on CPU in milliseconds, and is a *baseline*, not forensic-grade ReID.
* "resnet" (experimental): ImageNet ResNet-18 features. Tune MATCH_THRESHOLD if you switch to it.

To plug in a dedicated ReID network (e.g. OSNet from torchreid), add a function here that returns an
L2-normalised vector and select it with EMBEDDER=<name>.
"""
import cv2
import numpy as np

from ..config import settings

N_HUE = 16
# bins: [black, dark-grey, mid-grey, light/white] + 16 hue bins
N_BINS = 4 + N_HUE


def _color_hist(region_bgr: np.ndarray) -> np.ndarray:
    """
    Robust colour histogram. Hue is meaningless for black, grey and white clothing and is very noisy at low
    saturation, so those pixels go to separate achromatic bins (by brightness); only clearly coloured pixels
    vote for a hue bin. The histogram is then smoothed so small lighting/camera shifts move mass to the
    neighbouring bin instead of a completely different one.
    """
    region = cv2.GaussianBlur(region_bgr, (5, 5), 0)
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float32)
    h, sat, val = hsv[:, 0], hsv[:, 1], hsv[:, 2]

    black = val < 50
    achro = (~black) & (sat < 50)
    chroma = ~(black | achro)

    hist = np.zeros(N_BINS, np.float32)
    hist[0] = black.sum()
    v = val[achro]
    hist[1] = ((v >= 50) & (v < 115)).sum()
    hist[2] = ((v >= 115) & (v < 185)).sum()
    hist[3] = (v >= 185).sum()
    hue_bin = np.minimum((h[chroma] / 180.0 * N_HUE).astype(int), N_HUE - 1)
    hist[4:] = np.bincount(hue_bin, minlength=N_HUE)

    k = np.array([0.2, 0.6, 0.2], np.float32)                      # smoothing kernel
    hue = hist[4:]
    hist[4:] = k[0] * np.roll(hue, 1) + k[1] * hue + k[2] * np.roll(hue, -1)      # hue is circular
    ach = hist[:4].copy()
    hist[:4] = np.convolve(np.pad(ach, 1, mode="edge"), k, mode="valid")           # brightness is not
    total = hist.sum()
    return hist / total if total > 0 else hist


def _l2(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return (v / n).astype(np.float32) if n > 0 else v.astype(np.float32)


def histogram_embedding(crop_bgr: np.ndarray, group: str) -> np.ndarray:
    if group == "PERSON":
        img = cv2.resize(crop_bgr, (64, 128), interpolation=cv2.INTER_AREA)
        upper = img[int(128 * 0.15):int(128 * 0.50), 8:56]       # torso (skip head and background at the edges)
        lower = img[int(128 * 0.50):int(128 * 0.90), 8:56]       # legs
        feats = np.concatenate([np.sqrt(_color_hist(upper)), np.sqrt(_color_hist(lower))])
    else:
        img = cv2.resize(crop_bgr, (96, 64), interpolation=cv2.INTER_AREA)
        body = img[int(64 * 0.20):int(64 * 0.90), int(96 * 0.10):int(96 * 0.90)]
        feats = np.sqrt(_color_hist(body))
    return _l2(feats)


_resnet = None


def _resnet_embedding(crop_bgr: np.ndarray, group: str) -> np.ndarray:
    global _resnet
    import torch
    import torchvision

    if _resnet is None:
        m = torchvision.models.resnet18(weights=torchvision.models.ResNet18_Weights.DEFAULT)
        m.fc = torch.nn.Identity()
        _resnet = m.eval()
    size = (128, 256) if group == "PERSON" else (224, 160)
    rgb = cv2.cvtColor(cv2.resize(crop_bgr, size), cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    rgb = (rgb - np.array([0.485, 0.456, 0.406], np.float32)) / np.array([0.229, 0.224, 0.225], np.float32)
    t = torch.from_numpy(rgb.transpose(2, 0, 1)).unsqueeze(0)
    with torch.no_grad():
        return _l2(_resnet(t)[0].numpy())


def embed(crop_bgr: np.ndarray, group: str) -> np.ndarray:
    if settings.embedder == "resnet":
        return _resnet_embedding(crop_bgr, group)
    return histogram_embedding(crop_bgr, group)


def mean_embedding(vectors) -> np.ndarray:
    return _l2(np.mean(np.stack(vectors), axis=0))
