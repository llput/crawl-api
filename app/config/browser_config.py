# app/config/browser_config.py
import os
from typing import Optional


class BrowserPathManager:
    """浏览器路径管理器"""

    @staticmethod
    def get_chromium_path() -> Optional[str]:
        """获取 Chromium 浏览器路径"""

        # 1. 优先使用环境变量
        env_path = os.environ.get('CHROMIUM_EXECUTABLE_PATH')
        if env_path and os.path.exists(env_path):
            return env_path

        # 2. 用户自定义路径（从配置文件读取）
        custom_path = BrowserPathManager._get_custom_path()
        if custom_path and os.path.exists(custom_path):
            return custom_path

        # 3. 自动检测常见路径
        auto_path = BrowserPathManager._auto_detect_chromium()
        if auto_path:
            return auto_path

        return None

    @staticmethod
    def _get_custom_path() -> Optional[str]:
        """从配置文件读取自定义路径"""
        config_file = Path("./browser_config.txt")
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    path = f.read().strip()
                    if path and os.path.exists(path):
                        return path
            except Exception:
                pass
        return None

    @staticmethod
    def _auto_detect_chromium() -> Optional[str]:
        """自动检测 Chromium 路径"""
        import glob
        import platform

        system = platform.system()

        if system == "Darwin":  # macOS
            patterns = [
                "/Users/*/Library/Caches/ms-playwright/chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            ]
        elif system == "Linux":
            patterns = [
                "/home/*/snap/chromium/*/usr/lib/chromium-browser/chrome",
                "/usr/bin/chromium-browser",
                "/usr/bin/google-chrome",
                "/opt/google/chrome/chrome"
            ]
        elif system == "Windows":
            patterns = [
                "C:/Users/*/AppData/Local/ms-playwright/chromium-*/chrome-win/chrome.exe",
                "C:/Program Files/Google/Chrome/Application/chrome.exe",
                "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"
            ]
        else:
            return None

        for pattern in patterns:
            matches = glob.glob(pattern)
            if matches:
                # 返回最新版本
                latest = sorted(matches, reverse=True)[0]
                if os.path.exists(latest):
                    return latest

        return None

    @staticmethod
    def set_custom_path(path: str) -> bool:
        """设置自定义浏览器路径"""
        if not os.path.exists(path):
            return False

        config_file = Path("./browser_config.txt")
        try:
            with open(config_file, 'w') as f:
                f.write(path)
            return True
        except Exception:
            return False


# 使用示例
def get_browser_executable() -> Optional[str]:
    """获取浏览器可执行文件路径"""
    path = BrowserPathManager.get_chromium_path()
    if not path:
        raise RuntimeError(
            "找不到可用的 Chromium 浏览器。请确保已安装 Playwright 浏览器：\n"
            "python -m playwright install chromium\n"
            "或设置环境变量 CHROMIUM_EXECUTABLE_PATH"
        )
    return path
