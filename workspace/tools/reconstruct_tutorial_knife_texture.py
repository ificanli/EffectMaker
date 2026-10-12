import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def remove_editor_guides(rgb: np.ndarray) -> np.ndarray:
    result = rgb.copy()
    background = np.median(
        np.concatenate(
            [rgb[:8, :8].reshape(-1, 3), rgb[-8:, -8:].reshape(-1, 3)], axis=0
        ),
        axis=0,
    ).astype(np.uint8)
    green = result[:, :, 1].astype(np.int16)
    red = result[:, :, 0].astype(np.int16)
    blue = result[:, :, 2].astype(np.int16)
    guide_pixels = (green > red + 20) & (blue > red + 20) & (green > 80)
    guide_rows = np.where(guide_pixels.sum(axis=1) > result.shape[1] * 0.35)[0]
    for row in guide_rows:
        result[max(0, row - 1) : min(result.shape[0], row + 5)] = background
    return result


def card_alpha(rgb: np.ndarray) -> np.ndarray:
    background = np.median(
        np.concatenate(
            [rgb[:8, :8].reshape(-1, 3), rgb[-8:, -8:].reshape(-1, 3)], axis=0
        ),
        axis=0,
    )
    distance = np.linalg.norm(rgb.astype(np.float32) - background, axis=2)
    neutral = rgb.max(axis=2).astype(np.int16) - rgb.min(axis=2).astype(np.int16) < 14
    alpha = np.where(
        neutral,
        np.clip((distance - 12.0) * (255.0 / 24.0), 0.0, 255.0),
        255.0,
    )
    alpha[distance < 9.0] = 0.0
    return alpha.astype(np.uint8)


def luminance_alpha(rgb: np.ndarray) -> np.ndarray:
    luminance = (
        rgb[:, :, 0].astype(np.float32) * 0.2126
        + rgb[:, :, 1].astype(np.float32) * 0.7152
        + rgb[:, :, 2].astype(np.float32) * 0.0722
    )
    return np.clip((luminance - 8.0) * (255.0 / 180.0), 0.0, 255.0).astype(np.uint8)


def crop_card(source: Path, output: Path, mask_output: Path | None) -> None:
    image = Image.open(source).convert("RGB")
    crop = image.crop((340, 260, 760, 410))
    rgb = remove_editor_guides(np.asarray(crop))
    alpha = card_alpha(rgb)
    ys, xs = np.where(alpha > 8)
    if len(xs) == 0:
        raise RuntimeError("no card pixels survived background removal")
    margin = 3
    left = max(0, int(xs.min()) - margin)
    top = max(0, int(ys.min()) - margin)
    right = min(rgb.shape[1], int(xs.max()) + margin + 1)
    bottom = min(rgb.shape[0], int(ys.max()) + margin + 1)
    rgba = np.dstack((rgb, alpha))[top:bottom, left:right]
    card = Image.fromarray(rgba, mode="RGBA")
    target_width = 1024
    target_height = max(1, round(card.height * target_width / card.width))
    card = card.resize((target_width, target_height), Image.Resampling.LANCZOS)
    output.parent.mkdir(parents=True, exist_ok=True)
    card.save(output, format="PNG", optimize=True)
    if mask_output is not None:
        mask_output.parent.mkdir(parents=True, exist_ok=True)
        card.getchannel("A").save(mask_output, format="PNG", optimize=True)


def derive_luminance(source: Path, output: Path) -> None:
    image = Image.open(source).convert("RGB")
    rgb = np.asarray(image)
    alpha = luminance_alpha(rgb)
    rgba = np.dstack((rgb, alpha))
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, mode="RGBA").save(output, format="PNG", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("card", "luminance"), required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mask-output", type=Path)
    args = parser.parse_args()
    if args.mode == "card":
        crop_card(args.source, args.output, args.mask_output)
    else:
        derive_luminance(args.source, args.output)


if __name__ == "__main__":
    main()
