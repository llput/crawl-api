# app/routers/crawls.py

# 标准库导入
import os
import asyncio
from pathlib import Path

# 第三方库导入
from fastapi import APIRouter
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

# 本地应用导入
from app.models.models import CrawlRequest, MarkdownRequest, ScreenshotRequest, CrawlData, MarkdownData, ScreenshotData
from app.models.response import (
    ApiResponse, BusinessCode,
    CrawlResponse, MarkdownResponse, HealthResponse, ScreenshotResponse
)
from app.services.crawler_service import crawler_service, CrawlerException
from app.utils.helpers import is_valid_url

router = APIRouter(
    prefix="/api/v1/crawl",
    tags=["爬取"]
)


@router.post("/url", response_model=CrawlResponse)
async def crawl_single_url(request: CrawlRequest) -> CrawlResponse:
    """
    爬取单个URL并返回完整结果
    """
    if not is_valid_url(request.url):
        return ApiResponse.error_response(
            code=BusinessCode.INVALID_URL,
            message="无效的URL格式"
        )

    try:
        data = await crawler_service.crawl_url(request)
        return ApiResponse.success_response(
            data=data,
            message="爬取成功"
        )

    except CrawlerException as e:
        # 根据异常类型映射错误码
        error_code_map = {
            "timeout": BusinessCode.CRAWL_TIMEOUT,
            "crawl_failed": BusinessCode.CRAWL_FAILED,
            "unexpected": BusinessCode.INTERNAL_ERROR
        }

        code = error_code_map.get(e.error_type, BusinessCode.CRAWL_FAILED)
        return ApiResponse.error_response(code=code, message=e.message)

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"服务器内部错误: {str(e)}"
        )


@router.post("/markdown", response_model=MarkdownResponse)
async def crawl_markdown(request: MarkdownRequest) -> MarkdownResponse:
    """
    专门获取页面的Markdown内容

    支持多种格式:
    - raw: 原始markdown内容
    - fit: 经过内容过滤的markdown,更适合AI处理
    - both: 同时返回两种格式
    """
    if not is_valid_url(request.url):
        return ApiResponse.error_response(
            code=BusinessCode.INVALID_URL,
            message="无效的URL格式"
        )

    try:
        data = await crawler_service.crawl_markdown(request)
        return ApiResponse.success_response(
            data=data,
            message="Markdown获取成功"
        )

    except CrawlerException as e:
        error_code_map = {
            "timeout": BusinessCode.CRAWL_TIMEOUT,
            "crawl_failed": BusinessCode.CRAWL_FAILED,
            "unexpected": BusinessCode.INTERNAL_ERROR
        }

        code = error_code_map.get(e.error_type, BusinessCode.CRAWL_FAILED)
        return ApiResponse.error_response(code=code, message=e.message)

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"服务器内部错误: {str(e)}"
        )


@router.post("/screenshot", response_model=ScreenshotResponse)
async def take_screenshot(request: ScreenshotRequest) -> ScreenshotResponse:
    """
    截取页面截图

    支持功能:
    - 全页面截图或指定CSS选择器区域截图
    - 自定义视窗大小
    - JavaScript执行控制
    - 缓存控制
    """
    if not is_valid_url(request.url):
        return ApiResponse.error_response(
            code=BusinessCode.INVALID_URL,
            message="无效的URL格式"
        )

    try:
        data = await crawler_service.take_screenshot(request)
        return ApiResponse.success_response(
            data=data,
            message="截图成功"
        )

    except CrawlerException as e:
        # 根据异常类型映射错误码
        error_code_map = {
            "timeout": BusinessCode.CRAWL_TIMEOUT,
            "screenshot_failed": BusinessCode.CRAWL_FAILED,
            "screenshot_empty": BusinessCode.CRAWL_FAILED,
            "unexpected": BusinessCode.INTERNAL_ERROR
        }

        code = error_code_map.get(e.error_type, BusinessCode.CRAWL_FAILED)
        return ApiResponse.error_response(code=code, message=e.message)

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"服务器内部错误: {str(e)}"
        )


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    健康检查接口
    """
    return ApiResponse.success_response(
        data={"status": "healthy", "service": "crawl4ai-api"},
        message="服务正常"
    )


@router.post("/debug/extension", response_model=ApiResponse[dict])
async def debug_extension_loading(request: CrawlRequest) -> ApiResponse[dict]:
    """
    调试接口：验证扩展是否成功加载

    这个接口会保持浏览器打开更长时间，方便手动验证扩展是否工作
    """
    if not is_valid_url(request.url):
        return ApiResponse.error_response(
            code=BusinessCode.INVALID_URL,
            message="无效的URL格式"
        )

    try:
        # 检查扩展路径
        extension_path = None
        env_path = os.environ.get('CHROME_EXTENSION_PATH')
        if env_path and os.path.exists(env_path):
            extension_path = env_path
        else:
            project_extension_path = Path(
                "./chrome-extension/bypass-paywalls-chrome-clean")
            if project_extension_path.exists():
                extension_path = str(project_extension_path.resolve())

        debug_info = {
            "extension_detected": extension_path is not None,
            "extension_path": extension_path,
            "url_tested": request.url,
            "debug_mode": True,
            "browser_will_stay_open": True
        }

        if not extension_path:
            return ApiResponse.success_response(
                data=debug_info,
                message="⚠️ 未检测到扩展文件，请检查路径"
            )

        # 强制使用调试模式配置
        browser_config = BrowserConfig(
            headless=False,  # 强制可见模式
            java_script_enabled=request.js_enabled,
            viewport={"width": 1280, "height": 800},
            verbose=True,
            extra_args=[
                f"--load-extension={extension_path}",
                f"--disable-extensions-except={extension_path}",
                "--disable-extensions-except-devtools",
                "--enable-extensions",  # 确保扩展启用
            ]
        )

        config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=120000,  # 2分钟超时
            wait_for_images=request.include_images,
        )

        if request.css_selector:
            config.css_selector = request.css_selector

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=request.url, config=config)

            # 额外等待时间，让用户检查浏览器
            print("🔍 浏览器将保持打开30秒，请检查扩展是否已加载...")
            print("   在浏览器地址栏输入 chrome://extensions/ 查看扩展状态")
            await asyncio.sleep(30)  # 保持30秒

            debug_info.update({
                "crawl_success": result.success,
                "status_code": getattr(result, 'status_code', None),
                "content_length": len(result.markdown) if result.markdown else 0,
                "page_title_detected": "subscribe" not in result.markdown.lower() if result.markdown else False,
                "paywall_bypassed": "paywall" not in result.markdown.lower() if result.markdown else False
            })

            if not result.success:
                debug_info["error_message"] = getattr(
                    result, 'error_message', '未知错误')

        return ApiResponse.success_response(
            data=debug_info,
            message="🔍 扩展调试完成，请查看浏览器是否显示了扩展图标"
        )

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"调试过程中发生错误: {str(e)}"
        )
