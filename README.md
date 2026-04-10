# 微信红包助手 v2.0

基于 **截图 + 颜色检测 + 模拟点击** 实现的微信 PC 端自动抢红包工具，适配新版 Qt 微信。

## 工作原理

1. 持续截取微信窗口的聊天区域
2. 通过颜色范围匹配检测红包卡片（金橙色 + 红色信封）
3. 模拟点击红包卡片，弹出开红包界面
4. 在全屏截图中定位金色"开"按钮并点击
5. 自动关闭弹窗，继续监控下一个红包

## 快速开始

### 环境要求

- Windows 系统
- Python 3.8+
- 微信 PC 端（新版 Qt 微信）

### 安装

```bash
pip install -r requirements.txt
```

依赖列表：

| 包名 | 用途 |
|------|------|
| Pillow >= 10.0.0 | 屏幕截图 |
| numpy >= 1.24.0 | 图像处理与颜色检测 |
| pyautogui >= 0.9.54 | 模拟鼠标点击和键盘操作 |

### 使用

1. 打开微信 PC 端并登录
2. 打开要监控的群聊或私聊窗口
3. 运行脚本：

```bash
python main.py
```

4. `Ctrl+C` 停止

## 配置说明

所有配置项在 `config.py` 中修改：

### 基本配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `CHECK_INTERVAL` | `0.3` | 检测间隔（秒） |
| `SCAN_JITTER` | `0.10` | 检测间隔随机抖动（秒），实际 = `CHECK_INTERVAL` + random(0, `SCAN_JITTER`) |
| `AUTO_GRAB` | `True` | 是否自动抢红包。`False` 则只提醒不点击 |
| `AUTO_REPLY` | `False` | 抢到后是否自动回复感谢语 |
| `THANKS_TEXT` | `"谢谢老板！！！"` | 自动回复的内容 |
| `SOUND_ALERT` | `True` | 抢到红包时是否发出蜂鸣提示音 |
| `MAX_GRAB_COUNT` | `0` | 最大抢红包次数，`0` 表示不限 |
| `VERBOSE_LOG` | `True` | 输出详细日志 |
| `DEBUG_MODE` | `False` | 调试模式，保存截图到 `debug/` 目录 |

### 随机延迟配置

所有延迟均为 `random(MIN, MAX)` 范围内的随机值，模拟真实操作以规避检测。将同一组 MIN/MAX 设为相同值可关闭随机性。

| 配置项 | 默认值 (秒) | 说明 |
|--------|-------------|------|
| `CLICK_DELAY_MIN/MAX` | 0.05 ~ 0.15 | 点击红包卡片前的反应延迟 |
| `POPUP_WAIT_MIN/MAX` | 0.50 ~ 0.65 | 点击卡片后等待弹窗弹出 |
| `OPEN_DELAY_MIN/MAX` | 0.05 ~ 0.15 | 点击"开"按钮前的延迟 |
| `GRAB_DONE_WAIT_MIN/MAX` | 0.30 ~ 0.50 | 抢到红包后的恢复等待 |
| `CLOSE_PRE_MIN/MAX` | 0.10 ~ 0.20 | 关弹窗：第 1 次 ESC 前 |
| `CLOSE_ESC_MIN/MAX` | 0.08 ~ 0.18 | 关弹窗：两次 ESC 之间 |
| `CLOSE_POST_MIN/MAX` | 0.08 ~ 0.15 | 关弹窗：第 2 次 ESC 后 |
| `REPLY_PRE_MIN/MAX` | 0.10 ~ 0.20 | 自动回复：点击输入框前 |
| `REPLY_TYPE_PRE_MIN/MAX` | 0.05 ~ 0.15 | 自动回复：输入框获焦后到打字前 |
| `REPLY_CHAR_INTERVAL_MIN/MAX` | 0.02 ~ 0.06 | 自动回复：每个字符的打字间隔 |

### 颜色检测参数

| 配置项 | 默认范围 | 说明 |
|--------|----------|------|
| `CARD_R/G/B_RANGE` | R(240-255), G(140-175), B(40-80) | 红包卡片金橙色主体 |
| `ICON_R/G/B_RANGE` | R(200-255), G(55-120), B(30-95) | 红包中心红色信封 |
| `POPUP_R/G/B_RANGE` | R(220-250), G(70-100), B(55-80) | 弹窗红色背景 |
| `MIN_DENSITY` | `0.50` | 最小像素密度（匹配像素/区域面积） |
| `MIN_PIXEL_COUNT` | `2000` | 最小匹配像素数 |
| `CHAT_AREA_START_X_RATIO` | `0.28` | 聊天区域起始位置比例，排除左侧联系人列表 |

> 如果检测不准，开启 `DEBUG_MODE` 截图后用校准工具微调颜色范围。

## 辅助工具

### 校准工具 — `calibrate.py`

在截图上标记检测到的红包区域，帮助调整颜色参数。

```bash
python calibrate.py
```

使用前需先开启 `config.py` 中的 `DEBUG_MODE` 运行 `main.py` 生成截图到 `debug/` 目录。校准结果保存在 `debug/calibrate_result.png` 和 `debug/calibrate_mask.png`。

### 单步测试 — `test.py`

手动触发一次完整的抢红包流程，每一步都截图并输出详细日志，用于排查问题。

```bash
python test.py
```

在微信聊天窗口有红包时运行，测试结果截图保存在 `debug/test_*.png`。

### 诊断工具 — `diagnose.py`

查找微信窗口的实际属性（窗口类名、句柄等），用于适配不同版本的微信。

```bash
python diagnose.py
```

## 项目结构

```
红包助手/
├── main.py          # 主程序，红包监控与自动抢夺
├── config.py        # 配置文件，所有可调参数
├── calibrate.py     # 校准工具，标记检测结果辅助调参
├── test.py          # 单步测试，逐步排查检测流程
├── diagnose.py      # 诊断工具，查找微信窗口属性
├── requirements.txt # Python 依赖
└── debug/           # 调试截图输出目录（自动创建）
```

## 注意事项

- 仅适用于 Windows 系统
- 微信窗口需要保持可见状态（最小化时无法截图）
- 脚本支持窗口拖动，每次扫描会自动更新窗口位置
- 鼠标移动到屏幕左上角可触发 pyautogui 的安全退出机制
- 颜色检测参数基于特定版本的微信 UI，如微信更新可能导致检测失效，需重新校准
