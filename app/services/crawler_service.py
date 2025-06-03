import asyncio
import logging
from typing import Any

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter
from app.models.models import CrawlRequest, CrawlResult, MarkdownRequest, MarkdownResponse, MarkdownFormat


logger = logging.getLogger(__name__)


class CrawlerService:
    """爬虫服务类"""

    @staticmethod
    def _create_browser_config(js_enabled: bool = True) -> BrowserConfig:
        """创建浏览器配置"""
        return BrowserConfig(
            headless=True,
            java_script_enabled=js_enabled,
            viewport={"width": 1280, "height": 800},
            verbose=False
        )

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

    async def crawl_url(self, request: CrawlRequest) -> CrawlResult:
        """
        爬取单个URL

        Args:
            request: 爬取请求对象

        Returns:
            CrawlResult: 爬取结果
        """

        try:
            browser_config = self._create_browser_config(request.js_enabled)
            crawler_config = self._create_crawler_config(request)

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=request.url, config=crawler_config)

                return self._parse_crawl_result(request.url, result)

        except asyncio.TimeoutError:
            logger.error(f"爬取超时: {request.url}")
            return CrawlResult(
                url=request.url,
                success=False,
                error_message="爬取超时"
            )

        except Exception as e:
            logger.error(f"爬取失败 {request.url}: {str(e)}")
            return CrawlResult(
                url=request.url,
                success=False,
                error_message=f"爬取失败: {str(e)}"
            )

    async def crawl_markdown(self, request: MarkdownRequest) -> MarkdownResponse:
        """
        专门获取页面的Markdown内容

        Args:
            request: Markdown请求对象

        Returns:
            MarkdownResponse: Markdown响应
        """
        try:
            browser_config = self._create_browser_config(request.js_enabled)
            crawler_config = self._create_markdown_crawler_config(request)

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=request.url, config=crawler_config)

                return self._parse_markdown_result(request, result)

        except asyncio.TimeoutError:
            logger.error(f"Markdown爬取超时: {request.url}")
            return MarkdownResponse(
                url=request.url,
                success=False,
                error_message="爬取超时"
            )

        except Exception as e:
            logger.error(f"Markdown爬取失败 {request.url}: {str(e)}")
            return MarkdownResponse(
                url=request.url,
                success=False,
                error_message=f"爬取失败: {str(e)}"
            )

    @staticmethod
    def _parse_crawl_result(url: str, result: Any) -> CrawlResult:
        """解析爬取结果为统一格式"""
        return CrawlResult(
            url=url,
            success=result.success,
            status_code=getattr(result, 'status_code', None),
            markdown=result.markdown if result.success else None,
            error_message=getattr(result, 'error_message',
                                  None) if not result.success else None,
            media=result.media if result.success and hasattr(
                result, 'media') else None,
            links=result.links if result.success and hasattr(
                result, 'links') else None
        )

    @staticmethod
    def _parse_markdown_result(request: MarkdownRequest, result: Any) -> MarkdownResponse:
        """解析Markdown结果"""
        if not result.success:
            return MarkdownResponse(
                url=request.url,
                success=False,
                error_message=getattr(result, 'error_message', '未知错误')
            )

        # 获取页面标题
        title = None
        if hasattr(result, 'metadata') and result.metadata:
            title = result.metadata.get('title')

        # 根据请求格式返回相应的markdown内容
        raw_markdown = None
        fit_markdown = None

        if hasattr(result, 'markdown'):
            if request.format in [MarkdownFormat.RAW, MarkdownFormat.BOTH]:
                if hasattr(result.markdown, 'raw_markdown'):
                    raw_markdown = result.markdown.raw_markdown
                else:
                    # 向后兼容，如果没有raw_markdown属性，使用markdown本身
                    raw_markdown = result.markdown if isinstance(
                        result.markdown, str) else str(result.markdown)

            if request.format in [MarkdownFormat.FIT, MarkdownFormat.BOTH]:
                if hasattr(result.markdown, 'fit_markdown'):
                    fit_markdown = result.markdown.fit_markdown
                else:
                    # 如果没有fit_markdown，使用raw_markdown作为备选
                    fit_markdown = raw_markdown

        # 计算字数
        word_count = None
        if raw_markdown:
            word_count = len(raw_markdown.split())
        elif fit_markdown:
            word_count = len(fit_markdown.split())

        return MarkdownResponse(
            url=request.url,
            success=True,
            status_code=getattr(result, 'status_code', None),
            raw_markdown=raw_markdown,
            fit_markdown=fit_markdown,
            title=title,
            word_count=word_count
        )


# 创建服务实例
crawler_service = CrawlerService()
