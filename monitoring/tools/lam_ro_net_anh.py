#!/usr/bin/env python3
"""
Bot nho lam ro net anh (JPEG, PNG, WebP...) bang bo loc Unsharp Mask (Pillow).

Tren web: mo /admin, click anh, nut "Nang chat luong" (phong to + unsharp nhe, khong phai AI).
Anh rat lon bi gioi han; de luu file da xu ly hay dung script nay.

buiCai dat: pip install Pillow   (hoac dung cung moi truong agent: monitoring/agent)

Vi du:
  python lam_ro_net_anh.py -i anh.jpg -o anh_ro.jpg
  python lam_ro_net_anh.py -i ./screenshots -o ./screenshots_ro --suffix _ro
  python lam_ro_net_anh.py -i cap.jpg -o cap.jpg --in-place

Tham so UnsharpMask (Pillow):
  --radius   (mac dinh 2)   - ban kinh mo (pixel), cang lon vung anh huong cang rong
  --percent  (mac dinh 150) - cuong do tang net (100 = trung tinh)
  --threshold (mac dinh 3)  - bo qua vung gan phang mau (giam nhieu)
"""
from __future__ import annotations

import argparse    
import sys
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Lam ro net anh (Unsharp Mask). Ho tro 1 file hoac ca thu muc."
    )
    p.add_argument("-i", "--input", required=True, help="File anh hoac thu muc nguon")
    p.add_argument(
        "-o",
        "--output",
        help="File dich hoac thu muc dich (bat buoc neu khong --in-place)",
    )
    p.add_argument(
        "--in-place",
        action="store_true",
        help="Ghi de len file nguon (chi khi -i la 1 file)",
    )
    p.add_argument(
        "--suffix",
        default="",
        help="Hau to ten file khi xu ly thu muc (vd: _ro → screen.jpg → screen_ro.jpg)",
    )
    p.add_argument("--radius", type=float, default=2.0, help="Ban kinh UnsharpMask (mac dinh 2)")
    p.add_argument(
        "--percent",
        type=int,
        default=150,
        help="Phan tram tang net (mac dinh 150, ~100 = nhe)",
    )
    p.add_argument(
        "--threshold",
        type=int,
        default=3,
        help="Nguong bo qua bien mong (0-255, mac dinh 3)",
    )
    p.add_argument(
        "--quality",
        type=int,
        default=90,
        help="Chat luong JPEG khi luu .jpg (mac dinh 90)",
    )
    p.add_argument(
        "--exif",
        action="store_true",
        help="Giu EXIF khi luu JPEG (mac dinh bo de tranh loi mot so trinh xem)",
    )
    return p.parse_args()


def to_rgb_for_save(im: Image.Image, path: Path) -> Image.Image:
    suf = path.suffix.lower()
    if suf in (".jpg", ".jpeg") and im.mode in ("RGBA", "P"):
        return ImageOps.exif_transpose(im).convert("RGB")
    if im.mode == "P":
        return im.convert("RGBA")
    return ImageOps.exif_transpose(im)


def sharpen(im: Image.Image, *, radius: float, percent: int, threshold: int) -> Image.Image:
    return im.filter(
        ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold)
    )


def save_image(im: Image.Image, dest: Path, quality: int, save_exif: bool) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    suf = dest.suffix.lower()
    if suf in (".jpg", ".jpeg"):
        exif = im.info.get("exif") if save_exif else None
        im.save(dest, quality=quality, optimize=True, exif=exif)
    elif suf == ".png":
        im.save(dest, optimize=True)
    else:
        im.save(dest)


def process_one(
    src: Path,
    dest: Path,
    *,
    radius: float,
    percent: int,
    threshold: int,
    quality: int,
    save_exif: bool,
) -> None:
    with Image.open(src) as raw:
        im = to_rgb_for_save(raw, dest)
        if dest.suffix.lower() in (".jpg", ".jpeg") and im.mode != "RGB":
            im = im.convert("RGB")
        out = sharpen(im, radius=radius, percent=percent, threshold=threshold)
        save_image(out, dest, quality=quality, save_exif=save_exif)


def main() -> int:
    args = parse_args()
    src = Path(args.input).expanduser().resolve()

    if not src.exists():
        print("Khong tim thay:", src, file=sys.stderr)
        return 1

    if args.in_place:
        if not src.is_file():
            print("--in-place chi dung khi -i la mot file.", file=sys.stderr)
            return 1
        dest = src
    else:
        if not args.output:
            print("Can -o hoac --in-place.", file=sys.stderr)
            return 1
        dest_root = Path(args.output).expanduser().resolve()

    radius = max(0.1, float(args.radius))
    percent = max(0, min(500, int(args.percent)))
    threshold = max(0, min(255, int(args.threshold)))
    quality = max(1, min(100, int(args.quality)))

    if src.is_file():
        if src.suffix.lower() not in EXT:
            print("Dinh dang khong ho tro:", src.suffix, file=sys.stderr)
            return 1
        if args.in_place:
            out_path = src
        else:
            out_path = dest_root if dest_root.suffix else dest_root / src.name
        process_one(
            src,
            out_path,
            radius=radius,
            percent=percent,
            threshold=threshold,
            quality=quality,
            save_exif=args.exif,
        )
        print("OK:", out_path)
        return 0

    if not src.is_dir():
        return 1

    if args.in_place:
        print("--in-place khong dung voi thu muc.", file=sys.stderr)
        return 1

    out_dir = dest_root
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted(src.iterdir()):
        if not f.is_file() or f.suffix.lower() not in EXT:
            continue
        stem = f.stem + args.suffix + f.suffix
        outp = out_dir / stem
        try:
            process_one(
                f,
                outp,
                radius=radius,
                percent=percent,
                threshold=threshold,
                quality=quality,
                save_exif=args.exif,
            )
            n += 1
            print("+", outp.name)
        except OSError as e:
            print("Loi", f.name, e, file=sys.stderr)
    print("Xong,", n, "anh.")
    return 0 if n else 1


if __name__ == "__main__":
    raise SystemExit(main())
