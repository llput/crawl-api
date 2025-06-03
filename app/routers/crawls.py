from fastapi import APIRouter
from app.models.models import CrawlRequest, MarkdownRequest, CrawlData, MarkdownData
from app.models.response import (
    ApiResponse, BusinessCode,
    CrawlResponse, MarkdownResponse, HealthResponse
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


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    健康检查接口
    """
    return ApiResponse.success_response(
        data={"status": "healthy", "service": "crawl4ai-api"},
        message="服务正常"
    )
