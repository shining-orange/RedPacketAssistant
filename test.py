"""
单步测试 - 手动触发一次完整的抢红包流程，每一步都截图并输出日志
用法: 在微信聊天窗口有红包时运行 python test.py
"""

import ctypes
from ctypes import wintypes
import time
import numpy as np
from PIL import Image, ImageGrab, ImageDraw
import pyautogui

import config

user32 = ctypes.windll.user32

def find_wechat():
    hwnd = user32.FindWindowW("Qt51514QWindowIcon", "微信")
    if not hwnd:
        hwnd = user32.FindWindowW(None, "微信")
    return hwnd

def get_rect(hwnd):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return (rect.left, rect.top, rect.right, rect.bottom)

def color_mask(img, r_range, g_range, b_range):
    r = img[:, :, 0].astype(int)
    g = img[:, :, 1].astype(int)
    b = img[:, :, 2].astype(int)
    return (
        (r >= r_range[0]) & (r <= r_range[1]) &
        (g >= g_range[0]) & (g <= g_range[1]) &
        (b >= b_range[0]) & (b <= b_range[1])
    )

def find_regions(mask, min_h=20, min_w=40):
    h, w = mask.shape
    row_sums = np.sum(mask, axis=1)
    regions = []
    in_r = False; ys = 0
    for y in range(h):
        if row_sums[y] > 10 and not in_r:
            ys = y; in_r = True
        elif row_sums[y] <= 10 and in_r:
            rm = mask[ys:y, :]
            ci = np.where(np.sum(rm, axis=0) > 0)[0]
            if len(ci) > 0:
                rw = ci[-1] - ci[0]
                rh = y - ys
                if rh >= min_h and rw >= min_w:
                    regions.append({'y': ys, 'h': rh, 'x': ci[0], 'w': rw})
            in_r = False
    if in_r:
        rm = mask[ys:h, :]
        ci = np.where(np.sum(rm, axis=0) > 0)[0]
        if len(ci) > 0:
            rw = ci[-1] - ci[0]
            rh = h - ys
            if rh >= min_h and rw >= min_w:
                regions.append({'y': ys, 'h': rh, 'x': ci[0], 'w': rw})
    return regions

def save_annotated(img_arr, regions, tag):
    """保存带标记的截图"""
    vis = Image.fromarray(img_arr)
    draw = ImageDraw.Draw(vis)
    for i, reg in enumerate(regions):
        draw.rectangle(
            [reg['x']-2, reg['y']-2, reg['x']+reg['w']+2, reg['y']+reg['h']+2],
            outline='red', width=3
        )
        draw.text((reg['x'], reg['y']-15), f"#{i+1} {reg['w']}x{reg['h']}", fill='red')
    vis.save(f"debug/test_{tag}.png")
    print(f"  -> saved debug/test_{tag}.png")


