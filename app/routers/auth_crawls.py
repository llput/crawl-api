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


@router.post("/debug-setup", response_model=ApiResponse[AuthSetupData])
async def debug_setup_auth_profile(request: AuthSetupRequest) -> ApiResponse[AuthSetupData]:
    """
    调试版认证设置 - 用于排查问题
    """
    try:
        # 简化的调试版本
        result = await auth_crawler_service.debug_setup_auth_profile(
            site_name=request.site_name,
            login_url=request.login_url,
            test_url=request.test_url,
            setup_timeout=request.setup_timeout
        )

        data = AuthSetupData(**result)
        return ApiResponse.success_response(
            data=data,
            message="调试认证配置完成"
        )

    except CrawlerException as e:
        return ApiResponse.error_response(
            code=BusinessCode.CRAWL_FAILED,
            message=e.message
        )
    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"调试设置失败: {str(e)}"
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
            "browser_not_found": BusinessCode.CRAWL_FAILED,
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


@router.post("/manual-setup", response_model=ApiResponse[AuthSetupData])
async def manual_setup_auth_profile(request: AuthSetupRequest) -> ApiResponse[AuthSetupData]:
    """
    手动控制版认证设置 - 浏览器保持打开直到用户手动关闭

    使用流程：
    1. 调用此接口打开浏览器
    2. 在浏览器中完成登录
    3. 调用 /verify-login 验证登录状态
    4. 调用 /close-browser 关闭浏览器
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
        result = await auth_crawler_service.manual_setup_auth_profile(
            site_name=request.site_name,
            login_url=request.login_url,
            test_url=request.test_url,
            setup_timeout=request.setup_timeout
        )

        data = AuthSetupData(**result)
        return ApiResponse.success_response(
            data=data,
            message="手动认证设置完成"
        )

    except CrawlerException as e:
        error_code_map = {
            "setup_failed": BusinessCode.CRAWL_FAILED,
            "browser_not_found": BusinessCode.CRAWL_FAILED,
            "unexpected": BusinessCode.INTERNAL_ERROR
        }

        code = error_code_map.get(e.error_type, BusinessCode.CRAWL_FAILED)
        return ApiResponse.error_response(code=code, message=e.message)

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"手动认证设置时发生错误: {str(e)}"
        )


@router.post("/verify-login/{site_name}", response_model=ApiResponse[dict])
async def verify_login_status(site_name: str, test_url: str = None) -> ApiResponse[dict]:
    """
    验证登录状态 - 不关闭浏览器

    在手动登录完成后调用此接口验证登录状态
    """
    try:
        # 如果没有提供测试URL，使用默认规则
        if not test_url:
            if site_name == "medium_com":
                test_url = "https://medium.com/me/settings"
            elif site_name == "investors_com":
                test_url = "https://www.investors.com/research/stock-lists/ibd-50/"
            else:
                return ApiResponse.error_response(
                    code=BusinessCode.INVALID_PARAMS,
                    message="请提供测试URL参数"
                )

        if not is_valid_url(test_url):
            return ApiResponse.error_response(
                code=BusinessCode.INVALID_URL,
                message="无效的测试URL格式"
            )

        result = await auth_crawler_service.verify_login_status(site_name, test_url)

        return ApiResponse.success_response(
            data=result,
            message="登录状态验证完成"
        )

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"验证登录状态时发生错误: {str(e)}"
        )


@router.post("/close-browser/{site_name}", response_model=ApiResponse[dict])
async def close_browser_session(site_name: str) -> ApiResponse[dict]:
    """
    关闭浏览器会话

    在完成登录验证后调用此接口关闭浏览器
    """
    try:
        result = await auth_crawler_service.close_browser_session(site_name)

        return ApiResponse.success_response(
            data=result,
            message="浏览器关闭操作完成"
        )

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"关闭浏览器时发生错误: {str(e)}"
        )


@router.get("/browser-status/{site_name}", response_model=ApiResponse[dict])
async def get_browser_status(site_name: str) -> ApiResponse[dict]:
    """
    检查浏览器会话状态
    """
    try:
        from pathlib import Path
        browser_flag_file = Path(f"./auth_profiles/{site_name}_browser_active")

        if browser_flag_file.exists():
            return ApiResponse.success_response(
                data={
                    "browser_active": True,
                    "site_name": site_name,
                    "message": "浏览器会话正在运行"
                },
                message="浏览器会话状态正常"
            )
        else:
            return ApiResponse.success_response(
                data={
                    "browser_active": False,
                    "site_name": site_name,
                    "message": "浏览器会话未运行"
                },
                message="浏览器会话未激活"
            )

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"检查浏览器状态时发生错误: {str(e)}"
        )


@router.post("/simple-setup", response_model=ApiResponse[AuthSetupData])
async def simple_setup_auth_profile(request: AuthSetupRequest) -> ApiResponse[AuthSetupData]:
    """
    一键认证设置 - 自动检测登录状态

    使用流程：
    1. 调用此接口，浏览器会自动打开到登录页面
    2. 在浏览器中完成登录
    3. 系统会自动检测登录状态并关闭浏览器
    4. 认证配置自动保存完成

    推荐使用此接口替代复杂的手动流程
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
        result = await auth_crawler_service.simple_setup_auth_profile(
            site_name=request.site_name,
            login_url=request.login_url,
            test_url=request.test_url,
            setup_timeout=request.setup_timeout,
            check_interval=10  # 每10秒检测一次
        )

        data = AuthSetupData(**result)
        return ApiResponse.success_response(
            data=data,
            message="一键认证设置完成"
        )

    except CrawlerException as e:
        error_code_map = {
            "setup_failed": BusinessCode.CRAWL_FAILED,
            "browser_not_found": BusinessCode.CRAWL_FAILED,
            "unexpected": BusinessCode.INTERNAL_ERROR
        }

        code = error_code_map.get(e.error_type, BusinessCode.CRAWL_FAILED)
        return ApiResponse.error_response(code=code, message=e.message)

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"一键认证设置时发生错误: {str(e)}"
        )


