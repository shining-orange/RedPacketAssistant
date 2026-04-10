"""
校准工具 - 在截图上标记检测到的红包区域，帮助调参
用法: python calibrate.py
"""

import os
import numpy as np
from PIL import Image, ImageDraw

import config


def analyze_screenshot(img_path):
    """分析截图并用矩形标记检测结果"""
    img = Image.open(img_path)
    arr = np.array(img)
    draw = ImageDraw.Draw(img)
    h, w = arr.shape[:2]

    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)

    print(f"图片尺寸: {w}x{h}")
    print(f"卡片颜色: R{config.CARD_R_RANGE} G{config.CARD_G_RANGE} B{config.CARD_B_RANGE}")
    print(f"信封颜色: R{config.ICON_R_RANGE} G{config.ICON_G_RANGE} B{config.ICON_B_RANGE}")

    # 生成掩码（金橙卡片 + 红色信封 并集）
    card_mask = (
        (r >= config.CARD_R_RANGE[0]) & (r <= config.CARD_R_RANGE[1]) &
        (g >= config.CARD_G_RANGE[0]) & (g <= config.CARD_G_RANGE[1]) &
        (b >= config.CARD_B_RANGE[0]) & (b <= config.CARD_B_RANGE[1])
    )
    icon_mask = (
        (r >= config.ICON_R_RANGE[0]) & (r <= config.ICON_R_RANGE[1]) &
        (g >= config.ICON_G_RANGE[0]) & (g <= config.ICON_G_RANGE[1]) &
        (b >= config.ICON_B_RANGE[0]) & (b <= config.ICON_B_RANGE[1])
    )
    mask = card_mask | icon_mask

    total_match = np.sum(mask)
    print(f"匹配像素总数: {total_match}")

    if total_match == 0:
        print("没有匹配到任何像素！请调整颜色范围。")
        img.save("debug/calibrate_result.png")
        return

    # ---- 找连通区域 ----
    row_sums = np.sum(mask, axis=1)

    # 用 gap 分隔不同色块（连续空白行超过5行就认为是两个不同的块）
    GAP = 8
    regions = []
    in_region = False
    y_start = 0

    for y in range(h):
        if row_sums[y] > 10 and not in_region:
            y_start = y
            in_region = True
        elif row_sums[y] <= 10 and in_region:
            if y - y_start > 0:
                # 检查是否和上一个区域间隔太近（合并）
                if regions and y_start - regions[-1]['y_end'] < GAP:
                    # 合并到上一个区域
                    prev = regions[-1]
                    prev['y_end'] = y
                    region_mask = mask[prev['y_start']:y, :]
                    col_idx = np.where(np.sum(region_mask, axis=0) > 0)[0]
                    if len(col_idx) > 0:
                        prev['x_start'] = min(prev['x_start'], col_idx[0])
                        prev['x_end'] = max(prev['x_end'], col_idx[-1])
                else:
                    region_mask = mask[y_start:y, :]
                    col_idx = np.where(np.sum(region_mask, axis=0) > 0)[0]
                    if len(col_idx) > 0:
                        regions.append({
                            'y_start': y_start, 'y_end': y,
                            'x_start': col_idx[0], 'x_end': col_idx[-1],
                        })
            in_region = False

    if in_region:
        region_mask = mask[y_start:h, :]
        col_idx = np.where(np.sum(region_mask, axis=0) > 0)[0]
        if len(col_idx) > 0:
            if regions and y_start - regions[-1]['y_end'] < GAP:
                prev = regions[-1]
                prev['y_end'] = h
                col_idx2 = np.where(np.sum(mask[prev['y_start']:h, :], axis=0) > 0)[0]
                if len(col_idx2) > 0:
                    prev['x_start'] = min(prev['x_start'], col_idx2[0])
                    prev['x_end'] = max(prev['x_end'], col_idx2[-1])
            else:
                regions.append({
                    'y_start': y_start, 'y_end': h,
                    'x_start': col_idx[0], 'x_end': col_idx[-1],
                })

    # ---- 计算密度并过滤 ----
    filtered = []
    for reg in regions:
        rw = reg['x_end'] - reg['x_start']
        rh = reg['y_end'] - reg['y_start']
        area = rw * rh
        pixel_count = int(np.sum(mask[reg['y_start']:reg['y_end'], reg['x_start']:reg['x_end']]))
        density = pixel_count / max(area, 1)
        reg['pixel_count'] = pixel_count
        reg['density'] = density
        reg['rw'] = rw
        reg['rh'] = rh

        if pixel_count >= config.MIN_PIXEL_COUNT and density >= config.MIN_DENSITY:
            filtered.append(reg)

    # ---- 标记结果 ----
    colors = ['red', 'lime', 'cyan', 'yellow', 'magenta', 'orange', 'white']

    print(f"\n原始检测 {len(regions)} 个, 过滤后 {len(filtered)} 个:")
    print(f"  过滤阈值: 像素>={config.MIN_PIXEL_COUNT}, 密度>={config.MIN_DENSITY:.0%}")

    # 先画被过滤的（灰色虚线效果）
    for i, reg in enumerate(regions):
        if reg not in filtered:
            draw.rectangle(
                [reg['x_start'] - 2, reg['y_start'] - 2, reg['x_end'] + 2, reg['y_end'] + 2],
                outline='gray', width=1
            )
            draw.text((reg['x_start'], reg['y_start'] - 15),
                      f"filtered px={reg['pixel_count']} d={reg['density']:.0%}", fill='gray')

    # 再画保留的
    for i, reg in enumerate(filtered):
        cy = (reg['y_start'] + reg['y_end']) // 2
        cx = (reg['x_start'] + reg['x_end']) // 2
        center_rgb = (arr[cy, cx, 0], arr[cy, cx, 1], arr[cy, cx, 2])

        color = colors[i % len(colors)]
        draw.rectangle(
            [reg['x_start'] - 2, reg['y_start'] - 2, reg['x_end'] + 2, reg['y_end'] + 2],
            outline=color, width=3
        )
        label = f"#{i+1} {reg['rw']}x{reg['rh']} px={reg['pixel_count']} d={reg['density']:.0%}"
        draw.text((reg['x_start'], reg['y_start'] - 15), label, fill=color)

        print(f"  #{i+1} [KEEP]: y=[{reg['y_start']}-{reg['y_end']}] x=[{reg['x_start']}-{reg['x_end']}] "
              f"尺寸={reg['rw']}x{reg['rh']} 像素={reg['pixel_count']} 密度={reg['density']:.0%} "
              f"中心RGB={center_rgb}")

    # 保存标记后的图片
    out_path = "debug/calibrate_result.png"
    img.save(out_path)
    print(f"\n已保存标记图片: {out_path}")
    print("请打开查看，确认检测区域是否正确覆盖了红包。")

    # ---- 也保存纯掩码图 ----
    mask_vis = np.zeros_like(arr)
    mask_vis[mask] = [255, 255, 255]
    Image.fromarray(mask_vis).save("debug/calibrate_mask.png")
    print(f"已保存掩码图: debug/calibrate_mask.png")


def main():
    debug_dir = "debug"
    if not os.path.exists(debug_dir):
        print("debug/ 目录不存在，请先用 DEBUG_MODE=True 运行 main.py 生成截图")
        return

    # 查找截图
    pngs = [f for f in os.listdir(debug_dir) if f.endswith('.png') and 'calibrate' not in f]
    if not pngs:
        print("debug/ 中没有截图，请先用 DEBUG_MODE=True 运行 main.py")
        return

    # 用最新的一张
    pngs.sort(key=lambda f: os.path.getmtime(os.path.join(debug_dir, f)))
    latest = os.path.join(debug_dir, pngs[-1])
    print(f"分析截图: {latest}\n")
    analyze_screenshot(latest)


if __name__ == '__main__':
    main()
