# app/routers/auth_crawls.py
from fastapi import APIRouter, HTTPException
from app.models.auth_models import (
    AuthSetupRequest, AuthCrawlRequest, AuthMarkdownRequest,
    AuthSetupData, AuthProfileData, AuthProfileListData
)
from app.models.models import CrawlData, MarkdownData
from app.models.response import (
    ApiResponse, BusinessCode
)
from app.services.auth_crawler_service import auth_crawler_service, CrawlerException
from app.utils.helpers import is_valid_url

router = APIRouter(
    prefix="/api/v1/auth-crawl",
    tags=["认证爬取"]
)


@router.post("/setup", response_model=ApiResponse[AuthSetupData])
async def setup_auth_profile(request: AuthSetupRequest) -> ApiResponse[AuthSetupData]:
    """
    设置认证配置 - 打开可见浏览器供手动登录

    注意：此接口会打开可见浏览器窗口，需要手动完成登录过程
    """
    if not is_valid_url(request.login_url):
        return ApiResponse.error_response(
            code=BusinessCode.INVALID_URL,
            message="无效的登录URL格式"
        )

    if not is_valid_url(request.test_url):
        return ApiResponse.error_response(
            code=BusinessCode.INVALID_URL,
            message="无效的测试URL格式"
        )

    try:
        result = await auth_crawler_service.setup_auth_profile(
            site_name=request.site_name,
            login_url=request.login_url,
            test_url=request.test_url,
            setup_timeout=request.setup_timeout
        )

        data = AuthSetupData(**result)
        return ApiResponse.success_response(
            data=data,
            message="认证配置设置完成"
        )

    except CrawlerException as e:
        error_code_map = {
            "setup_failed": BusinessCode.CRAWL_FAILED,
            "unexpected": BusinessCode.INTERNAL_ERROR
        }

        code = error_code_map.get(e.error_type, BusinessCode.CRAWL_FAILED)
        return ApiResponse.error_response(code=code, message=e.message)

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"设置认证配置时发生错误: {str(e)}"
        )


@router.post("/crawl", response_model=ApiResponse[CrawlData])
async def crawl_with_auth(request: AuthCrawlRequest) -> ApiResponse[CrawlData]:
    """
    使用认证配置爬取URL

    需要先通过 /setup 接口设置对应站点的认证配置
    """
    if not is_valid_url(request.url):
        return ApiResponse.error_response(
            code=BusinessCode.INVALID_URL,
            message="无效的URL格式"
        )

    try:
        # 将 AuthCrawlRequest 转换为 CrawlRequest
        from app.models.models import CrawlRequest
        crawl_request = CrawlRequest(
            url=request.url,
            js_enabled=request.js_enabled,
            bypass_cache=request.bypass_cache,
            include_images=request.include_images,
            css_selector=request.css_selector
        )

        data = await auth_crawler_service.crawl_with_auth(
            site_name=request.site_name,
            request=crawl_request
        )

        return ApiResponse.success_response(
            data=data,
            message="认证爬取成功"
        )

    except CrawlerException as e:
        error_code_map = {
            "auth_required": BusinessCode.INVALID_PARAMS,
            "auth_expired": BusinessCode.CRAWL_FAILED,
            "timeout": BusinessCode.CRAWL_TIMEOUT,
            "crawl_failed": BusinessCode.CRAWL_FAILED,
            "unexpected": BusinessCode.INTERNAL_ERROR
        }

        code = error_code_map.get(e.error_type, BusinessCode.CRAWL_FAILED)
        return ApiResponse.error_response(code=code, message=e.message)

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"认证爬取时发生错误: {str(e)}"
        )


@router.post("/markdown", response_model=ApiResponse[MarkdownData])
async def crawl_markdown_with_auth(request: AuthMarkdownRequest) -> ApiResponse[MarkdownData]:
    """
    使用认证配置获取页面的Markdown内容

    需要先通过 /setup 接口设置对应站点的认证配置
    """
    if not is_valid_url(request.url):
        return ApiResponse.error_response(
            code=BusinessCode.INVALID_URL,
            message="无效的URL格式"
        )

    try:
        # 将 AuthMarkdownRequest 转换为 MarkdownRequest
        from app.models.models import MarkdownRequest, MarkdownFormat
        markdown_request = MarkdownRequest(
            url=request.url,
            format=MarkdownFormat.RAW,  # 默认使用原始格式
            js_enabled=request.js_enabled,
            bypass_cache=request.bypass_cache,
            css_selector=request.css_selector
        )

        data = await auth_crawler_service.crawl_markdown_with_auth(
            site_name=request.site_name,
            request=markdown_request
        )

        return ApiResponse.success_response(
            data=data,
            message="认证Markdown获取成功"
        )

    except CrawlerException as e:
        error_code_map = {
            "auth_required": BusinessCode.INVALID_PARAMS,
            "auth_expired": BusinessCode.CRAWL_FAILED,
            "timeout": BusinessCode.CRAWL_TIMEOUT,
            "crawl_failed": BusinessCode.CRAWL_FAILED,
            "unexpected": BusinessCode.INTERNAL_ERROR
        }

        code = error_code_map.get(e.error_type, BusinessCode.CRAWL_FAILED)
        return ApiResponse.error_response(code=code, message=e.message)

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"认证Markdown获取时发生错误: {str(e)}"
        )


@router.get("/profiles", response_model=ApiResponse[AuthProfileListData])
async def list_auth_profiles() -> ApiResponse[AuthProfileListData]:
    """
    列出所有已设置的认证配置
    """
    try:
        profiles_dict = auth_crawler_service.list_auth_profiles()

        # 转换为 AuthProfileData 对象
        profiles = {}
        for site_name, info in profiles_dict.items():
            profiles[site_name] = AuthProfileData(**info)

        data = AuthProfileListData(
            profiles=profiles,
            total_count=len(profiles)
        )

        return ApiResponse.success_response(
            data=data,
            message=f"找到 {len(profiles)} 个认证配置"
        )

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"获取认证配置列表时发生错误: {str(e)}"
        )


@router.delete("/profiles/{site_name}", response_model=ApiResponse[dict])
async def delete_auth_profile(site_name: str) -> ApiResponse[dict]:
    """
    删除指定的认证配置
    """
    try:
        success = auth_crawler_service.delete_auth_profile(site_name)

        if success:
            return ApiResponse.success_response(
                data={"site_name": site_name, "deleted": True},
                message=f"认证配置 '{site_name}' 删除成功"
            )
        else:
            return ApiResponse.error_response(
                code=BusinessCode.INVALID_PARAMS,
                message=f"认证配置 '{site_name}' 不存在"
            )

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"删除认证配置时发生错误: {str(e)}"
        )


@router.get("/health", response_model=ApiResponse[dict])
async def auth_health_check() -> ApiResponse[dict]:
    """
    认证爬取服务健康检查
    """
    try:
        profiles = auth_crawler_service.list_auth_profiles()

        return ApiResponse.success_response(
            data={
                "status": "healthy",
                "service": "auth-crawl4ai",
                "auth_profiles_count": len(profiles)
            },
            message="认证爬取服务正常"
        )

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"健康检查失败: {str(e)}"
        )
