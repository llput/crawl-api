
from fastapi import APIRouter, HTTPException
from app.models.models import CrawlRequest, CrawlResult, MarkdownRequest, MarkdownResponse
from app.services.crawler_service import crawler_service
from app.utils.helpers import is_valid_url

router = APIRouter(
    prefix="/api/v1/crawl",
    tags=["爬取"]
)


@router.post("/url", response_model=CrawlResult)
async def crawl_single_url(request: CrawlRequest):
    """
    爬取单个URL并返回完整结果
    """
    if not is_valid_url(request.url):
        raise HTTPException(status_code=400, detail="无效的URL")

    result = await crawler_service.crawl_url(request)
    return result


@router.post("/markdown", response_model=MarkdownResponse)
async def crawl_markdown(request: MarkdownRequest):
    """
    专门获取页面的Markdown内容

    支持多种格式：
    - raw: 原始markdown内容
    - fit: 经过内容过滤的markdown，更适合AI处理
    - both: 同时返回两种格式
    """
    if not is_valid_url(request.url):
        raise HTTPException(status_code=400, detail="无效的URL")

    result = await crawler_service.crawl_markdown(request)
    return result


@router.get("/health")
async def health_check():
    """
    健康检查接口
    """
    return {"status": "healthy", "service": "crawl4ai-api"}