@router.post("/quick-setup", response_model=ApiResponse[AuthSetupData])
async def quick_setup_auth_profile(
    request: AuthSetupRequest,
    wait_time: int = 120
) -> ApiResponse[AuthSetupData]:
    """
    快速认证设置 - 固定等待时间（推荐）

    使用流程：
    1. 调用此接口，浏览器自动打开到登录页面
    2. 在指定时间内（默认2分钟）完成登录
    3. 时间到后自动保存配置并关闭浏览器

    参数：
    - wait_time: 等待时间（秒），建议120-300秒
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
        result = await auth_crawler_service.quick_setup_auth_profile(
            site_name=request.site_name,
            login_url=request.login_url,
            test_url=request.test_url,
            wait_time=wait_time
        )

        data = AuthSetupData(**result)
        return ApiResponse.success_response(
            data=data,
            message="快速认证设置完成"
        )

    except CrawlerException as e:
        error_code_map = {
            "setup_failed": BusinessCode.CRAWL_FAILED,
            "browser_not_found": BusinessCode.CRAWL_FAILED,
            "unexpected": BusinessCode.INTERNAL_ERROR
        }

        code = error_code_map.get(e.error_type, BusinessCode.CRAWL_FAILED)
        return ApiResponse.error_response(code=code, message=e.message)

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"快速认证设置时发生错误: {str(e)}"
        )


@router.post("/interactive-setup", response_model=ApiResponse[AuthSetupData])
async def interactive_setup_auth_profile(request: AuthSetupRequest) -> ApiResponse[AuthSetupData]:
    """
    交互式认证设置 - 用户手动确认完成

    使用流程：
    1. 调用此接口，浏览器自动打开到登录页面
    2. 在浏览器中完成登录
    3. 登录完成后直接关闭浏览器窗口
    4. 系统检测到浏览器关闭后自动保存配置
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
        result = await auth_crawler_service.interactive_setup_auth_profile(
            site_name=request.site_name,
            login_url=request.login_url,
            test_url=request.test_url,
            setup_timeout=request.setup_timeout
        )

        data = AuthSetupData(**result)
        return ApiResponse.success_response(
            data=data,
            message="交互式认证设置完成"
        )

    except CrawlerException as e:
        error_code_map = {
            "setup_failed": BusinessCode.CRAWL_FAILED,
            "browser_not_found": BusinessCode.CRAWL_FAILED,
            "unexpected": BusinessCode.INTERNAL_ERROR
        }

        code = error_code_map.get(e.error_type, BusinessCode.CRAWL_FAILED)
        return ApiResponse.error_response(code=code, message=e.message)

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"交互式认证设置时发生错误: {str(e)}"
        )


@router.post("/simple-wait-setup", response_model=ApiResponse[AuthSetupData])
async def simple_wait_setup_auth_profile(
    request: AuthSetupRequest,
    wait_time: int = 180
) -> ApiResponse[AuthSetupData]:
    """
    简单等待版认证设置 - 最小化干预（推荐用来替代有问题的版本）

    策略：
    1. 打开浏览器到登录页面
    2. 纯等待指定时间，期间不做任何操作避免触发页面关闭
    3. 等待结束后访问测试页面保存认证状态
    4. 关闭浏览器

    参数：
    - wait_time: 等待时间（秒），建议180-300秒（3-5分钟）

    注意：
    - 等待期间请勿关闭浏览器
    - 建议设置较长的等待时间以确保有足够时间完成登录
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
        result = await auth_crawler_service.simple_wait_setup_auth_profile(
            site_name=request.site_name,
            login_url=request.login_url,
            test_url=request.test_url,
            wait_time=wait_time
        )

        data = AuthSetupData(**result)
        return ApiResponse.success_response(
            data=data,
            message="简单等待版认证设置完成"
        )

    except CrawlerException as e:
        error_code_map = {
            "setup_failed": BusinessCode.CRAWL_FAILED,
            "browser_not_found": BusinessCode.CRAWL_FAILED,
            "unexpected": BusinessCode.INTERNAL_ERROR
        }

        code = error_code_map.get(e.error_type, BusinessCode.CRAWL_FAILED)
        return ApiResponse.error_response(code=code, message=e.message)

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"简单等待版认证设置时发生错误: {str(e)}"
        )
