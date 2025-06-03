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

    def delete_auth_profile(self, site_name: str) -> bool:
        """删除指定的认证配置"""
        import shutil

        profile_path = Path(self.get_profile_path(site_name))
        if profile_path.exists():
            shutil.rmtree(profile_path)
            logger.info(f"已删除认证配置: {site_name}")
            return True
        return False


# 创建服务实例
auth_crawler_service = AuthCrawlerService()
