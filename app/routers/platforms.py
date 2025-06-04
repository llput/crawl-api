# app/routers/platforms.py
from fastapi import APIRouter, HTTPException, Query, Path
from typing import Optional, List

from app.models.response import ApiResponse, BusinessCode
from app.models.platform_models import (
    PlatformInfo, PlatformLinksData, PlatformContentData,
    XiaohongshuLinksData, XiaohongshuNoteData,
    PlatformExtractRequest, PlatformCrawlRequest
)
from app.platforms.xiaohongshu import XiaohongshuPlatform
from app.services.auth_crawler_service import auth_crawler_service, CrawlerException
from app.utils.helpers import is_valid_url

# 创建平台路由
router = APIRouter(
    prefix="/api/v1/platforms",
    tags=["平台模块"]
)

# 初始化支持的平台
SUPPORTED_PLATFORMS = {
    "xiaohongshu": XiaohongshuPlatform(auth_crawler_service)
}


def get_platform(platform_name: str):
    """获取平台实例"""
    if platform_name not in SUPPORTED_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的平台: {platform_name}。支持的平台: {list(SUPPORTED_PLATFORMS.keys())}"
        )
    return SUPPORTED_PLATFORMS[platform_name]


@router.get("/", response_model=ApiResponse[List[PlatformInfo]])
async def list_platforms() -> ApiResponse[List[PlatformInfo]]:
    """
    获取所有支持的平台列表
    """
    try:
        platforms_info = []

        for platform_name, platform_instance in SUPPORTED_PLATFORMS.items():
            config = platform_instance.config
            available = platform_instance.is_available()

            platforms_info.append(PlatformInfo(
                name=config.name,
                display_name=config.display_name,
                version=config.version,
                enabled=config.enabled,
                available=available
            ))

        return ApiResponse.success_response(
            data=platforms_info,
            message=f"找到 {len(platforms_info)} 个支持的平台"
        )

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"获取平台列表失败: {str(e)}"
        )


@router.post("/{platform_name}/extract", response_model=ApiResponse[PlatformLinksData])
async def extract_platform_content_links(
    platform_name: str = Path(..., description="平台名称"),
    source_url: Optional[str] = Query(None, description="源页面URL"),
    max_links: int = Query(20, description="最大提取链接数")
) -> ApiResponse[PlatformLinksData]:
    """
    从指定平台提取内容链接

    支持的平台:
    - xiaohongshu: 小红书笔记链接
    """
    try:
        platform = get_platform(platform_name)

        if not platform.is_available():
            return ApiResponse.error_response(
                code=BusinessCode.INVALID_PARAMS,
                message=f"{platform.config.display_name} 认证配置不存在，请先设置认证"
            )

        if source_url and not is_valid_url(source_url):
            return ApiResponse.error_response(
                code=BusinessCode.INVALID_URL,
                message="无效的源页面URL格式"
            )

        data = await platform.extract_content_links(
            source_url=source_url,
            max_links=max_links
        )

        # 根据平台类型返回特定格式
        if platform_name == "xiaohongshu":
            response_data = XiaohongshuLinksData(**data)
        else:
            response_data = PlatformLinksData(**data)

        return ApiResponse.success_response(
            data=response_data,
            message=f"成功从 {platform.config.display_name} 提取 {data['total_count']} 个内容链接"
        )

    except CrawlerException as e:
        return ApiResponse.error_response(
            code=BusinessCode.CRAWL_FAILED,
            message=e.message
        )
    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"提取内容链接失败: {str(e)}"
        )


@router.post("/{platform_name}/content/{content_id}", response_model=ApiResponse[PlatformContentData])
async def crawl_platform_content(
    platform_name: str = Path(..., description="平台名称"),
    content_id: str = Path(..., description="内容ID"),
    source_url: Optional[str] = Query(None, description="源页面URL")
) -> ApiResponse[PlatformContentData]:
    """
    爬取指定平台的特定内容

    支持的平台和内容类型:
    - xiaohongshu: 笔记ID（如：683e5ac20000000023015825）
    """
    try:
        platform = get_platform(platform_name)

        if not platform.is_available():
            return ApiResponse.error_response(
                code=BusinessCode.INVALID_PARAMS,
                message=f"{platform.config.display_name} 认证配置不存在，请先设置认证"
            )

        if source_url and not is_valid_url(source_url):
            return ApiResponse.error_response(
                code=BusinessCode.INVALID_URL,
                message="无效的源页面URL格式"
            )

        data = await platform.crawl_content_by_id(
            content_id=content_id,
            source_url=source_url
        )

        # 根据平台类型返回特定格式
        if platform_name == "xiaohongshu":
            response_data = XiaohongshuNoteData(**data)
        else:
            response_data = PlatformContentData(**data)

        return ApiResponse.success_response(
            data=response_data,
            message=f"{platform.config.display_name} 内容 {content_id} 爬取成功"
        )

    except CrawlerException as e:
        return ApiResponse.error_response(
            code=BusinessCode.CRAWL_FAILED,
            message=e.message
        )
    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"爬取内容失败: {str(e)}"
        )

# 小红书专用便捷接口


@router.get("/xiaohongshu/health", response_model=ApiResponse[dict])
async def xiaohongshu_health_check() -> ApiResponse[dict]:
    """小红书平台健康检查"""
    try:
        platform = get_platform("xiaohongshu")
        config = platform.config

        return ApiResponse.success_response(
            data={
                "platform": config.name,
                "display_name": config.display_name,
                "version": config.version,
                "enabled": config.enabled,
                "available": platform.is_available(),
                "site_name": config.site_name,
                "default_source_url": config.default_source_url,
                "status": "healthy"
            },
            message="小红书平台运行正常"
        )

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"小红书平台健康检查失败: {str(e)}"
        )


@router.post("/xiaohongshu/notes", response_model=ApiResponse[XiaohongshuLinksData])
async def extract_xiaohongshu_notes(
    source_url: Optional[str] = Query(None, description="源页面URL，默认为探索页"),
    max_notes: int = Query(20, description="最大笔记数量")
) -> ApiResponse[XiaohongshuLinksData]:
    """
    提取小红书笔记链接的便捷接口
    """
    return await extract_platform_content_links("xiaohongshu", source_url, max_notes)


@router.post("/xiaohongshu/notes/{note_id}", response_model=ApiResponse[XiaohongshuNoteData])
async def crawl_xiaohongshu_note(
    note_id: str = Path(..., description="小红书笔记ID"),
    source_url: Optional[str] = Query(None, description="获取token的源页面URL")
) -> ApiResponse[XiaohongshuNoteData]:
    """
    爬取小红书笔记内容的便捷接口
    """
    return await crawl_platform_content("xiaohongshu", note_id, source_url)
