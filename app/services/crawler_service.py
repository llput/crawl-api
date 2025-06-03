import asyncio
import logging
from typing import Any

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from app.models.models import CrawlRequest, CrawlResult

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


# 创建服务实例
crawler_service = CrawlerService()
