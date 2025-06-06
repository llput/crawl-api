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
        from pathlib import Path
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

    # @staticmethod
    # def _create_browser_config(js_enabled: bool = True) -> BrowserConfig:
    #     """创建浏览器配置 - 单实例修复版本"""
    #     # 检查是否有扩展需要加载
    #     extension_path = CrawlerService._get_extension_path()

    #     # 检查调试模式
    #     debug_mode = CrawlerService._is_debug_mode()

    #     # 🔧 关键修复：如果有扩展，强制使用非无头模式以确保插件正常工作
    #     headless = True
    #     user_data_dir = None

    #     if extension_path:
    #         headless = False  # 插件在无头模式下可能不工作
    #         # 🆕 使用持久化用户数据目录确保插件配置保持
    #         user_data_dir = "./extension_browser_profile"
    #         logger.info(f"🔌 检测到扩展，使用单实例配置: {extension_path}")
    #     elif debug_mode:
    #         headless = False
    #         user_data_dir = "./debug_browser_profile"
    #         logger.info(f"🐛 调试模式启用，使用单实例配置")

    #     browser_config = BrowserConfig(
    #         headless=headless,
    #         java_script_enabled=js_enabled,
    #         viewport={"width": 1280, "height": 800},
    #         verbose=True,
    #         # 🆕 关键配置：确保单一浏览器实例
    #         user_data_dir=user_data_dir,
    #         use_persistent_context=True if user_data_dir else False,
    #     )

    #     # 🔧 修复扩展配置
    #     if extension_path:
    #         extension_args = [
    #             f"--load-extension={extension_path}",
    #             f"--disable-extensions-except={extension_path}",
    #             "--disable-extensions-except-devtools",
    #             "--enable-extensions",  # 确保扩展启用
    #             # 🆕 单实例相关参数
    #             "--no-first-run",
    #             "--no-default-browser-check",
    #             "--disable-default-apps",
    #             # 🆕 付费墙绕过相关参数
    #             "--disable-web-security",  # 对某些付费墙绕过有帮助
    #             "--disable-features=VizDisplayCompositor",  # 提高兼容性
    #             "--allow-running-insecure-content",  # 允许不安全内容
    #             # 🆕 确保扩展在正确的进程中运行
    #             "--disable-extensions-file-access-check",
    #             "--enable-extension-activity-logging",
    #         ]

    #         if not hasattr(browser_config, 'extra_args') or browser_config.extra_args is None:
    #             browser_config.extra_args = []

    #         browser_config.extra_args.extend(extension_args)
    #         logger.info(f"🔌 已配置扩展参数，总数: {len(extension_args)}")

    #     # 调试模式下添加额外参数
    #     if debug_mode:
    #         debug_args = [
    #             "--no-first-run",
    #             "--no-default-browser-check",
    #         ]

    #         if not hasattr(browser_config, 'extra_args') or browser_config.extra_args is None:
    #             browser_config.extra_args = []

    #         browser_config.extra_args.extend(debug_args)
    #         logger.info(f"🐛 已添加调试参数: {debug_args}")

    #     return browser_config

    @staticmethod
    def _create_browser_config(js_enabled: bool = True, force_headless: Optional[bool] = None) -> BrowserConfig:
        """创建浏览器配置 - 支持强制无头模式"""
        # 检查是否有扩展需要加载
        extension_path = CrawlerService._get_extension_path()

        # 检查调试模式
        debug_mode = CrawlerService._is_debug_mode()

        # 🔧 智能headless模式决策
        if force_headless is not None:
            # 强制指定模式（用于生产环境）
            headless = force_headless
            user_data_dir = "./extension_browser_profile" if extension_path else None
            logger.info(f"🎯 强制{'无头' if headless else '可见'}模式")
        elif extension_path:
            # 有扩展时，默认非无头（但可以被force_headless覆盖）
            headless = False
            user_data_dir = "./extension_browser_profile"
            logger.info(f"🔌 检测到扩展，使用可见模式: {extension_path}")
        elif debug_mode:
            headless = False
            user_data_dir = "./debug_browser_profile"
            logger.info(f"🐛 调试模式启用，使用可见模式")
        else:
            headless = True
            user_data_dir = None

        browser_config = BrowserConfig(
            headless=headless,
            java_script_enabled=js_enabled,
            viewport={"width": 1280, "height": 800},
            verbose=True,
            # 使用持久化配置（如果有扩展）
            user_data_dir=user_data_dir,
            use_persistent_context=True if user_data_dir else False,
        )

        # 🔧 扩展配置
        if extension_path:
            extension_args = [
                f"--load-extension={extension_path}",
                f"--disable-extensions-except={extension_path}",
                "--disable-extensions-except-devtools",
                "--enable-extensions",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-default-apps",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--allow-running-insecure-content",
                "--disable-extensions-file-access-check",
            ]

            if not hasattr(browser_config, 'extra_args') or browser_config.extra_args is None:
                browser_config.extra_args = []

            browser_config.extra_args.extend(extension_args)
            logger.info(f"🔌 已配置扩展参数，无头模式: {headless}")

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

    # @staticmethod
    # def _create_markdown_crawler_config(request: MarkdownRequest) -> CrawlerRunConfig:
    #     """创建Markdown专用爬虫配置 - 修复版本"""
    #     # 创建Markdown生成器配置
    #     md_options = {}
    #     if request.ignore_links:
    #         md_options["ignore_links"] = True
    #     if not request.escape_html:
    #         md_options["escape_html"] = False
    #     if request.body_width:
    #         md_options["body_width"] = request.body_width

    #     # 根据格式类型选择是否使用内容过滤
    #     if request.format in [MarkdownFormat.FIT, MarkdownFormat.BOTH]:
    #         # 使用内容过滤器生成更适合AI的markdown
    #         content_filter = PruningContentFilter(
    #             threshold=0.4, threshold_type="fixed")
    #         md_generator = DefaultMarkdownGenerator(
    #             content_filter=content_filter,
    #             options=md_options
    #         )
    #     else:
    #         # 原始markdown，不使用过滤器
    #         md_generator = DefaultMarkdownGenerator(options=md_options)

    #     config = CrawlerRunConfig(
    #         cache_mode=CacheMode.BYPASS if request.bypass_cache else CacheMode.ENABLED,
    #         page_timeout=90000,  # 🔧 增加超时时间给插件更多时间工作
    #         markdown_generator=md_generator,
    #         wait_for_images=True,  # 🆕 等待图片加载完成
    #     )

    #     if request.css_selector:
    #         config.css_selector = request.css_selector

    #     return config

    @staticmethod
    def _create_markdown_crawler_config(request: MarkdownRequest) -> CrawlerRunConfig:
        """创建Markdown专用爬虫配置 - 优化版本，获得更干净的内容"""

        # 🆕 基于 crawl4ai 官方文档的优化参数
        md_options = {
            # 链接处理优化
            "ignore_links": True,  # 完全忽略所有链接，获得纯文本
            "skip_internal_links": True,  # 跳过内部锚点链接
            "escape_html": False,  # 不转义HTML，保持内容流畅

            # 格式优化
            "body_width": 0,  # 不限制行宽，保持自然换行
            "mark_code": True,  # 标记代码块
            "handle_code_in_pre": True,  # 处理 <pre> 标签中的代码

            # 🆕 高级选项
            "include_sup_sub": False,  # 简化上下标处理
            "unicode_snob": True,  # 优化Unicode处理
            "default_image_alt": "",  # 图片默认alt文本
        }

        # 根据用户请求调整特定参数
        if request.ignore_links:
            md_options["ignore_links"] = True
        if not request.escape_html:
            md_options["escape_html"] = False
        if request.body_width:
            md_options["body_width"] = request.body_width

        # 🆕 选择更强力的内容过滤器
        if request.format in [MarkdownFormat.FIT, MarkdownFormat.BOTH]:
            # 使用更激进的pruning过滤器去除噪音
            content_filter = PruningContentFilter(
                threshold=0.3,  # 更低的阈值，更激进地移除噪音
                threshold_type="dynamic",  # 动态阈值，更智能
                min_word_threshold=10,  # 至少10个词才保留
                # 🆕 新增参数
                excluded_tags=['nav', 'header', 'footer',
                               'aside', 'menu'],  # 排除导航相关标签
                exclude_external_links=True,  # 排除外部链接
                word_count_threshold=15,  # 段落至少15个词
            )

            md_generator = DefaultMarkdownGenerator(
                content_filter=content_filter,
                options=md_options
            )
        else:
            # 原始markdown，但仍然应用基础清理
            md_generator = DefaultMarkdownGenerator(options=md_options)

        config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS if request.bypass_cache else CacheMode.ENABLED,
            page_timeout=90000,
            markdown_generator=md_generator,
            wait_for_images=True,

            # 🆕 额外的页面级别优化
            excluded_tags=['nav', 'header', 'footer',
                           'aside', 'script', 'style', 'noscript'],
            remove_overlay_elements=True,  # 移除覆盖元素
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

    # async def crawl_markdown(self, request: MarkdownRequest) -> MarkdownData:
    #     """
    #     专门获取页面的Markdown内容 - 单实例修复版本
    #     """
    #     try:
    #         browser_config = self._create_browser_config(request.js_enabled)
    #         crawler_config = self._create_markdown_crawler_config(request)

    #         # 🔧 如果检测到扩展，增加额外的等待和预热
    #         extension_path = self._get_extension_path()
    #         if extension_path:
    #             logger.info(f"🔌 使用扩展模式抓取，确保单实例运行")

    #         async with AsyncWebCrawler(config=browser_config) as crawler:
    #             # 🆕 扩展预热机制 - 更加稳健
    #             if extension_path:
    #                 logger.info("🔥 扩展预热中...")
    #                 try:
    #                     # 1. 首先访问扩展管理页面确保扩展加载
    #                     warmup_config = CrawlerRunConfig(
    #                         cache_mode=CacheMode.BYPASS,
    #                         page_timeout=15000
    #                     )
    #                     await crawler.arun(url="chrome://extensions/", config=warmup_config)
    #                     await asyncio.sleep(3)

    #                     # 2. 再访问一个简单页面测试网络请求
    #                     await crawler.arun(url="https://httpbin.org/get", config=warmup_config)
    #                     await asyncio.sleep(2)

    #                     logger.info("✅ 扩展预热完成")
    #                 except Exception as e:
    #                     logger.warning(f"⚠️ 扩展预热失败，继续尝试: {str(e)}")

    #             # 执行正式抓取
    #             logger.info(f"🚀 开始抓取: {request.url}")
    #             result = await crawler.arun(url=request.url, config=crawler_config)

    #             # 🆕 智能重试机制
    #             if extension_path and result.success:
    #                 content_lower = result.markdown.lower() if result.markdown else ""
    #                 paywall_indicators = [
    #                     "subscribe", "sign in", "premium", "subscription", "paywall", "register"]
    #                 detected_indicators = [
    #                     ind for ind in paywall_indicators if ind in content_lower]

    #                 if len(detected_indicators) > 2:  # 如果检测到多个付费墙指标
    #                     logger.info(
    #                         f"🔄 检测到付费墙指标 {detected_indicators}，等待后重试...")
    #                     await asyncio.sleep(8)  # 更长的等待时间

    #                     # 重试配置：更激进的参数
    #                     retry_config = CrawlerRunConfig(
    #                         cache_mode=CacheMode.BYPASS,
    #                         page_timeout=90000,  # 1.5分钟
    #                         markdown_generator=crawler_config.markdown_generator,
    #                         wait_for_images=True,
    #                     )

    #                     retry_result = await crawler.arun(url=request.url, config=retry_config)
    #                     if retry_result.success:
    #                         retry_content_lower = retry_result.markdown.lower() if retry_result.markdown else ""
    #                         retry_indicators = [
    #                             ind for ind in paywall_indicators if ind in retry_content_lower]

    #                         # 如果重试后指标减少，使用重试结果
    #                         if len(retry_indicators) < len(detected_indicators):
    #                             result = retry_result
    #                             logger.info(
    #                                 f"🎉 重试改善了结果，指标从 {len(detected_indicators)} 减少到 {len(retry_indicators)}")
    #                         else:
    #                             logger.info("🔄 重试未能改善结果，使用原始结果")

    #             if not result.success:
    #                 raise CrawlerException(
    #                     message=getattr(
    #                         result, 'error_message', 'Markdown获取失败'),
    #                     error_type="crawl_failed"
    #                 )

    #             # 解析结果
    #             title = None
    #             if hasattr(result, 'metadata') and result.metadata:
    #                 title = result.metadata.get('title')

    #             raw_markdown = None
    #             fit_markdown = None

    #             if hasattr(result, 'markdown'):
    #                 if request.format in [MarkdownFormat.RAW, MarkdownFormat.BOTH]:
    #                     raw_markdown = self._extract_raw_markdown(
    #                         result.markdown)

    #                 if request.format in [MarkdownFormat.FIT, MarkdownFormat.BOTH]:
    #                     fit_markdown = self._extract_fit_markdown(
    #                         result.markdown, raw_markdown)

    #             # 计算字数
    #             word_count = None
    #             if raw_markdown:
    #                 word_count = len(raw_markdown.split())
    #             elif fit_markdown:
    #                 word_count = len(fit_markdown.split())

    #             # 🆕 详细的内容质量分析和日志
    #             if extension_path:
    #                 content_to_check = fit_markdown or raw_markdown or ""
    #                 paywall_indicators = [
    #                     "subscribe", "sign in", "premium", "subscription", "paywall", "register"]
    #                 detected_indicators = [
    #                     ind for ind in paywall_indicators if ind in content_to_check.lower()]

    #                 logger.info(f"📊 内容分析结果:")
    #                 logger.info(f"   - 字数: {word_count}")
    #                 logger.info(f"   - 付费墙指标: {detected_indicators}")
    #                 logger.info(
    #                     f"   - 状态码: {getattr(result, 'status_code', None)}")

    #                 if len(detected_indicators) <= 1:
    #                     logger.info("✅ 内容质量良好，疑似成功绕过付费墙")
    #                 else:
    #                     logger.warning(
    #                         f"⚠️ 检测到较多付费墙指标({len(detected_indicators)}个)，可能未完全绕过")

    #             return MarkdownData(
    #                 url=request.url,
    #                 status_code=getattr(result, 'status_code', None),
    #                 raw_markdown=raw_markdown,
    #                 fit_markdown=fit_markdown,
    #                 title=title,
    #                 word_count=word_count
    #             )

    #     except asyncio.TimeoutError:
    #         logger.error(f"Markdown爬取超时: {request.url}")
    #         raise CrawlerException(
    #             message="Markdown获取超时，请稍后重试",
    #             error_type="timeout"
    #         )
    #     except CrawlerException:
    #         raise
    #     except Exception as e:
    #         logger.error(f"Markdown爬取失败 {request.url}: {str(e)}")
    #         raise CrawlerException(
    #             message=f"Markdown获取过程中发生错误: {str(e)}",
    #             error_type="unexpected"
    #         )

    async def crawl_markdown(self, request: MarkdownRequest) -> MarkdownData:
        """
        专门获取页面的Markdown内容 - 生产环境优化版本

        优先尝试无头模式，如果效果不好则自动降级到可见模式
        """
        try:
            extension_path = self._get_extension_path()

            # 🆕 生产环境策略：优先尝试无头模式
            if extension_path:
                logger.info(f"🔌 检测到扩展，尝试无头模式运行")
                try:
                    return await self._crawl_markdown_with_mode(request, headless=True)
                except Exception as e:
                    # 如果无头模式失败，降级到可见模式
                    logger.warning(f"⚠️ 无头模式失败，降级到可见模式: {str(e)}")
                    return await self._crawl_markdown_with_mode(request, headless=False)
            else:
                # 没有扩展，直接使用无头模式
                logger.info("📄 无扩展模式，使用标准无头抓取")
                return await self._crawl_markdown_with_mode(request, headless=True)

        except Exception as e:
            logger.error(f"Markdown爬取失败 {request.url}: {str(e)}")
            raise CrawlerException(
                message=f"Markdown获取过程中发生错误: {str(e)}",
                error_type="unexpected"
            )

    async def _crawl_markdown_with_mode(self, request: MarkdownRequest, headless: bool) -> MarkdownData:
        """
        使用指定模式进行markdown抓取的内部方法
        """
        try:
            browser_config = self._create_browser_config(
                request.js_enabled, force_headless=headless)
            crawler_config = self._create_markdown_crawler_config(request)

            extension_path = self._get_extension_path()
            mode_name = "无头" if headless else "可见"
            logger.info(f"🚀 开始{mode_name}模式抓取: {request.url}")

            async with AsyncWebCrawler(config=browser_config) as crawler:
                # 🔧 简化的扩展预热（移除chrome://访问）
                if extension_path and not headless:
                    logger.info("🔥 扩展预热中...")
                    try:
                        # 只使用简单的HTTP请求预热，不访问chrome://
                        warmup_config = CrawlerRunConfig(
                            cache_mode=CacheMode.BYPASS,
                            page_timeout=10000
                        )
                        await crawler.arun(url="https://httpbin.org/get", config=warmup_config)
                        await asyncio.sleep(2)
                        logger.info("✅ 扩展预热完成")
                    except Exception as e:
                        logger.warning(f"⚠️ 扩展预热失败，继续尝试: {str(e)}")

                # 执行正式抓取
                result = await crawler.arun(url=request.url, config=crawler_config)

                # 🔧 智能重试逻辑（仅在可见模式或初次失败时）
                if extension_path and result.success:
                    content_lower = result.markdown.lower() if result.markdown else ""
                    paywall_indicators = [
                        "subscribe", "sign in", "premium", "subscription", "paywall", "register"]
                    detected_indicators = [
                        ind for ind in paywall_indicators if ind in content_lower]

                    # 只有在检测到较多付费墙指标且是可见模式时才重试
                    if len(detected_indicators) > 2 and not headless:
                        logger.info(
                            f"🔄 可见模式检测到付费墙指标 {detected_indicators}，重试中...")
                        await asyncio.sleep(5)

                        retry_config = CrawlerRunConfig(
                            cache_mode=CacheMode.BYPASS,
                            page_timeout=60000,
                            markdown_generator=crawler_config.markdown_generator,
                            wait_for_images=True,
                        )

                        retry_result = await crawler.arun(url=request.url, config=retry_config)
                        if retry_result.success:
                            retry_content_lower = retry_result.markdown.lower() if retry_result.markdown else ""
                            retry_indicators = [
                                ind for ind in paywall_indicators if ind in retry_content_lower]

                            if len(retry_indicators) < len(detected_indicators):
                                result = retry_result
                                logger.info(
                                    f"🎉 重试改善了结果，指标从 {len(detected_indicators)} 减少到 {len(retry_indicators)}")

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

                # 🔧 内容质量分析（简化版）
                if extension_path:
                    content_to_check = fit_markdown or raw_markdown or ""
                    paywall_indicators = [
                        "subscribe", "sign in", "premium", "subscription", "paywall"]
                    detected_indicators = [
                        ind for ind in paywall_indicators if ind in content_to_check.lower()]

                    logger.info(
                        f"📊 {mode_name}模式抓取结果: 字数={word_count}, 付费墙指标={len(detected_indicators)}个, 状态码={getattr(result, 'status_code', None)}")

                    if len(detected_indicators) <= 1:
                        logger.info("✅ 内容质量良好")
                    elif len(detected_indicators) <= 3:
                        logger.info("🟡 内容质量中等")
                    else:
                        logger.warning("🔴 内容质量较差，可能未完全绕过付费墙")

                        # 如果是无头模式且效果不好，抛出异常触发降级
                        if headless and len(detected_indicators) > 3:
                            raise CrawlerException(
                                message=f"无头模式效果不佳，检测到{len(detected_indicators)}个付费墙指标",
                                error_type="headless_mode_insufficient"
                            )

                return MarkdownData(
                    url=request.url,
                    status_code=getattr(result, 'status_code', None),
                    raw_markdown=raw_markdown,
                    fit_markdown=fit_markdown,
                    title=title,
                    word_count=word_count
                )

        except asyncio.TimeoutError:
            logger.error(f"{mode_name}模式Markdown爬取超时: {request.url}")
            raise CrawlerException(
                message=f"{mode_name}模式Markdown获取超时，请稍后重试",
                error_type="timeout"
            )

    # 🆕 为调试接口提供专门的方法

    async def crawl_markdown_debug(self, request: MarkdownRequest) -> MarkdownData:
        """
        调试专用的markdown抓取 - 强制可见模式，详细日志
        """
        browser_config = self._create_browser_config(
            request.js_enabled, force_headless=False)
        crawler_config = self._create_markdown_crawler_config(request)

        extension_path = self._get_extension_path()
        logger.info(f"🔍 调试模式抓取: {request.url}")

        async with AsyncWebCrawler(config=browser_config) as crawler:
            # 调试模式的详细预热
            if extension_path:
                logger.info("🔥 调试模式扩展预热...")
                try:
                    warmup_config = CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        page_timeout=10000
                    )
                    await crawler.arun(url="https://httpbin.org/get", config=warmup_config)
                    await asyncio.sleep(3)
                    logger.info("✅ 调试预热完成")
                except Exception as e:
                    logger.warning(f"⚠️ 调试预热失败: {str(e)}")

            # 执行抓取
            result = await crawler.arun(url=request.url, config=crawler_config)

            if not result.success:
                raise CrawlerException(
                    message=getattr(result, 'error_message', '调试Markdown获取失败'),
                    error_type="crawl_failed"
                )

            # 简化的结果解析
            raw_markdown = result.markdown if hasattr(
                result, 'markdown') else None
            word_count = len(raw_markdown.split()) if raw_markdown else 0

            logger.info(
                f"🔍 调试抓取完成: 字数={word_count}, 状态码={getattr(result, 'status_code', None)}")

            return MarkdownData(
                url=request.url,
                status_code=getattr(result, 'status_code', None),
                raw_markdown=raw_markdown,
                fit_markdown=raw_markdown,  # 调试模式简化处理
                title=getattr(result, 'metadata', {}).get(
                    'title') if hasattr(result, 'metadata') else None,
                word_count=word_count
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
