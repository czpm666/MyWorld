# -*- coding: utf-8 -*-
"""
make_normalmaps.py — 平铺 albedo 贴图 -> 切线空间法线贴图（批处理，可复现，可调参）

流程：
  1. Pillow 读图转灰度（ITU-R 601 luma）：高度图 h = 1 - luminance（暗缝 = 低，凸起 = 高）
  2. 轻微高斯模糊（sigma = BLUR_SIGMA，边界 wrap）压掉 JPEG 噪声
  3. Sobel 算子求 dx / dy，采样越界一律 wrap，保证法线图仍然无缝平铺
  4. n = normalize(-dx * strength, -dy * strength, 1)  -> 切线空间（+Y 向上）
     （Unity / OpenGL 约定：绿通道朝上，不要反相，否则光照会"凸变凹"）
  5. 编码 RGB = n * 0.5 + 0.5（8 bit，无 alpha）
  6. 输出分辨率 = 源图分辨率；超过 MAX_SIZE 缩到 MAX_SIZE，小于 MIN_SIZE 放大到 MIN_SIZE

用法（需 Python 3 + Pillow + numpy）：
  python make_normalmaps.py                 # 处理 TEXTURES 全表
  python make_normalmaps.py kit_roof_tile   # 只重跑某一张
输出：
  - 同目录 <stem>_n.png
  - <REPORT_PATH>（尺寸 / 平均 RGB / 平均倾斜角 / 文件大小）
"""

import json
import os
import sys
from datetime import datetime

import numpy as np
from PIL import Image, ImageFilter

TEXTURE_DIR = r"E:\My World\Assets\Art\Textures"
REPORT_PATH = r"E:\My World\WorkQC\kingdom\normalmaps.json"

# 每张贴图的法线强度（越大越深）。3.0 大致相当于 1px 高的台阶倾斜 17.6°。
STRENGTH = {
    "kit_cobble": 2.7,
    "kit_stone_wall": 1.95,
    "kit_blocks": 1.75,
    "kit_plaster": 0.7,
    "kit_roof_tile": 2.75,
    "kit_planks": 1.1,
    "kit_brick": 1.5,
    "kit_thatch": 1.6,
}

TEXTURES = [
    "kit_cobble",
    "kit_stone_wall",
    "kit_blocks",
    "kit_plaster",
    "kit_roof_tile",
    "kit_planks",
    "kit_brick",
    "kit_thatch",
]

BLUR_SIGMA = 1.0
MAX_SIZE = 1024
MIN_SIZE = 512
FLAT_TILT_DEG = 2.0
FLAT_BOOST = 1.5


def _luma(img):
    a = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    return 0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]


def _wrap_blur(arr, sigma):
    """高斯模糊，边界按 wrap 处理（先平铺 3x3 再裁回，保持无缝）。"""
    h, w = arr.shape
    tile = np.tile(arr, (3, 3))
    img = Image.fromarray((np.clip(tile, 0.0, 1.0) * 255.0).astype(np.uint8), mode="L")
    img = img.filter(ImageFilter.GaussianBlur(radius=sigma))
    out = np.asarray(img, dtype=np.float32) / 255.0
    return out[h:2 * h, w:2 * w]


def _sobel_wrap(arr):
    a = np.pad(arr, 1, mode="wrap")
    dx = (
        (a[:-2, 2:] + 2.0 * a[1:-1, 2:] + a[2:, 2:])
        - (a[:-2, :-2] + 2.0 * a[1:-1, :-2] + a[2:, :-2])
    )
    dy = (
        (a[2:, :-2] + 2.0 * a[2:, 1:-1] + a[2:, 2:])
        - (a[:-2, :-2] + 2.0 * a[:-2, 1:-1] + a[:-2, 2:])
    )
    return dx, dy


def _normals(arr, strength):
    d = _wrap_blur(arr, BLUR_SIGMA)
    dx, dy = _sobel_wrap(d)
    nx = -dx * strength
    ny = -dy * strength
    nz = np.ones_like(nx)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / ln, ny / ln, nz / ln
    out = np.stack([nx * 0.5 + 0.5, ny * 0.5 + 0.5, nz * 0.5 + 0.5], axis=-1)
    return (np.clip(out, 0.0, 1.0) * 255.0).astype(np.uint8), nz


def _tilt_deg(nz):
    return float(np.degrees(np.arccos(np.clip(float(nz.mean()), -1.0, 1.0))))


def build(stem, strength):
    src = os.path.join(TEXTURE_DIR, stem + ".jpg")
    if not os.path.exists(src):
        src = os.path.join(TEXTURE_DIR, stem + ".png")
    if not os.path.exists(src):
        return None

    img = Image.open(src)
    w, h = img.size
    height = 1.0 - _luma(img)

    rgb, nz = _normals(height, strength)
    tilt = _tilt_deg(nz)
    if tilt < FLAT_TILT_DEG:
        boost = strength * FLAT_BOOST
        rgb, nz = _normals(height, boost)
        tilt = _tilt_deg(nz)

    out = Image.fromarray(rgb, mode="RGB")
    if max(out.size) > MAX_SIZE:
        k = MAX_SIZE / float(max(out.size))
        out = out.resize((max(1, int(out.size[0] * k)), max(1, int(out.size[1] * k))), Image.LANCZOS)
    elif max(out.size) < MIN_SIZE:
        k = MIN_SIZE / float(max(out.size))
        out = out.resize((int(out.size[0] * k), int(out.size[1] * k)), Image.LANCZOS)

    dst = os.path.join(TEXTURE_DIR, stem + "_n.png")
    out.save(dst, optimize=True)

    a = np.asarray(out, dtype=np.float32)
    return {
        "texture": stem,
        "src": os.path.basename(src),
        "src_size": [w, h],
        "out_size": [out.size[0], out.size[1]],
        "mean_rgb": [round(float(a[:, :, i].mean()), 2) for i in range(3)],
        "mean_tilt_deg": round(tilt, 2),
        "bytes": os.path.getsize(dst),
    }


def main():
    stems = sys.argv[1:] or list(TEXTURES)
    report = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "blur_sigma": BLUR_SIGMA,
        "strength": {s: STRENGTH.get(s, 2.0) for s in stems},
        "items": [],
    }
    for stem in stems:
        r = build(stem, STRENGTH.get(stem, 2.0))
        if r is None:
            print("skip (no source): %s" % stem)
            continue
        report["items"].append(r)
        print("%-16s %sx%s  mean=%s  tilt=%.2f deg  %.0f KB" % (
            stem, r["out_size"][0], r["out_size"][1],
            tuple(r["mean_rgb"]), r["mean_tilt_deg"], r["bytes"] / 1024.0))

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("report: %s" % REPORT_PATH)


if __name__ == "__main__":
    main()



