"""
诊断脚本 - 查找微信窗口的实际属性
"""
import uiautomation as auto

print("正在查找所有窗口，请稍候...\n")

# 方法1: 遍历所有顶层窗口，查找包含"微信"关键字的
print("=" * 60)
print("方法1: 查找所有包含'微信'关键字的窗口")
print("=" * 60)

root = auto.GetRootControl()
found = False

for win in root.GetChildren():
    name = win.Name
    classname = win.ClassName
    if name and ('微信' in name or 'WeChat' in name.lower()):
        print(f"  窗口名: {name}")
        print(f"  类名:   {classname}")
        print(f"  句柄:   {win.NativeWindowHandle}")
        found = True

if not found:
    print("  未找到包含'微信'的窗口")

# 方法2: 尝试常见的微信窗口类名
print("\n" + "=" * 60)
print("方法2: 尝试常见微信窗口类名")
print("=" * 60)

class_names = [
    'WeChatMainWndForPC',
    'WeUIMainWndForPC',
    'ChatWnd',
    'CefWebViewWnd',
    'DuiHostWnd',
    'wxworkWindow',  # 企业微信
]

for cn in class_names:
    try:
        w = auto.WindowControl(ClassName=cn, searchDepth=1)
        if w.Exists(maxSearchSeconds=1):
            print(f"  找到! 类名={cn}, 窗口名={w.Name}")
        else:
            print(f"  未找到: {cn}")
    except Exception as e:
        print(f"  异常: {cn} -> {e}")

# 方法3: 列出所有可见窗口
print("\n" + "=" * 60)
print("方法3: 所有可见顶层窗口列表")
print("=" * 60)

for win in root.GetChildren():
    name = win.Name or ""
    classname = win.ClassName or ""
    if name and not name.startswith(""):
        visible = False
        try:
            visible = win.IsOffscreen == False
        except:
            pass
        if visible or name:
            print(f"  [{classname or 'N/A'}] {name[:60]}")

print("\n诊断完成。请将结果反馈，以便调整脚本。")
