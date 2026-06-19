#!/usr/bin/env python3
"""
download_pexels_image.py
通过 Pexels API 搜索并下载免费图片，自动裁剪到目标尺寸。

用法:
  python download_pexels_image.py --query "Madrid smartphone" \
      --out "static/images/blog/ciudad-madrid-xxx.jpg" \
      --size 800x500 --quality 82

依赖: requests, Pillow
"""
import os
import sys
import time
import argparse
import io
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

# 从环境变量或命令行参数读取 API key
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")


def search_photo(api_key, query, per_page=5, orientation="landscape", retries=3):
    """搜索 Pexels 图片，返回第一张可用的 photo dict。"""
    headers = {"Authorization": api_key}
    params = {"query": query, "per_page": per_page, "orientation": orientation}
    for attempt in range(retries):
        try:
            resp = requests.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            photos = data.get("photos", [])
            if not photos:
                raise RuntimeError(f"Pexels 未找到图片: query='{query}'")
            return photos[0]
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"Pexels API 请求失败（重试 {retries} 次）: {e}")


def download_image(url, timeout=30, retries=3):
    """下载图片，返回 PIL Image 对象。"""
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return Image.open(io.BytesIO(resp.content))
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"下载图片失败（重试 {retries} 次）: {e}")


def crop_to_target(img, target_w, target_h):
    """
    将图片中心裁剪到目标宽高比，再缩放到精确尺寸。
    避免拉伸变形。
    """
    src_w, src_h = img.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if abs(src_ratio - target_ratio) < 0.01:
        # 比例已接近，直接缩放
        return img.resize((target_w, target_h), Image.LANCZOS)

    # 先裁剪成目标比例
    if src_ratio > target_ratio:
        # 原图太宽，裁左右
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, src_h))
    else:
        # 原图太高，裁上下
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        img = img.crop((0, top, src_w, top + new_h))

    # 再缩放到精确尺寸
    return img.resize((target_w, target_h), Image.LANCZOS)


def main():
    parser = argparse.ArgumentParser(description="从 Pexels 下载免费图片")
    parser.add_argument("--query", required=True, help="搜索关键词（英文）")
    parser.add_argument("--out", required=True, help="输出图片路径")
    parser.add_argument("--size", default="800x500", help="目标尺寸 WxH（默认 800x500）")
    parser.add_argument("--quality", type=int, default=82, help="JPEG 质量 1-95（默认 82）")
    parser.add_argument("--api-key", default="", help="Pexels API Key（也可用环境变量 PEXELS_API_KEY）")
    parser.add_argument("--orientation", default="landscape", choices=["landscape", "portrait", "square"],
                        help="图片方向偏好（默认 landscape）")
    args = parser.parse_args()

    api_key = args.api_key or PEXELS_API_KEY
    if not api_key:
        print("ERROR: 未提供 Pexels API Key。请设置环境变量 PEXELS_API_KEY 或用 --api-key 指定。")
        sys.exit(1)

    target_w, target_h = map(int, args.size.split("x"))

    # 搜索
    print(f"[Pexels] 搜索: '{args.query}' ({args.orientation})")
    photo = search_photo(api_key, args.query, per_page=5, orientation=args.orientation)
    print(f"[Pexels] 选中: {photo['url']} (by {photo['photographer']})")

    # 下载原图（用 large 尺寸，足够大）
    img_url = photo["src"].get("large", photo["src"]["medium"])
    print(f"[Download] {img_url}")
    img = download_image(img_url)

    # 裁剪 + 缩放
    img_final = crop_to_target(img, target_w, target_h)

    # 保存
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img_final.save(str(out_path), "JPEG", quality=args.quality)
    size_kb = out_path.stat().st_size / 1024

    print(f"[Save] {out_path} ({target_w}x{target_h}, {size_kb:.1f} KB)")
    print("OK")


if __name__ == "__main__":
    main()
