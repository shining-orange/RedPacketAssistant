"""
微信PC端自动抢红包脚本（适配新版 Qt 微信）
基于 截图 + 颜色检测 + 模拟点击 实现

使用方法:
    1. pip install -r requirements.txt
    2. 打开微信 PC 端并登录
    3. 打开要监控的聊天窗口
    4. python main.py
    5. Ctrl+C 停止
"""

import os
import sys
import time
import datetime
import ctypes
from ctypes import wintypes

try:
    import numpy as np
    from PIL import ImageGrab
    import pyautogui
except ImportError:
    print("请先安装依赖: pip install -r requirements.txt")
    sys.exit(1)

import config

# pyautogui 安全设置
pyautogui.PAUSE = 0.05
pyautogui.FAILSAFE = True

# ============ 工具函数 ============

def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {msg}")

def beep_alert():
    if config.SOUND_ALERT:
        try:
            ctypes.windll.kernel32.Beep(800, 200)
        except Exception:
            pass

def ensure_debug_dir():
    if config.DEBUG_MODE:
        os.makedirs("debug", exist_ok=True)

def save_debug_img(img_array, tag=""):
    if config.DEBUG_MODE:
        from PIL import Image
        ts = datetime.datetime.now().strftime("%H%M%S")
        path = f"debug/{ts}_{tag}.png"
        Image.fromarray(img_array).save(path)
        log(f"[DEBUG] 已保存截图: {path}")


# ============ 窗口查找 ============

user32 = ctypes.windll.user32

def find_wechat_hwnd():
    """查找微信窗口句柄，兼容新旧版本"""
    # 新版 Qt 微信
    hwnd = user32.FindWindowW("Qt51514QWindowIcon", "微信")
    if hwnd:
        return hwnd
    # 旧版微信
    hwnd = user32.FindWindowW("WeChatMainWndForPC", "微信")
    if hwnd:
        return hwnd
    # 通用查找：按标题
    hwnd = user32.FindWindowW(None, "微信")
    return hwnd

def get_window_rect(hwnd):
    """获取窗口位置和大小"""
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return (rect.left, rect.top, rect.right, rect.bottom)

def bring_to_front(hwnd):
    """将窗口置于前台"""
    try:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


# ============ 图像检测 ============

def capture_window(rect):
    """截取窗口区域的屏幕截图"""
    img = np.array(ImageGrab.grab(bbox=rect))
    return img

def color_mask(img, r_range, g_range, b_range):
    """根据颜色范围生成二值掩码"""
    r = img[:, :, 0].astype(np.int16)
    g = img[:, :, 1].astype(np.int16)
    b = img[:, :, 2].astype(np.int16)
    mask = (
        (r >= r_range[0]) & (r <= r_range[1]) &
        (g >= g_range[0]) & (g <= g_range[1]) &
        (b >= b_range[0]) & (b <= b_range[1])
    )
    return mask

def find_color_regions(mask, min_height=30, min_width=80):
    """在二值掩码中查找连续区域，返回各区域的中心坐标和尺寸"""
    h, w = mask.shape
    row_sums = np.sum(mask, axis=1)

    regions = []
    in_region = False
    y_start = 0

    for y in range(h):
        has_pixels = row_sums[y] > 15
        if has_pixels and not in_region:
            y_start = y
            in_region = True
        elif not has_pixels and in_region:
            y_end = y
            # 在这个 y 范围内找 x 边界
            region_mask = mask[y_start:y_end, :]
            col_sums = np.sum(region_mask, axis=0)
            col_idx = np.where(col_sums > 2)[0]
            if len(col_idx) > 0:
                x_start = col_idx[0]
                x_end = col_idx[-1]
                rw = x_end - x_start
                rh = y_end - y_start
                if rh >= min_height and rw >= min_width:
                    cx = (x_start + x_end) // 2
                    cy = (y_start + y_end) // 2
                    regions.append({
                        'center': (cx, cy),       # 相对于截图的坐标
                        'x': x_start, 'y': y_start,
                        'w': rw, 'h': rh,
                        'area': rh * rw,
                    })
            in_region = False

    # 处理到末尾仍在区域中的情况
    if in_region:
        y_end = h
        region_mask = mask[y_start:y_end, :]
        col_sums = np.sum(region_mask, axis=0)
        col_idx = np.where(col_sums > 2)[0]
        if len(col_idx) > 0:
            x_start = col_idx[0]
            x_end = col_idx[-1]
            rw = x_end - x_start
            rh = y_end - y_start
            if rh >= min_height and rw >= min_width:
                cx = (x_start + x_end) // 2
                cy = (y_start + y_end) // 2
                regions.append({
                    'center': (cx, cy),
                    'x': x_start, 'y': y_start,
                    'w': rw, 'h': rh,
                    'area': rh * rw,
                })

    return regions