def main():
    hwnd = find_wechat()
    if not hwnd:
        print("未找到微信窗口!")
        return

    rect = get_rect(hwnd)
    print(f"微信窗口: hwnd={hwnd} rect={rect}")

    # ======== 第1步: 截取完整窗口 ========
    print("\n===== 第1步: 截取微信窗口 =====")
    full = np.array(ImageGrab.grab(bbox=rect))
    Image.fromarray(full).save("debug/test_0_full.png")
    print(f"  窗口截图: {full.shape[1]}x{full.shape[0]}, saved debug/test_0_full.png")

    # ======== 第2步: 截取聊天区域 ========
    print("\n===== 第2步: 截取聊天区域 =====")
    w_full = full.shape[1]
    start_x = int(w_full * config.CHAT_AREA_START_X_RATIO)
    chat = full[:, start_x:, :]
    Image.fromarray(chat).save("debug/test_1_chat.png")
    print(f"  聊天区域: 从x={start_x}开始, {chat.shape[1]}x{chat.shape[0]}")
    print(f"  CHAT_AREA_START_X_RATIO={config.CHAT_AREA_START_X_RATIO}")

    # ======== 第3步: 检测红包卡片 ========
    print("\n===== 第3步: 检测红包卡片 =====")
    card_mask = color_mask(chat, config.CARD_R_RANGE, config.CARD_G_RANGE, config.CARD_B_RANGE)
    icon_mask = color_mask(chat, config.ICON_R_RANGE, config.ICON_G_RANGE, config.ICON_B_RANGE)
    combined = card_mask | icon_mask

    card_px = int(np.sum(card_mask))
    icon_px = int(np.sum(icon_mask))
    total_px = int(np.sum(combined))
    print(f"  卡片色匹配: {card_px} 像素")
    print(f"  信封色匹配: {icon_px} 像素")
    print(f"  合并匹配:   {total_px} 像素")

    if total_px == 0:
        print("\n  [FAIL] 没有匹配到任何红包像素!")
        print("  请确认聊天窗口中有红包，然后重新运行")
        # 保存掩码供调试
        vis = np.zeros_like(chat)
        vis[card_mask] = [255, 0, 0]     # 卡片色=红
        vis[icon_mask] = [0, 255, 0]      # 信封色=绿
        Image.fromarray(vis).save("debug/test_1_masks.png")
        print("  saved debug/test_1_masks.png (红=卡片色, 绿=信封色)")
        return

    regions = find_regions(combined)
    print(f"  检测到 {len(regions)} 个区域")
    save_annotated(chat, regions, "2_detect")

    # 过滤
    filtered = []
    for reg in regions:
        rm = combined[reg['y']:reg['y']+reg['h'], reg['x']:reg['x']+reg['w']]
        px = int(np.sum(rm))
        area = max(reg['w'] * reg['h'], 1)
        density = px / area
        icon_in = icon_mask[reg['y']:reg['y']+reg['h'], reg['x']:reg['x']+reg['w']]
        icon_count = int(np.sum(icon_in))

        reg['pixel_count'] = px
        reg['density'] = density
        reg['icon_count'] = icon_count
        keep = px >= config.MIN_PIXEL_COUNT and density >= config.MIN_DENSITY and icon_count >= 200
        status = "KEEP" if keep else "SKIP"
        print(f"  [{status}] #{regions.index(reg)+1}: {reg['w']}x{reg['h']} px={px} density={density:.0%} icon={icon_count}")
        if keep:
            filtered.append(reg)

    if not filtered:
        print("\n  [FAIL] 没有通过过滤的红包区域!")
        return

    # 取最下面的红包
    pkt = max(filtered, key=lambda r: r['y'])
    cx = pkt['x'] + pkt['w'] // 2
    cy = pkt['y'] + pkt['h'] // 2
    screen_x = rect[0] + start_x + cx
    screen_y = rect[1] + cy
    print(f"\n  目标红包: ({cx},{cy}) -> 屏幕({screen_x},{screen_y})")

    # ======== 第4步: 点击红包卡片 ========
    print(f"\n===== 第4步: 点击红包卡片 ({screen_x}, {screen_y}) =====")
    pyautogui.click(screen_x, screen_y)
    print("  已点击, 等待弹窗...")
    time.sleep(0.8)

    # ======== 第5步: 截取弹窗 ========
    print("\n===== 第5步: 截取弹窗 =====")
    popup_full = np.array(ImageGrab.grab(bbox=rect))
    Image.fromarray(popup_full).save("debug/test_3_popup.png")
    print(f"  saved debug/test_3_popup.png ({popup_full.shape[1]}x{popup_full[0]})")

    # ======== 第6步: 检测弹窗和开按钮 ========
    print("\n===== 第6步: 检测弹窗 =====")
    popup_mask = color_mask(popup_full, config.POPUP_R_RANGE, config.POPUP_G_RANGE, config.POPUP_B_RANGE)
    popup_px = int(np.sum(popup_mask))
    print(f"  弹窗红色像素: {popup_px}")

    if popup_px < 5000:
        print("  [FAIL] 未检测到弹窗! 弹窗可能未打开或颜色不匹配")
        vis = np.zeros_like(popup_full)
        vis[popup_mask] = [255, 255, 255]
        Image.fromarray(vis).save("debug/test_3_popup_mask.png")
        print("  saved debug/test_3_popup_mask.png")
        # 仍然尝试 ESC 关闭
        pyautogui.press('escape')
        return

    rows, cols = np.where(popup_mask)
    y_min, y_max = int(rows.min()), int(rows.max())
    x_min, x_max = int(cols.min()), int(cols.max())
    pw = x_max - x_min
    ph = y_max - y_min
    print(f"  弹窗区域: ({x_min},{y_min})-({x_max},{y_max}) {pw}x{ph}")

    btn_x = (x_min + x_max) // 2
    btn_y = y_max - int(ph * config.OPEN_BTN_FROM_BOTTOM)
    screen_btn_x = rect[0] + btn_x
    screen_btn_y = rect[1] + btn_y

    # 保存带标记的弹窗截图
    vis = Image.fromarray(popup_full)
    draw = ImageDraw.Draw(vis)
    draw.rectangle([x_min, y_min, x_max, y_max], outline='lime', width=2)
    # 画开按钮点击位置
    draw.ellipse([btn_x-8, btn_y-8, btn_x+8, btn_y+8], fill='red', outline='white')
    draw.text((btn_x-20, btn_y-25), "CLICK", fill='red')
    vis.save("debug/test_4_popup_marked.png")
    print(f"  saved debug/test_4_popup_marked.png")

    print(f"\n  开按钮位置: ({btn_x},{btn_y}) -> 屏幕({screen_btn_x},{screen_btn_y})")
    print(f"  该点颜色: RGB({popup_full[btn_y,btn_x,0]},{popup_full[btn_y,btn_x,1]},{popup_full[btn_y,btn_x,2]})")

    # ======== 第7步: 点击开按钮 ========
    print(f"\n===== 第7步: 点击开按钮 =====")
    pyautogui.click(screen_btn_x, screen_btn_y)
    print("  已点击开按钮!")
    time.sleep(0.5)
    pyautogui.press('escape')
    print("  已按 ESC 关闭弹窗")
    print("\n===== 完成 =====")


if __name__ == '__main__':
    import os
    os.makedirs("debug", exist_ok=True)
    main()
