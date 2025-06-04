# app/services/auth_crawler_service.py
import asyncio
import logging
import os
import glob
from pathlib import Path
from typing import Dict, Optional

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from app.models.models import CrawlRequest, CrawlData, MarkdownRequest, MarkdownData
from app.services.crawler_service import CrawlerException

logger = logging.getLogger(__name__)


class AuthCrawlerService:
    """带认证功能的爬虫服务"""

    def __init__(self):
        # 认证配置文件存储目录
        self.auth_profiles_dir = Path("./auth_profiles")
        self.auth_profiles_dir.mkdir(parents=True, exist_ok=True)

    def get_profile_path(self, site_name: str) -> str:
        """获取指定站点的认证配置文件路径"""
        return str((self.auth_profiles_dir / site_name).resolve())

    def _get_extension_path(self) -> Optional[str]:
        """获取扩展路径"""
        # 支持环境变量配置
        env_path = os.environ.get('CHROME_EXTENSION_PATH')
        if env_path and os.path.exists(env_path):
            return env_path

        # 默认查找项目根目录下的 chrome-extension 文件夹
        project_extension_path = Path(
            "./chrome-extension/bypass-paywalls-chrome-clean")
        if project_extension_path.exists():
            return str(project_extension_path.resolve())

        # 备选路径 1: download 文件夹
        download_path = Path("./download/bypass-paywalls-chrome-clean-master")
        if download_path.exists():
            return str(download_path.resolve())

        # 备选路径 2: 用户下载目录
        home_download_path = Path.home() / "Downloads" / \
            "bypass-paywalls-chrome-clean-master"
        if home_download_path.exists():
            return str(home_download_path.resolve())

        return None

    def _create_auth_browser_config(
        self,
        site_name: str,
        js_enabled: bool = True,
        headless: bool = True
    ) -> BrowserConfig:
        """创建带认证的浏览器配置"""
        user_data_dir = self.get_profile_path(site_name)

        # 强制获取浏览器路径
        browser_path = self._get_browser_executable_path()

        # 检查是否有扩展需要加载
        extension_path = self._get_extension_path()

        # 如果有扩展，强制使用非无头模式
        if extension_path:
            headless = False
            logger.info(f"🔌 检测到扩展，将使用非无头模式: {extension_path}")

        # 创建浏览器配置
        browser_config = BrowserConfig(
            headless=headless,
            java_script_enabled=js_enabled,
            use_persistent_context=True,
            user_data_dir=user_data_dir,
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            verbose=True
        )

        # 强制设置浏览器路径
        if browser_path:
            browser_config.browser_executable_path = browser_path
            logger.info(f"✅ 强制设置浏览器路径: {browser_path}")
        else:
            # 如果自动检测失败，使用已知路径
            fallback_path = "/Users/M16/Library/Caches/ms-playwright/chromium-1169/chrome-mac/Chromium.app/Contents/MacOS/Chromium"
            if os.path.exists(fallback_path):
                browser_config.browser_executable_path = fallback_path
                logger.info(f"🔄 使用备用路径: {fallback_path}")
            else:
                logger.error("❌ 未找到可用的浏览器路径")
                raise CrawlerException(
                    message=f"未找到可用的 Chromium 浏览器。请确保已安装 Playwright 浏览器或设置正确的浏览器路径",
                    error_type="browser_not_found"
                )

        # 🆕 添加扩展支持
        if extension_path:
            # 添加扩展相关参数到 extra_args
            extension_args = [
                f"--load-extension={extension_path}",
                f"--disable-extensions-except={extension_path}",
                "--disable-extensions-except-devtools"  # 允许开发者工具扩展
            ]

            # 初始化 extra_args 如果不存在
            if not hasattr(browser_config, 'extra_args') or browser_config.extra_args is None:
                browser_config.extra_args = []

            browser_config.extra_args.extend(extension_args)
            logger.info(f"🔌 已添加扩展参数: {extension_args}")

        # 验证路径是否可执行
        if hasattr(browser_config, 'browser_executable_path') and browser_config.browser_executable_path:
            if not os.access(browser_config.browser_executable_path, os.X_OK):
                logger.warning(
                    f"⚠️ 浏览器文件不可执行，尝试修复权限: {browser_config.browser_executable_path}")
                try:
                    os.chmod(browser_config.browser_executable_path, 0o755)
                    logger.info("✅ 权限修复成功")
                except Exception as e:
                    logger.error(f"❌ 权限修复失败: {e}")

        return browser_config

    def _get_browser_executable_path(self) -> Optional[str]:
        """获取浏览器可执行文件路径"""

        # 1. 优先使用环境变量
        env_path = os.environ.get('CHROMIUM_EXECUTABLE_PATH')
        if env_path and os.path.exists(env_path):
            logger.info(f"使用环境变量指定的浏览器: {env_path}")
            return env_path

        # 2. 从配置文件读取
        config_file = Path("./browser_config.txt")
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    path = f.read().strip()
                    if path and os.path.exists(path):
                        logger.info(f"使用配置文件指定的浏览器: {path}")
                        return path
            except Exception:
                pass

        # 3. 自动检测
        auto_path = self._auto_detect_chromium()
        if auto_path:
            logger.info(f"自动检测到浏览器: {auto_path}")
            return auto_path

        # 4. 尝试用户报告的具体路径
        user_reported_path = "/Users/M16/Library/Caches/ms-playwright/chromium-1169/chrome-mac/Chromium.app/Contents/MacOS/Chromium"
        if os.path.exists(user_reported_path):
            logger.info(f"使用检测到的浏览器路径: {user_reported_path}")
            return user_reported_path

        logger.warning("未找到可用的浏览器路径")
        return None

    def _auto_detect_chromium(self) -> Optional[str]:
        """自动检测 Chromium 路径"""
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
                "/usr/bin/google-chrome"
            ]
        elif system == "Windows":
            patterns = [
                "C:/Users/*/AppData/Local/ms-playwright/chromium-*/chrome-win/chrome.exe",
                "C:/Program Files/Google/Chrome/Application/chrome.exe"
            ]
        else:
            return None

        for pattern in patterns:
            matches = glob.glob(pattern)
            if matches:
                # 选择版本号最高的
                latest = sorted(matches, reverse=True)[0]
                if os.path.exists(latest):
                    return latest

        return None

    def _create_auth_browser_config(
        self,
        site_name: str,
        js_enabled: bool = True,
        headless: bool = True
    ) -> BrowserConfig:
        """创建带认证的浏览器配置"""
        user_data_dir = self.get_profile_path(site_name)

        # 强制获取浏览器路径
        browser_path = self._get_browser_executable_path()

        # 创建浏览器配置
        browser_config = BrowserConfig(
            headless=headless,
            java_script_enabled=js_enabled,
            use_persistent_context=True,
            user_data_dir=user_data_dir,
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            verbose=True
        )

        # 强制设置浏览器路径
        if browser_path:
            browser_config.browser_executable_path = browser_path
            logger.info(f"✅ 强制设置浏览器路径: {browser_path}")
        else:
            # 如果自动检测失败，使用已知路径
            fallback_path = "/Users/M16/Library/Caches/ms-playwright/chromium-1169/chrome-mac/Chromium.app/Contents/MacOS/Chromium"
            if os.path.exists(fallback_path):
                browser_config.browser_executable_path = fallback_path
                logger.info(f"🔄 使用备用路径: {fallback_path}")
            else:
                logger.error("❌ 未找到可用的浏览器路径")
                raise CrawlerException(
                    message=f"未找到可用的 Chromium 浏览器。请确保已安装 Playwright 浏览器或设置正确的浏览器路径",
                    error_type="browser_not_found"
                )

        # 验证路径是否可执行
        if hasattr(browser_config, 'browser_executable_path') and browser_config.browser_executable_path:
            if not os.access(browser_config.browser_executable_path, os.X_OK):
                logger.warning(
                    f"⚠️ 浏览器文件不可执行，尝试修复权限: {browser_config.browser_executable_path}")
                try:
                    os.chmod(browser_config.browser_executable_path, 0o755)
                    logger.info("✅ 权限修复成功")
                except Exception as e:
                    logger.error(f"❌ 权限修复失败: {e}")

        return browser_config

    async def setup_auth_profile(
        self,
        site_name: str,
        login_url: str,
        test_url: str,
        setup_timeout: int = 300
    ) -> Dict[str, str]:
        """
        设置认证配置文件 - 打开可见浏览器供手动登录

        Args:
            site_name: 站点名称，用作配置文件名
            login_url: 登录页面URL
            test_url: 用于测试登录状态的URL
            setup_timeout: 设置超时时间（秒）

        Returns:
            Dict: 包含操作结果的字典
        """
        try:
            # 创建可见浏览器配置（用于手动登录）
            browser_config = self._create_auth_browser_config(
                site_name=site_name,
                headless=False  # 可见模式
            )

            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=setup_timeout * 1000  # 转换为毫秒
            )

            logger.info(f"正在为 {site_name} 设置认证配置文件...")
            logger.info(f"将打开浏览器窗口，请手动完成登录过程")

            async with AsyncWebCrawler(config=browser_config) as crawler:
                # 先访问登录页面
                logger.info(f"访问登录页面: {login_url}")
                login_result = await crawler.arun(url=login_url, config=config)

                if not login_result.success:
                    raise CrawlerException(
                        message=f"无法访问登录页面: {login_result.error_message}",
                        error_type="setup_failed"
                    )

                # 访问测试页面以验证登录状态并保存会话
                logger.info(f"请在浏览器中完成登录，然后脚本将验证登录状态...")
                logger.info(f"验证登录状态: {test_url}")

                test_result = await crawler.arun(url=test_url, config=config)

                if test_result.success:
                    # 检查是否登录成功的简单验证
                    content_lower = test_result.html.lower()
                    if any(keyword in content_lower for keyword in ['login', 'sign in', 'signin']) and \
                       not any(keyword in content_lower for keyword in ['logout', 'sign out', 'account', 'profile']):
                        logger.warning("可能仍未登录，请检查登录状态")
                        return {
                            "status": "warning",
                            "message": "认证配置已保存，但可能未成功登录，请检查",
                            "profile_path": self.get_profile_path(site_name)
                        }
                    else:
                        logger.info("认证配置设置成功！")
                        return {
                            "status": "success",
                            "message": "认证配置设置成功，会话已保存",
                            "profile_path": self.get_profile_path(site_name)
                        }
                else:
                    raise CrawlerException(
                        message=f"验证登录状态失败: {test_result.error_message}",
                        error_type="setup_failed"
                    )

        except Exception as e:
            logger.error(f"设置认证配置失败: {str(e)}")
            raise CrawlerException(
                message=f"设置认证配置失败: {str(e)}",
                error_type="setup_failed"
            )

    async def crawl_with_auth(
        self,
        site_name: str,
        request: CrawlRequest
    ) -> CrawlData:
        """
        使用保存的认证配置爬取URL

        Args:
            site_name: 站点名称
            request: 爬取请求

        Returns:
            CrawlData: 爬取结果
        """
        try:
            # 检查认证配置是否存在
            profile_path = self.get_profile_path(site_name)
            if not os.path.exists(profile_path):
                raise CrawlerException(
                    message=f"认证配置不存在，请先调用 setup_auth_profile 设置认证",
                    error_type="auth_required"
                )

            browser_config = self._create_auth_browser_config(
                site_name=site_name,
                js_enabled=request.js_enabled,
                headless=True  # 生产环境使用无头模式
            )

            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS if request.bypass_cache else CacheMode.ENABLED,
                page_timeout=60000,
                wait_for_images=request.include_images,
            )

            if request.css_selector:
                config.css_selector = request.css_selector

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=request.url, config=config)

                if not result.success:
                    # 检查是否被重定向到登录页面
                    if result.status_code in [401, 403] or \
                       any(keyword in result.html.lower() for keyword in ['login', 'sign in', 'signin']):
                        raise CrawlerException(
                            message="认证已过期，请重新设置认证配置",
                            error_type="auth_expired"
                        )
                    else:
                        raise CrawlerException(
                            message=getattr(result, 'error_message', '爬取失败'),
                            error_type="crawl_failed"
                        )

                return CrawlData(
                    url=request.url,
                    status_code=getattr(result, 'status_code', None),
                    markdown=result.markdown,
                    media=result.media if hasattr(result, 'media') else None,
                    links=result.links if hasattr(result, 'links') else None
                )

        except CrawlerException:
            raise
        except Exception as e:
            logger.error(f"认证爬取失败 {request.url}: {str(e)}")
            raise CrawlerException(
                message=f"认证爬取过程中发生错误: {str(e)}",
                error_type="unexpected"
            )

    async def crawl_markdown_with_auth(
        self,
        site_name: str,
        request: MarkdownRequest
    ) -> MarkdownData:
        """
        使用保存的认证配置获取Markdown

        Args:
            site_name: 站点名称
            request: Markdown请求

        Returns:
            MarkdownData: Markdown数据
        """
        try:
            # 检查认证配置是否存在
            profile_path = self.get_profile_path(site_name)
            if not os.path.exists(profile_path):
                raise CrawlerException(
                    message=f"认证配置不存在，请先设置认证",
                    error_type="auth_required"
                )

            browser_config = self._create_auth_browser_config(
                site_name=site_name,
                js_enabled=request.js_enabled,
                headless=True
            )

            # 创建Markdown专用配置（这里简化处理，实际可以参考原服务的markdown配置）
            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS if request.bypass_cache else CacheMode.ENABLED,
                page_timeout=60000,
            )

            if request.css_selector:
                config.css_selector = request.css_selector

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=request.url, config=config)

                if not result.success:
                    if result.status_code in [401, 403] or \
                       any(keyword in result.html.lower() for keyword in ['login', 'sign in']):
                        raise CrawlerException(
                            message="认证已过期，请重新设置认证配置",
                            error_type="auth_expired"
                        )
                    else:
                        raise CrawlerException(
                            message=getattr(
                                result, 'error_message', 'Markdown获取失败'),
                            error_type="crawl_failed"
                        )

                # 解析结果
                title = None
                if hasattr(result, 'metadata') and result.metadata:
                    title = result.metadata.get('title')

                raw_markdown = result.markdown if hasattr(
                    result, 'markdown') else None
                word_count = len(raw_markdown.split()) if raw_markdown else 0

                return MarkdownData(
                    url=request.url,
                    status_code=getattr(result, 'status_code', None),
                    raw_markdown=raw_markdown,
                    fit_markdown=raw_markdown,  # 简化处理，实际可以添加过滤逻辑
                    title=title,
                    word_count=word_count
                )

        except CrawlerException:
            raise
        except Exception as e:
            logger.error(f"认证Markdown爬取失败 {request.url}: {str(e)}")
            raise CrawlerException(
                message=f"认证Markdown获取过程中发生错误: {str(e)}",
                error_type="unexpected"
            )

    def list_auth_profiles(self) -> Dict[str, Dict]:
        """列出所有已设置的认证配置"""
        profiles = {}

        for profile_dir in self.auth_profiles_dir.iterdir():
            if profile_dir.is_dir():
                profiles[profile_dir.name] = {
                    "site_name": profile_dir.name,
                    "profile_path": str(profile_dir.resolve()),
                    "created_time": profile_dir.stat().st_mtime
                }

        return profiles

    async def debug_setup_auth_profile(
        self,
        site_name: str,
        login_url: str,
        test_url: str,
        setup_timeout: int = 300
    ) -> Dict[str, str]:
        """
        调试版认证设置 - 用于排查浏览器关闭问题
        """
        try:
            # 参数规范化
            if setup_timeout > 1000:
                setup_timeout = setup_timeout // 1000
            setup_timeout = max(60, min(setup_timeout, 600))

            logger.info(f"🔧 调试模式 - 设置超时: {setup_timeout} 秒")

            # 创建浏览器配置
            browser_config = self._create_auth_browser_config(
                site_name=site_name,
                headless=False
            )

            logger.info("🌐 正在启动浏览器...")

            async with AsyncWebCrawler(config=browser_config) as crawler:
                logger.info("✅ 浏览器已启动")

                try:
                    # 第一步：尝试打开登录页面
                    logger.info(f"📖 正在打开: {login_url}")

                    config = CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        page_timeout=30000  # 30秒
                    )

                    result = await crawler.arun(url=login_url, config=config)

                    if result.success:
                        logger.info("✅ 页面加载成功")
                        logger.info("🚨 浏览器应该现在是打开状态，请检查！")

                        # 简单等待 - 不做任何复杂操作
                        wait_time = min(setup_timeout, 300)  # 最多等5分钟
                        logger.info(f"⏰ 开始等待 {wait_time} 秒...")

                        # 分段等待，每30秒报告一次
                        for i in range(0, wait_time, 30):
                            remaining = wait_time - i
                            logger.info(f"⏰ 剩余等待时间: {remaining} 秒")
                            logger.info("   请在浏览器中完成登录...")
                            await asyncio.sleep(min(30, remaining))

                        logger.info("✅ 等待完成，准备验证")

                        # 验证步骤
                        if test_url != login_url:
                            logger.info(f"🔍 验证登录状态: {test_url}")
                            verify_result = await crawler.arun(url=test_url, config=config)

                            if verify_result.success:
                                logger.info("✅ 验证页面访问成功")
                                return {
                                    "status": "success",
                                    "message": "调试模式完成 - 请检查实际登录状态",
                                    "profile_path": self.get_profile_path(site_name)
                                }
                            else:
                                logger.error(
                                    f"❌ 验证页面访问失败: {verify_result.error_message}")
                        else:
                            logger.info("🔄 测试URL与登录URL相同，跳过验证")
                            return {
                                "status": "warning",
                                "message": "调试模式完成 - 建议使用不同的测试URL",
                                "profile_path": self.get_profile_path(site_name)
                            }

                    else:
                        logger.error(f"❌ 页面加载失败: {result.error_message}")
                        raise CrawlerException(
                            message=f"无法打开登录页面: {result.error_message}",
                            error_type="setup_failed"
                        )

                except Exception as e:
                    logger.error(f"❌ 内部异常: {str(e)}")
                    # 即使有异常也要等待，让用户看到浏览器
                    logger.info("🚨 出现异常但继续等待，让您检查浏览器状态...")
                    await asyncio.sleep(60)  # 等待1分钟
                    raise

            logger.info("🔚 浏览器即将关闭")

        except Exception as e:
            logger.error(f"设置失败: {str(e)}")
            raise CrawlerException(
                message=f"调试设置失败: {str(e)}",
                error_type="setup_failed"
            )

    def delete_auth_profile(self, site_name: str) -> bool:
        """删除指定的认证配置"""
        import shutil

        profile_path = Path(self.get_profile_path(site_name))
        if profile_path.exists():
            shutil.rmtree(profile_path)
            logger.info(f"已删除认证配置: {site_name}")
            return True
        return False

    async def manual_setup_auth_profile(
        self,
        site_name: str,
        login_url: str,
        test_url: str,
        setup_timeout: int = 600
    ) -> Dict[str, str]:
        """
        手动控制版认证设置 - 用户通过API控制流程
        """
        try:
            # 创建浏览器配置
            browser_config = self._create_auth_browser_config(
                site_name=site_name,
                headless=False
            )

            logger.info(f"🚀 开始手动控制认证设置: {site_name}")

            async with AsyncWebCrawler(config=browser_config) as crawler:
                # 第一步：打开登录页面
                logger.info(f"📖 打开登录页面: {login_url}")

                config = CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    page_timeout=30000
                )

                result = await crawler.arun(url=login_url, config=config)

                if not result.success:
                    raise CrawlerException(
                        message=f"无法打开登录页面: {result.error_message}",
                        error_type="setup_failed"
                    )

                logger.info("✅ 浏览器已打开，登录页面加载完成")
                logger.info("=" * 60)
                logger.info("🔑 请在浏览器中完成登录，然后：")
                logger.info("   1. 调用 /api/v1/auth-crawl/verify-login 验证登录")
                logger.info("   2. 或调用 /api/v1/auth-crawl/close-browser 关闭浏览器")
                logger.info("=" * 60)

                # 保持浏览器打开，等待用户调用其他API
                # 使用一个长时间的等待，但不做任何操作
                wait_time = min(setup_timeout, 1800)  # 最多30分钟
                logger.info(f"⏰ 浏览器将保持打开 {wait_time//60} 分钟")

                # 创建一个标记文件表示浏览器正在运行
                browser_flag_file = Path(
                    f"./auth_profiles/{site_name}_browser_active")
                browser_flag_file.parent.mkdir(parents=True, exist_ok=True)
                browser_flag_file.write_text("active")

                try:
                    # 定期检查标记文件，如果被删除就退出
                    for i in range(0, wait_time, 10):
                        if not browser_flag_file.exists():
                            logger.info("🛑 检测到停止信号，准备关闭浏览器")
                            break

                        remaining = wait_time - i
                        if remaining % 300 == 0:  # 每5分钟提醒一次
                            logger.info(f"⏰ 浏览器仍然打开，剩余 {remaining//60} 分钟")

                        await asyncio.sleep(10)

                    # 清理标记文件
                    if browser_flag_file.exists():
                        browser_flag_file.unlink()

                    # 最后验证一次登录状态
                    logger.info(f"🔍 最终验证登录状态: {test_url}")
                    verify_result = await crawler.arun(url=test_url, config=config)

                    if verify_result.success:
                        analysis = self._analyze_login_status(
                            verify_result, site_name)
                        logger.info(f"📊 最终登录状态: {analysis['status']}")
                        return analysis
                    else:
                        return {
                            "status": "warning",
                            "message": "浏览器会话已保存，但无法验证最终登录状态",
                            "profile_path": self.get_profile_path(site_name)
                        }

                finally:
                    # 确保清理标记文件
                    if browser_flag_file.exists():
                        browser_flag_file.unlink()

            logger.info("🔚 浏览器已关闭")
            return {
                "status": "completed",
                "message": "手动认证设置流程完成",
                "profile_path": self.get_profile_path(site_name)
            }

        except Exception as e:
            logger.error(f"手动认证设置失败: {str(e)}")
            raise CrawlerException(
                message=f"手动认证设置失败: {str(e)}",
                error_type="setup_failed"
            )

    async def verify_login_status(self, site_name: str, test_url: str) -> Dict[str, str]:
        """验证当前登录状态 - 不关闭浏览器"""
        try:
            # 检查浏览器是否还在运行
            browser_flag_file = Path(
                f"./auth_profiles/{site_name}_browser_active")
            if not browser_flag_file.exists():
                return {
                    "status": "error",
                    "message": "浏览器会话不存在或已关闭"
                }

            # 使用现有会话验证
            browser_config = self._create_auth_browser_config(
                site_name=site_name,
                headless=True  # 后台验证
            )

            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=30000
            )

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=test_url, config=config)

                if result.success:
                    return self._analyze_login_status(result, site_name)
                else:
                    return {
                        "status": "error",
                        "message": f"验证失败: {result.error_message}"
                    }

        except Exception as e:
            return {
                "status": "error",
                "message": f"验证过程中出错: {str(e)}"
            }

    async def close_browser_session(self, site_name: str) -> Dict[str, str]:
        """关闭浏览器会话"""
        try:
            browser_flag_file = Path(
                f"./auth_profiles/{site_name}_browser_active")
            if browser_flag_file.exists():
                browser_flag_file.unlink()
                return {
                    "status": "success",
                    "message": "浏览器关闭信号已发送"
                }
            else:
                return {
                    "status": "warning",
                    "message": "浏览器会话不存在或已关闭"
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"关闭浏览器时出错: {str(e)}"
            }

    async def simple_setup_auth_profile(
        self,
        site_name: str,
        login_url: str,
        test_url: str,
        setup_timeout: int = 300,
        check_interval: int = 10
    ) -> Dict[str, str]:
        """
        一键认证设置 - 自动检测登录状态并关闭浏览器

        Args:
            site_name: 站点名称
            login_url: 登录页面URL
            test_url: 测试页面URL
            setup_timeout: 总超时时间（秒）
            check_interval: 检测间隔（秒）

        Returns:
            Dict: 设置结果
        """
        try:
            # 创建浏览器配置
            browser_config = self._create_auth_browser_config(
                site_name=site_name,
                headless=False
            )

            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=30000
            )

            logger.info(f"🚀 开始一键认证设置: {site_name}")
            logger.info("📖 浏览器将会打开，请在浏览器中完成登录")
            logger.info("✨ 登录完成后会自动检测并关闭浏览器")

            async with AsyncWebCrawler(config=browser_config) as crawler:
                # 第一步：打开登录页面
                logger.info(f"📖 正在打开登录页面: {login_url}")
                result = await crawler.arun(url=login_url, config=config)

                if not result.success:
                    raise CrawlerException(
                        message=f"无法打开登录页面: {result.error_message}",
                        error_type="setup_failed"
                    )

                logger.info("✅ 登录页面已打开，请在浏览器中完成登录...")

                # 第二步：定期检测登录状态
                total_wait = 0
                login_detected = False
                last_notification = 0

                while total_wait < setup_timeout and not login_detected:
                    await asyncio.sleep(check_interval)
                    total_wait += check_interval

                    # 每60秒提醒一次
                    if total_wait - last_notification >= 60:
                        remaining = setup_timeout - total_wait
                        logger.info(f"⏰ 等待登录中... 剩余时间: {remaining} 秒")
                        last_notification = total_wait

                    try:
                        # 检测登录状态
                        test_result = await crawler.arun(url=test_url, config=config)

                        if test_result.success:
                            # 分析页面内容判断是否已登录
                            analysis = self._analyze_login_status(
                                test_result, site_name)

                            if analysis['status'] in ['success', 'likely_logged_in']:
                                login_detected = True
                                logger.info("🎉 检测到登录成功！")
                                logger.info("🔒 正在保存认证配置...")

                                # 再次访问测试页面确保会话保存
                                await crawler.arun(url=test_url, config=config)

                                return {
                                    "status": "success",
                                    "message": "一键认证设置完成，登录状态已保存",
                                    "profile_path": self.get_profile_path(site_name),
                                    "login_detected_at": f"{total_wait}秒"
                                }

                    except Exception as e:
                        # 检测过程中的错误不中断流程
                        logger.debug(f"检测登录状态时出错: {str(e)}")
                        continue

                # 超时处理
                if not login_detected:
                    logger.warning("⚠️ 未检测到登录成功，但会话可能已保存")
                    return {
                        "status": "timeout",
                        "message": "设置超时，但认证配置可能已保存，请尝试使用",
                        "profile_path": self.get_profile_path(site_name)
                    }

            logger.info("🔚 浏览器已自动关闭")

        except Exception as e:
            logger.error(f"一键认证设置失败: {str(e)}")
            raise CrawlerException(
                message=f"一键认证设置失败: {str(e)}",
                error_type="setup_failed"
            )

    def _analyze_login_status(self, result, site_name: str) -> Dict[str, str]:
        """分析页面内容判断登录状态"""
        try:
            content_lower = result.html.lower()

            # 通用登录成功指标
            success_indicators = [
                'logout', 'sign out', 'profile', 'account', 'dashboard',
                'settings', 'my account', 'user menu', 'welcome'
            ]

            # 通用未登录指标
            login_indicators = [
                'login', 'sign in', 'signin', 'log in', 'authenticate'
            ]

            # 站点特定指标
            if site_name == "medium_com":
                success_indicators.extend(
                    ['write', 'stories', 'following', 'notifications'])
                login_indicators.extend(['get started', 'sign up'])
            elif site_name == "investors_com":
                success_indicators.extend(
                    ['premium', 'watchlist', 'portfolio'])
                login_indicators.extend(['subscribe', 'free trial'])

            # 计算指标
            success_count = sum(
                1 for indicator in success_indicators if indicator in content_lower)
            login_count = sum(
                1 for indicator in login_indicators if indicator in content_lower)

            # 判断逻辑
            if success_count > login_count and success_count >= 2:
                return {
                    "status": "success",
                    "message": f"登录成功 (成功指标: {success_count}, 登录指标: {login_count})",
                    "confidence": "high"
                }
            elif success_count > 0 and login_count == 0:
                return {
                    "status": "likely_logged_in",
                    "message": f"可能已登录 (成功指标: {success_count})",
                    "confidence": "medium"
                }
            elif login_count > success_count:
                return {
                    "status": "not_logged_in",
                    "message": f"尚未登录 (登录指标: {login_count})",
                    "confidence": "high"
                }
            else:
                return {
                    "status": "uncertain",
                    "message": "无法确定登录状态",
                    "confidence": "low"
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"分析登录状态时出错: {str(e)}",
                "confidence": "none"
            }

    async def interactive_setup_auth_profile(
        self,
        site_name: str,
        login_url: str,
        test_url: str,
        setup_timeout: int = 600
    ) -> Dict[str, str]:
        """
        交互式认证设置 - 用户手动确认登录完成

        流程：
        1. 打开浏览器到登录页面
        2. 用户在浏览器中完成登录
        3. 用户在浏览器地址栏访问特殊确认URL来确认登录完成
        4. 系统检测到确认信号后保存配置并关闭浏览器

        Args:
            site_name: 站点名称
            login_url: 登录页面URL
            test_url: 测试页面URL
            setup_timeout: 总超时时间（秒）

        Returns:
            Dict: 设置结果
        """
        try:
            # 创建浏览器配置
            browser_config = self._create_auth_browser_config(
                site_name=site_name,
                headless=False
            )

            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=30000
            )

            # 生成确认URL
            confirm_url = f"data:text/html,<html><body><h1>认证设置完成!</h1><p>站点: {site_name}</p><p>请关闭此浏览器窗口</p><script>setTimeout(()=>{{window.close();}}, 3000);</script></body></html>"

            logger.info(f"🚀 开始交互式认证设置: {site_name}")
            logger.info("=" * 60)
            logger.info("📖 浏览器即将打开，请按以下步骤操作：")
            logger.info("   1. 在浏览器中完成登录")
            logger.info(f"   2. 登录成功后，在地址栏输入: about:blank")
            logger.info("   3. 然后输入以下确认地址:")
            logger.info(f"      {confirm_url[:100]}...")
            logger.info("   4. 或者直接关闭浏览器窗口")
            logger.info("=" * 60)

            async with AsyncWebCrawler(config=browser_config) as crawler:
                # 第一步：打开登录页面
                logger.info(f"📖 正在打开登录页面: {login_url}")
                result = await crawler.arun(url=login_url, config=config)

                if not result.success:
                    raise CrawlerException(
                        message=f"无法打开登录页面: {result.error_message}",
                        error_type="setup_failed"
                    )

                logger.info("✅ 登录页面已打开")
                logger.info("🔑 请在浏览器中完成登录...")

                # 等待用户操作 - 定期检测浏览器是否还活着
                total_wait = 0
                check_interval = 5
                last_notification = 0

                while total_wait < setup_timeout:
                    await asyncio.sleep(check_interval)
                    total_wait += check_interval

                    # 每120秒提醒一次
                    if total_wait - last_notification >= 120:
                        remaining = setup_timeout - total_wait
                        logger.info(f"⏰ 等待用户操作... 剩余时间: {remaining//60} 分钟")
                        logger.info("   登录完成后请关闭浏览器窗口")
                        last_notification = total_wait

                    try:
                        # 尝试访问测试页面验证浏览器状态
                        # 这里不做登录状态判断，只是保持会话活跃
                        test_result = await crawler.arun(url=test_url, config=config)

                        # 检查是否用户尝试访问确认页面
                        if test_result.success and "认证设置完成" in test_result.html:
                            logger.info("🎉 检测到用户确认信号！")
                            break

                    except Exception as e:
                        # 如果出现连接错误，可能是浏览器被关闭了
                        if "disconnected" in str(e).lower() or "closed" in str(e).lower():
                            logger.info("🔚 检测到浏览器已关闭")
                            break
                        # 其他错误继续等待
                        continue

                # 最终验证和保存
                logger.info("💾 正在保存认证配置...")

                try:
                    # 最后验证一次登录状态
                    final_result = await crawler.arun(url=test_url, config=config)
                    if final_result.success:
                        # 简单检查是否还有明显的登录提示
                        content_lower = final_result.html.lower()
                        obvious_login_signs = ['sign in',
                                               'log in', 'login', 'sign up']

                        login_signs_count = sum(
                            1 for sign in obvious_login_signs if sign in content_lower)

                        if login_signs_count <= 2:  # 容忍少量登录提示（可能是页脚等）
                            status = "success"
                            message = "认证配置设置成功，登录状态已保存"
                        else:
                            status = "warning"
                            message = f"认证配置已保存，但检测到{login_signs_count}个登录提示，请验证登录状态"
                    else:
                        status = "warning"
                        message = "认证配置已保存，但无法验证最终状态"

                except Exception:
                    status = "completed"
                    message = "认证配置已保存，用户已关闭浏览器"

                return {
                    "status": status,
                    "message": message,
                    "profile_path": self.get_profile_path(site_name),
                    "duration": f"{total_wait}秒"
                }

            logger.info("🔚 浏览器会话已结束")

        except Exception as e:
            logger.error(f"交互式认证设置失败: {str(e)}")
            raise CrawlerException(
                message=f"交互式认证设置失败: {str(e)}",
                error_type="setup_failed"
            )

    async def quick_setup_auth_profile(
        self,
        site_name: str,
        login_url: str,
        test_url: str,
        wait_time: int = 120
    ) -> Dict[str, str]:
        """
        快速认证设置 - 固定等待时间版本

        Args:
            site_name: 站点名称
            login_url: 登录页面URL
            test_url: 测试页面URL
            wait_time: 等待时间（秒），默认2分钟

        Returns:
            Dict: 设置结果
        """
        try:
            browser_config = self._create_auth_browser_config(
                site_name=site_name,
                headless=False
            )

            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=30000
            )

            logger.info(f"🚀 快速认证设置: {site_name}")
            logger.info(f"⏰ 将等待 {wait_time} 秒供您完成登录")

            async with AsyncWebCrawler(config=browser_config) as crawler:
                # 打开登录页面
                logger.info(f"📖 正在打开登录页面: {login_url}")
                result = await crawler.arun(url=login_url, config=config)

                if not result.success:
                    raise CrawlerException(
                        message=f"无法打开登录页面: {result.error_message}",
                        error_type="setup_failed"
                    )

                logger.info("✅ 登录页面已打开，请开始登录...")

                # 分段等待，每30秒提醒一次
                for i in range(0, wait_time, 30):
                    remaining = wait_time - i
                    logger.info(f"⏰ 等待登录中... 剩余时间: {remaining} 秒")
                    await asyncio.sleep(min(30, remaining))

                logger.info("⏰ 等待时间结束，正在保存配置...")

                # 访问测试页面保存会话
                try:
                    await crawler.arun(url=test_url, config=config)
                    logger.info("💾 会话已保存")
                except Exception:
                    logger.warning("⚠️ 保存会话时出现警告，但配置可能仍有效")

                return {
                    "status": "completed",
                    "message": f"快速认证设置完成，已等待{wait_time}秒",
                    "profile_path": self.get_profile_path(site_name)
                }

            logger.info("🔚 浏览器已关闭")

        except Exception as e:
            logger.error(f"快速认证设置失败: {str(e)}")
            raise CrawlerException(
                message=f"快速认证设置失败: {str(e)}",
                error_type="setup_failed"
            )

    async def quick_setup_auth_profile(
        self,
        site_name: str,
        login_url: str,
        test_url: str,
        wait_time: int = 120
    ) -> Dict[str, str]:
        """
        快速认证设置 - 修复浏览器自动关闭问题

        Args:
            site_name: 站点名称
            login_url: 登录页面URL
            test_url: 测试页面URL
            wait_time: 等待时间（秒），默认2分钟

        Returns:
            Dict: 设置结果
        """
        try:
            browser_config = self._create_auth_browser_config(
                site_name=site_name,
                headless=False
            )

            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=60000  # 增加页面超时时间
            )

            logger.info(f"🚀 快速认证设置: {site_name}")
            logger.info(f"⏰ 将等待 {wait_time} 秒供您完成登录")

            async with AsyncWebCrawler(config=browser_config) as crawler:
                # 打开登录页面
                logger.info(f"📖 正在打开登录页面: {login_url}")
                result = await crawler.arun(url=login_url, config=config)

                if not result.success:
                    raise CrawlerException(
                        message=f"无法打开登录页面: {result.error_message}",
                        error_type="setup_failed"
                    )

                logger.info("✅ 登录页面已打开，请开始登录...")

                # 修复：在等待期间保持页面活跃，防止被自动关闭
                elapsed_time = 0
                check_interval = 30  # 每30秒检查一次

                while elapsed_time < wait_time:
                    remaining = wait_time - elapsed_time
                    logger.info(f"⏰ 等待登录中... 剩余时间: {remaining} 秒")

                    # 等待时间（但不超过剩余时间）
                    sleep_time = min(check_interval, remaining)
                    await asyncio.sleep(sleep_time)
                    elapsed_time += sleep_time

                    # 关键修复：定期访问页面保持活跃，防止被关闭
                    try:
                        # 使用更短的超时时间进行轻量级检查
                        keep_alive_config = CrawlerRunConfig(
                            cache_mode=CacheMode.BYPASS,
                            page_timeout=10000  # 10秒超时
                        )

                        # 访问当前页面保持活跃（不输出结果）
                        await crawler.arun(url=login_url, config=keep_alive_config)
                        logger.debug("🔄 页面保活检查完成")

                    except Exception as e:
                        # 如果保活失败，记录但继续等待
                        logger.debug(f"保活检查出现异常: {str(e)}")
                        continue

                logger.info("⏰ 等待时间结束，正在保存认证配置...")

                # 访问测试页面保存会话
                try:
                    final_config = CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        page_timeout=30000
                    )
                    test_result = await crawler.arun(url=test_url, config=final_config)

                    if test_result.success:
                        logger.info("💾 认证会话已保存")

                        # 简单验证登录状态
                        content_lower = test_result.html.lower()
                        login_indicators = ['sign in',
                                            'log in', 'login', 'sign up']
                        login_count = sum(
                            1 for indicator in login_indicators if indicator in content_lower)

                        if login_count <= 2:
                            status = "success"
                            message = f"认证设置成功，等待时间{wait_time}秒"
                        else:
                            status = "warning"
                            message = f"认证配置已保存，但检测到{login_count}个登录提示，建议验证"
                    else:
                        status = "completed"
                        message = f"认证设置完成，等待时间{wait_time}秒，请测试使用"

                except Exception as e:
                    logger.warning(f"保存会话时出现警告: {str(e)}")
                    status = "completed"
                    message = f"认证设置完成，等待时间{wait_time}秒，配置可能已保存"

                return {
                    "status": status,
                    "message": message,
                    "profile_path": self.get_profile_path(site_name)
                }

            logger.info("🔚 浏览器已关闭")

        except Exception as e:
            logger.error(f"快速认证设置失败: {str(e)}")
            raise CrawlerException(
                message=f"快速认证设置失败: {str(e)}",
                error_type="setup_failed"
            )

    async def simple_wait_setup_auth_profile(
        self,
        site_name: str,
        login_url: str,
        test_url: str,
        wait_time: int = 120
    ) -> Dict[str, str]:
        """
        简单等待版认证设置 - 最小化干预

        策略：打开页面后纯等待，最后保存，避免中间操作导致页面关闭
        """
        try:
            browser_config = self._create_auth_browser_config(
                site_name=site_name,
                headless=False
            )

            # 设置较长的页面超时时间
            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=max(wait_time * 1000 + 30000,
                                 60000)  # 等待时间+30秒的缓冲
            )

            logger.info(f"🚀 简单等待版认证设置: {site_name}")
            logger.info(f"⏰ 浏览器将保持打开 {wait_time} 秒")
            logger.info("🔑 请在浏览器中完成登录，期间请勿关闭浏览器")

            async with AsyncWebCrawler(config=browser_config) as crawler:
                # 第一步：打开登录页面
                logger.info(f"📖 正在打开登录页面: {login_url}")
                result = await crawler.arun(url=login_url, config=config)

                if not result.success:
                    raise CrawlerException(
                        message=f"无法打开登录页面: {result.error_message}",
                        error_type="setup_failed"
                    )

                logger.info("✅ 登录页面已打开")
                logger.info("💡 请在浏览器中完成登录...")

                # 第二步：纯等待，避免任何可能触发页面关闭的操作
                for i in range(wait_time // 30):
                    remaining = wait_time - (i * 30)
                    logger.info(f"⏰ 等待中... 剩余约 {remaining} 秒")
                    await asyncio.sleep(30)

                # 处理剩余的不足30秒的时间
                final_wait = wait_time % 30
                if final_wait > 0:
                    logger.info(f"⏰ 最后等待 {final_wait} 秒...")
                    await asyncio.sleep(final_wait)

                logger.info("⏰ 等待完成，正在保存认证状态...")

                # 第三步：访问测试页面以保存认证状态
                try:
                    save_config = CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        page_timeout=30000
                    )

                    save_result = await crawler.arun(url=test_url, config=save_config)

                    if save_result.success:
                        logger.info("💾 认证状态已保存")
                        return {
                            "status": "completed",
                            "message": f"简单等待版设置完成，已等待{wait_time}秒",
                            "profile_path": self.get_profile_path(site_name)
                        }
                    else:
                        logger.warning("保存认证状态时出现问题，但配置文件可能已生成")
                        return {
                            "status": "warning",
                            "message": f"设置完成但保存状态异常，已等待{wait_time}秒，请测试使用",
                            "profile_path": self.get_profile_path(site_name)
                        }

                except Exception as e:
                    logger.warning(f"保存阶段出现异常: {str(e)}")
                    return {
                        "status": "completed",
                        "message": f"设置完成，已等待{wait_time}秒，配置可能已保存",
                        "profile_path": self.get_profile_path(site_name)
                    }

            logger.info("🔚 浏览器已关闭")

        except Exception as e:
            logger.error(f"简单等待版认证设置失败: {str(e)}")
            raise CrawlerException(
                message=f"简单等待版认证设置失败: {str(e)}",
                error_type="setup_failed"
            )


# 创建服务实例
auth_crawler_service = AuthCrawlerService()