# ============ 红包抢夺核心 ============

class RedPacketGrabber:
    def __init__(self):
        self.hwnd = None
        self.rect = None
        self.grab_count = 0
        self.running = False
        # 已点击位置，防重复
        self.clicked_centers = []
        self.max_history = 100

    def _to_screen(self, pos):
        """截图内坐标 -> 屏幕绝对坐标"""
        return (self.rect[0] + pos[0], self.rect[1] + pos[1])

    def _to_screen_chat(self, pos, chat_offset_x):
        """聊天区域截图内坐标 -> 屏幕绝对坐标"""
        return (self.rect[0] + chat_offset_x + pos[0],
                self.rect[1] + pos[1])

    def _is_clicked(self, sx, sy, threshold=25):
        """检查屏幕坐标是否已点击过"""
        for (cx, cy) in self.clicked_centers:
            if abs(sx - cx) < threshold and abs(sy - cy) < threshold:
                return True
        return False

    def _record_click(self, sx, sy):
        self.clicked_centers.append((sx, sy))
        if len(self.clicked_centers) > self.max_history:
            self.clicked_centers = self.clicked_centers[-self.max_history // 2:]

    def find_wechat(self):
        self.hwnd = find_wechat_hwnd()
        if not self.hwnd:
            return False
        self.rect = get_window_rect(self.hwnd)
        return True

    def get_chat_screenshot(self):
        """截取聊天区域（窗口右侧部分）"""
        full = capture_window(self.rect)
        w = full.shape[1]
        start_x = int(w * config.CHAT_AREA_START_X_RATIO)
        chat_img = full[:, start_x:, :]
        return chat_img, start_x

    def detect_red_packets(self, chat_img):
        """在聊天区域截图中检测红包（金橙卡片 + 红色信封 取并集）"""
        # 检测金橙色卡片主体
        card_mask = color_mask(
            chat_img,
            config.CARD_R_RANGE,
            config.CARD_G_RANGE,
            config.CARD_B_RANGE,
        )
        # 检测红色信封中心
        icon_mask = color_mask(
            chat_img,
            config.ICON_R_RANGE,
            config.ICON_G_RANGE,
            config.ICON_B_RANGE,
        )
        # 合并两个掩码
        combined = card_mask | icon_mask

        regions = find_color_regions(combined, min_height=20, min_width=40)

        if config.DEBUG_MODE:
            save_debug_img(chat_img, "chat")
            vis = np.zeros_like(chat_img)
            vis[combined] = [255, 255, 255]
            save_debug_img(vis, "mask")

        # 用密度和像素数过滤
        filtered = []
        for pkt in regions:
            region_mask = combined[pkt['y']:pkt['y']+pkt['h'], pkt['x']:pkt['x']+pkt['w']]
            pixel_count = int(np.sum(region_mask))
            area = max(pkt['w'] * pkt['h'], 1)
            density = pixel_count / area

            pkt['pixel_count'] = pixel_count
            pkt['density'] = density

            if pixel_count < config.MIN_PIXEL_COUNT:
                continue
            if density < config.MIN_DENSITY:
                continue

            # 额外验证：红包卡片内必须包含红色信封区域
            icon_in_region = icon_mask[pkt['y']:pkt['y']+pkt['h'], pkt['x']:pkt['x']+pkt['w']]
            if np.sum(icon_in_region) < 200:
                continue

            filtered.append(pkt)

        return filtered

    def detect_open_button(self, full_img):
        """检测弹窗并定位"开"按钮

        弹窗布局: 左侧信息(灰) | 中间(白) | 右侧红包卡(红)
        "开"按钮是右侧红色面板中的金色圆形按钮
        """
        r = full_img[:, :, 0].astype(int)
        g = full_img[:, :, 1].astype(int)
        b = full_img[:, :, 2].astype(int)

        # 1. 检测所有红色像素
        red_mask = (
            (r >= 215) & (r <= 250) &
            (g >= 65) & (g <= 100) &
            (b >= 50) & (b <= 85)
        )
        red_px = int(np.sum(red_mask))
        if red_px < 5000:
            if config.VERBOSE_LOG:
                log(f"  红色像素不足: {red_px}")
            return None

        if config.DEBUG_MODE:
            save_debug_img(full_img, "popup")

        # 2. 按列统计红色像素，找右侧密集红色面板
        img_h = full_img.shape[0]
        col_counts = np.sum(red_mask, axis=0)
        dense_cols = np.where(col_counts > img_h * 0.3)[0]

        if len(dense_cols) == 0:
            return None

        # 找最右边的连续段
        gaps = np.where(np.diff(dense_cols) > 5)[0]
        segments = np.split(dense_cols, gaps + 1)
        right_seg = max(segments, key=lambda s: s[-1])

        panel_x_min = int(right_seg[0])
        panel_x_max = int(right_seg[-1])

        # y 边界
        panel_mask = red_mask[:, panel_x_min:panel_x_max+1]
        panel_rows = np.where(np.any(panel_mask, axis=1))[0]
        if len(panel_rows) == 0:
            return None
        panel_y_min = int(panel_rows.min())
        panel_y_max = int(panel_rows.max())

        if config.VERBOSE_LOG:
            pw = panel_x_max - panel_x_min
            ph = panel_y_max - panel_y_min
            log(f"  右侧红色面板: ({panel_x_min},{panel_y_min})-({panel_x_max},{panel_y_max}) {pw}x{ph}")

        # 3. 在右侧面板内找金色圆环 (开按钮)
        gold_mask = (
            (r >= 220) & (r <= 250) &
            (g >= 180) & (g <= 220) &
            (b >= 130) & (b <= 175) &
            (~red_mask)
        )
        # 限制在右侧面板区域
        gold_mask[:panel_y_min, :] = False
        gold_mask[panel_y_max+1:, :] = False
        gold_mask[:, :panel_x_min] = False
        gold_mask[:, panel_x_max+1:] = False

        gold_px = int(np.sum(gold_mask))

        if gold_px > 50:
            gold_ys, gold_xs = np.where(gold_mask)
            # 按y分组找最大聚集区
            GAP = 20
            clusters = []
            cs = 0
            idx = np.argsort(gold_ys)
            gold_ys = gold_ys[idx]
            gold_xs = gold_xs[idx]
            for i in range(1, len(gold_ys)):
                if gold_ys[i] - gold_ys[i-1] > GAP:
                    clusters.append((gold_ys[cs:i], gold_xs[cs:i]))
                    cs = i
            clusters.append((gold_ys[cs:], gold_xs[cs:]))

            biggest_ys, biggest_xs = max(clusters, key=lambda c: len(c[0]))
            btn_x = int(np.mean(biggest_xs))
            btn_y = int(np.mean(biggest_ys))

            if config.VERBOSE_LOG:
                log(f"  开按钮(金色): ({btn_x}, {btn_y})")

            return (btn_x, btn_y)

        # 备选: 用红色面板相对位置
        pw = panel_x_max - panel_x_min
        ph = panel_y_max - panel_y_min
        btn_x = panel_x_min + pw // 2
        btn_y = panel_y_min + int(ph * 0.75)

        if config.VERBOSE_LOG:
            log(f"  开按钮(估算): ({btn_x}, {btn_y})")

        return (btn_x, btn_y)

    def click(self, screen_pos):
        """点击屏幕坐标"""
        x, y = screen_pos
        pyautogui.click(x, y, _pause=False)

    def try_grab_one(self):
        """尝试检测并抢一个红包，返回是否处理了一个"""
        try:
            # 每次循环更新窗口位置（用户可能移动了窗口）
            self.rect = get_window_rect(self.hwnd)

            chat_img, offset_x = self.get_chat_screenshot()
            packets = self.detect_red_packets(chat_img)

            if not packets:
                return False

            # 优先抢最下面的（最新的）红包
            packets.sort(key=lambda p: p['center'][1], reverse=True)

            for pkt in packets:
                cx, cy = pkt['center']
                sx, sy = self._to_screen_chat((cx, cy), offset_x)

                if self._is_clicked(sx, sy):
                    continue

                log(f"发现红包 @ ({sx}, {sy}) 尺寸 {pkt['w']}x{pkt['h']}")

                if not config.AUTO_GRAB:
                    beep_alert()
                    log("(仅提醒模式)")
                    self._record_click(sx, sy)
                    return False

                if config.GRAB_DELAY > 0:
                    time.sleep(config.GRAB_DELAY)

                # 第1步: 点击红包卡片
                self.click((sx, sy))
                self._record_click(sx, sy)
                log("已点击红包卡片，等待弹窗...")
                time.sleep(0.8)

                # 第2步: 截全屏查找并点击"开"按钮
                # 弹窗可能超出微信窗口范围，必须截全屏
                fullscreen = np.array(ImageGrab.grab())
                if config.DEBUG_MODE:
                    save_debug_img(fullscreen, "fullscreen_popup")
                open_pos = self.detect_open_button(fullscreen)
                if open_pos:
                    # open_pos 已经是全屏坐标，直接点击
                    log(f"点击开按钮 @ ({open_pos[0]}, {open_pos[1]})")
                    self.click(open_pos)
                    self.grab_count += 1
                    beep_alert()
                    log(f"抢到红包！第 {self.grab_count} 个")
                    time.sleep(1.0)
                else:
                    log("未找到开按钮（红包可能已被领取）")

                # 第3步: 关闭弹窗（多按几次确保关闭）
                self._close_dialog()

                # 自动回复
                if config.AUTO_REPLY:
                    self._auto_reply()

                return True

            return False

        except Exception as e:
            log(f"抢红包异常: {e}")
            # 尝试按ESC恢复
            try:
                pyautogui.press('escape')
                time.sleep(0.3)
                pyautogui.press('escape')
            except Exception:
                pass
            return False

    def _close_dialog(self):
        """关闭弹窗（多次ESC确保关闭）"""
        time.sleep(0.3)
        pyautogui.press('escape')
        time.sleep(0.2)
        pyautogui.press('escape')
        time.sleep(0.2)

    def _auto_reply(self):
        """自动回复感谢语（实验性）"""
        try:
            time.sleep(0.3)
            # 点击聊天输入框（通常在窗口底部中间）
            w = self.rect[2] - self.rect[0]
            h = self.rect[3] - self.rect[1]
            input_x = self.rect[0] + int(w * 0.6)
            input_y = self.rect[3] - 50
            self.click((input_x, input_y))
            time.sleep(0.2)
            pyautogui.typewrite(config.THANKS_TEXT, interval=0.02)
            pyautogui.press('enter')
            log(f"已回复: {config.THANKS_TEXT}")
        except Exception as e:
            if config.VERBOSE_LOG:
                log(f"自动回复失败: {e}")

    def run(self):
        self.running = True
        ensure_debug_dir()

        log("=" * 50)
        log("  微信红包助手 v2.0 (截图检测版)")
        log(f"  自动抢: {'开' if config.AUTO_GRAB else '关（仅提醒）'}")
        log(f"  间隔: {config.CHECK_INTERVAL}s | 声音: {'开' if config.SOUND_ALERT else '关'}")
        if config.DEBUG_MODE:
            log("  调试模式: 开启 (截图保存到 debug/)")
        log("=" * 50)
        log("  Ctrl+C 停止\n")

        # 等待微信窗口
        while self.running:
            if self.find_wechat():
                break
            log("等待微信窗口...请确认微信已打开")
            time.sleep(3)

        log(f"已定位微信窗口: {self.rect}")
        # bring_to_front(self.hwnd)

        consecutive_fail = 0
        scan_count = 0
        while self.running:
            try:
                if config.MAX_GRAB_COUNT > 0 and self.grab_count >= config.MAX_GRAB_COUNT:
                    log(f"已达上限 ({config.MAX_GRAB_COUNT}个)，停止")
                    break

                # 确保微信还在
                if not user32.IsWindow(self.hwnd):
                    log("微信窗口已关闭，尝试重新查找...")
                    if not self.find_wechat():
                        time.sleep(3)
                        continue
                    log(f"重新定位: {self.rect}")

                scan_count += 1
                # 每30次扫描输出一次心跳日志（约每9秒）
                if scan_count % 30 == 0:
                    log(f"监控中... 已扫描 {scan_count} 次，已抢 {self.grab_count} 个")

                self.try_grab_one()
                time.sleep(config.CHECK_INTERVAL)

            except KeyboardInterrupt:
                break
            except Exception as e:
                consecutive_fail += 1
                log(f"主循环异常 ({consecutive_fail}): {e}")
                if consecutive_fail > 10:
                    log(f"连续失败过多，暂停5秒...")
                    time.sleep(5)
                    consecutive_fail = 0
                else:
                    time.sleep(1)

        self.running = False
        log(f"\n已停止，共抢到 {self.grab_count} 个红包")


# ============ 入口 ============

def main():
    print("""
╔══════════════════════════════════════════╗
║     微信红包助手 v2.0 (截图检测版)       ║
║     适配新版 Qt 微信                     ║
╠══════════════════════════════════════════╣
║  1. 打开微信并登录                       ║
║  2. 打开要监控的群聊/私聊                ║
║  3. 脚本会自动检测红包颜色并点击         ║
║  4. Ctrl+C 停止                          ║
╚══════════════════════════════════════════╝
""")
    grabber = RedPacketGrabber()
    grabber.run()

if __name__ == '__main__':
    main()
