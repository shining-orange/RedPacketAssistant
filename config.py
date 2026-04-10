"""配置文件 - 根据实际情况调整"""

# ============ 抢红包配置 ============

# 检测间隔（秒）
CHECK_INTERVAL = 0.3

# 是否自动抢红包（False 则只提醒不点击）
AUTO_GRAB = True

# 抢红包后是否自动回复感谢语
AUTO_REPLY = False
THANKS_TEXT = "谢谢老板！！！"

# 声音提醒
SOUND_ALERT = True

# 模拟人类反应延迟（秒），0 = 不延迟
GRAB_DELAY = 0.0

# 最大抢红包次数（0 = 不限）
MAX_GRAB_COUNT = 0

# 详细日志
VERBOSE_LOG = True

# 调试模式（保存截图到 debug/ 文件夹，用于调参）
DEBUG_MODE = False

# ============ 颜色检测参数 ============
# 如检测不准，可开启 DEBUG_MODE 截图后微调以下范围

# 红包卡片主体颜色范围 (RGB) — 金橙色
# 实测: 卡片大面积 RGB(250,157,59)
CARD_R_RANGE = (240, 255)
CARD_G_RANGE = (140, 175)
CARD_B_RANGE = (40, 80)

# 红包中心信封颜色范围 (RGB) — 红色
# 实测: 中心区域 RGB(225,73,73)
ICON_R_RANGE = (200, 255)
ICON_G_RANGE = (55, 120)
ICON_B_RANGE = (30, 95)

# 弹窗红色背景颜色范围 (RGB) — 点击红包卡片后弹出的开红包界面
# 实测: RGB(231,81,64) 和 RGB(243,85,67)
POPUP_R_RANGE = (220, 250)
POPUP_G_RANGE = (70, 100)
POPUP_B_RANGE = (55, 80)

# "开"按钮在弹窗中的相对位置（从底部算起的比例）
OPEN_BTN_FROM_BOTTOM = 0.05

# 最小像素密度（匹配像素/区域面积）
MIN_DENSITY = 0.50

# 最小匹配像素数
MIN_PIXEL_COUNT = 2000

# 聊天区域起始位置（排除左侧联系人列表，比例值）
CHAT_AREA_START_X_RATIO = 0.28
