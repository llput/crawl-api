import asyncio
import os
import logging
from typing import Any, Optional

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter
from app.models.models import CrawlRequest, CrawlData, MarkdownRequest, MarkdownData, MarkdownFormat, ScreenshotRequest, ScreenshotData

logger = logging.getLogger(__name__)


class CrawlerException(Exception):
    """爬虫异常类"""

    def __init__(self, message: str, error_type: str = "unknown"):
        self.message = message
        self.error_type = error_type
        super().__init__(message)


class CrawlerService:
    """爬虫服务类"""

    @staticmethod
    def _is_debug_mode() -> bool:
        """检查是否为调试模式"""
        return os.environ.get('CRAWLER_DEBUG_MODE', 'false').lower() == 'true'

    @staticmethod
    def _get_extension_path() -> Optional[str]:
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

    @staticmethod
    def _create_browser_config(js_enabled: bool = True) -> BrowserConfig:
        """创建浏览器配置"""
        # 检查是否有扩展需要加载
        extension_path = CrawlerService._get_extension_path()

        # 检查调试模式
        debug_mode = CrawlerService._is_debug_mode()

        # 如果有扩展或调试模式，强制使用非无头模式
        headless = True
        if extension_path:
            headless = False
            logger.info(f"🔌 检测到扩展，将使用非无头模式: {extension_path}")
        elif debug_mode:
            headless = False
            logger.info(f"🐛 调试模式启用，将使用非无头模式")

        browser_config = BrowserConfig(
            headless=headless,
            java_script_enabled=js_enabled,
            viewport={"width": 1280, "height": 800},
            verbose=True  # 调试时启用详细日志
        )

        # 添加扩展支持
        if extension_path:
            extension_args = [
                f"--load-extension={extension_path}",
                f"--disable-extensions-except={extension_path}",
                "--disable-extensions-except-devtools"
            ]

            if not hasattr(browser_config, 'extra_args') or browser_config.extra_args is None:
                browser_config.extra_args = []

            browser_config.extra_args.extend(extension_args)
            logger.info(f"🔌 已添加扩展参数: {extension_args}")

        # 调试模式下添加额外参数
        if debug_mode:
            debug_args = [
                "--disable-web-security",  # 禁用web安全限制
                "--disable-features=VizDisplayCompositor",  # 提高兼容性
                "--allow-running-insecure-content",  # 允许不安全内容
            ]

            if not hasattr(browser_config, 'extra_args') or browser_config.extra_args is None:
                browser_config.extra_args = []

            browser_config.extra_args.extend(debug_args)
            logger.info(f"🐛 已添加调试参数: {debug_args}")

        return browser_config

    @staticmethod
    def _create_crawler_config(request: CrawlRequest) -> CrawlerRunConfig:
        """创建爬虫配置"""
        config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS if request.bypass_cache else CacheMode.ENABLED,
            page_timeout=60000,  # 60秒
            wait_for_images=request.include_images,
        )

        if request.css_selector:
            config.css_selector = request.css_selector

        return config

    @staticmethod
    def _create_markdown_crawler_config(request: MarkdownRequest) -> CrawlerRunConfig:
        """创建Markdown专用爬虫配置"""
        # 创建Markdown生成器配置
        md_options = {}
        if request.ignore_links:
            md_options["ignore_links"] = True
        if not request.escape_html:
            md_options["escape_html"] = False
        if request.body_width:
            md_options["body_width"] = request.body_width

        # 根据格式类型选择是否使用内容过滤
        if request.format in [MarkdownFormat.FIT, MarkdownFormat.BOTH]:
            # 使用内容过滤器生成更适合AI的markdown
            content_filter = PruningContentFilter(
                threshold=0.4, threshold_type="fixed")
            md_generator = DefaultMarkdownGenerator(
                content_filter=content_filter,
                options=md_options
            )
        else:
            # 原始markdown，不使用过滤器
            md_generator = DefaultMarkdownGenerator(options=md_options)

        config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS if request.bypass_cache else CacheMode.ENABLED,
            page_timeout=60000,  # 60秒
            markdown_generator=md_generator,
        )

        if request.css_selector:
            config.css_selector = request.css_selector

        return config

    async def crawl_url(self, request: CrawlRequest) -> CrawlData:
        """
        爬取单个URL - 返回纯业务数据或抛出异常

        Args:
            request: 爬取请求对象

        Returns:
            CrawlData: 爬取的业务数据

        Raises:
            CrawlerException: 爬取失败时抛出
        """
        try:
            browser_config = self._create_browser_config(request.js_enabled)
            crawler_config = self._create_crawler_config(request)

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=request.url, config=crawler_config)

                if not result.success:
                    raise CrawlerException(
                        message=getattr(result, 'error_message', '爬取失败'),
                        error_type="crawl_failed"
                    )

                # 返回纯业务数据
                return CrawlData(
                    url=request.url,
                    status_code=getattr(result, 'status_code', None),
                    markdown=result.markdown,
                    media=result.media if hasattr(result, 'media') else None,
                    links=result.links if hasattr(result, 'links') else None
                )

        except asyncio.TimeoutError:
            logger.error(f"爬取超时: {request.url}")
            raise CrawlerException(
                message="爬取超时，请稍后重试",
                error_type="timeout"
            )
        except CrawlerException:
            # 重新抛出已知异常
            raise
        except Exception as e:
            logger.error(f"爬取失败 {request.url}: {str(e)}")
            raise CrawlerException(
                message=f"爬取过程中发生错误: {str(e)}",
                error_type="unexpected"
            )

    async def crawl_markdown(self, request: MarkdownRequest) -> MarkdownData:
        """
        专门获取页面的Markdown内容 - 返回纯业务数据或抛出异常

        Args:
            request: Markdown请求对象

        Returns:
            MarkdownData: Markdown业务数据

        Raises:
            CrawlerException: 爬取失败时抛出
        """
        try:
            browser_config = self._create_browser_config(request.js_enabled)
            crawler_config = self._create_markdown_crawler_config(request)

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=request.url, config=crawler_config)

                if not result.success:
                    raise CrawlerException(
                        message=getattr(
                            result, 'error_message', 'Markdown获取失败'),
                        error_type="crawl_failed"
                    )

                # 解析结果
                title = None
                if hasattr(result, 'metadata') and result.metadata:
                    title = result.metadata.get('title')

                raw_markdown = None
                fit_markdown = None

                if hasattr(result, 'markdown'):
                    if request.format in [MarkdownFormat.RAW, MarkdownFormat.BOTH]:
                        raw_markdown = self._extract_raw_markdown(
                            result.markdown)

                    if request.format in [MarkdownFormat.FIT, MarkdownFormat.BOTH]:
                        fit_markdown = self._extract_fit_markdown(
                            result.markdown, raw_markdown)

                # 计算字数
                word_count = None
                if raw_markdown:
                    word_count = len(raw_markdown.split())
                elif fit_markdown:
                    word_count = len(fit_markdown.split())

                return MarkdownData(
                    url=request.url,
                    status_code=getattr(result, 'status_code', None),
                    raw_markdown=raw_markdown,
                    fit_markdown=fit_markdown,
                    title=title,
                    word_count=word_count
                )

        except asyncio.TimeoutError:
            logger.error(f"Markdown爬取超时: {request.url}")
            raise CrawlerException(
                message="Markdown获取超时，请稍后重试",
                error_type="timeout"
            )
        except CrawlerException:
            raise
        except Exception as e:
            logger.error(f"Markdown爬取失败 {request.url}: {str(e)}")
            raise CrawlerException(
                message=f"Markdown获取过程中发生错误: {str(e)}",
                error_type="unexpected"
            )

    @staticmethod
    def _extract_raw_markdown(markdown_result) -> str:
        """提取原始markdown内容"""
        if hasattr(markdown_result, 'raw_markdown'):
            return markdown_result.raw_markdown
        else:
            # 向后兼容，如果没有raw_markdown属性，使用markdown本身
            return markdown_result if isinstance(markdown_result, str) else str(markdown_result)

    @staticmethod
    def _extract_fit_markdown(markdown_result, raw_markdown: str = None) -> str:
        """提取经过过滤的markdown内容"""
        if hasattr(markdown_result, 'fit_markdown'):
            return markdown_result.fit_markdown
        else:
            # 如果没有fit_markdown，使用raw_markdown作为备选
            return raw_markdown

    @staticmethod
    def _create_screenshot_browser_config(request: ScreenshotRequest) -> BrowserConfig:
        """创建截图专用浏览器配置"""
        return BrowserConfig(
            headless=True,
            java_script_enabled=request.js_enabled,
            viewport={"width": request.viewport_width or 1280,
                      "height": request.viewport_height or 720},
            verbose=False
        )

    @staticmethod
    def _create_screenshot_crawler_config(request: ScreenshotRequest) -> CrawlerRunConfig:
        """创建截图专用爬虫配置"""
        config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS if request.bypass_cache else CacheMode.ENABLED,
            page_timeout=60000,  # 60秒
            screenshot=True,
        )

        if request.css_selector:
            config.css_selector = request.css_selector

        if request.wait_for:
            config.wait_until = request.wait_for

        return config

    async def take_screenshot(self, request: ScreenshotRequest) -> ScreenshotData:
        """
        截取页面截图 - 返回纯业务数据或抛出异常

        Args:
            request: 截图请求对象

        Returns:
            ScreenshotData: 截图业务数据

        Raises:
            CrawlerException: 截图失败时抛出
        """
        try:
            browser_config = self._create_screenshot_browser_config(request)
            crawler_config = self._create_screenshot_crawler_config(request)

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=request.url, config=crawler_config)

                if not result.success:
                    raise CrawlerException(
                        message=getattr(result, 'error_message', '截图失败'),
                        error_type="screenshot_failed"
                    )

                if not result.screenshot:
                    raise CrawlerException(
                        message="截图数据为空",
                        error_type="screenshot_empty"
                    )

                # 返回纯业务数据
                return ScreenshotData(
                    url=request.url,
                    status_code=getattr(result, 'status_code', None),
                    screenshot_base64=result.screenshot,
                    error_message=None
                )

        except asyncio.TimeoutError:
            logger.error(f"截图超时: {request.url}")
            raise CrawlerException(
                message="截图超时，请稍后重试",
                error_type="timeout"
            )
        except CrawlerException:
            # 重新抛出已知异常
            raise
        except Exception as e:
            logger.error(f"截图失败 {request.url}: {str(e)}")
            raise CrawlerException(
                message=f"截图过程中发生错误: {str(e)}",
                error_type="unexpected"
            )


# 创建服务实例
crawler_service = CrawlerService()
