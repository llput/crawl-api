# app/routers/crawls.py

# 标准库导入
import os
import asyncio
from pathlib import Path

# 第三方库导入
from fastapi import APIRouter, Query
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

# 本地应用导入
from app.models.models import CrawlRequest, MarkdownRequest, ScreenshotRequest, CrawlData, MarkdownData, ScreenshotData, MarkdownFormat
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


# 辅助函数


async def _crawl_markdown_with_clean_config(request: MarkdownRequest) -> MarkdownData:
    """使用超级清理配置的内部函数"""
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

    # 最激进的清理选项
    super_clean_options = {
        "ignore_links": True,
        "skip_internal_links": True,
        "escape_html": False,
        "body_width": 0,
        "unicode_snob": True,
        "default_image_alt": "[图片]",
        "mark_code": True,
        "handle_code_in_pre": True,
        "include_sup_sub": False,
    }

    # 更激进的内容过滤器
    content_filter = PruningContentFilter(
        threshold=0.2,  # 非常低的阈值，激进过滤
        threshold_type="dynamic",
        min_word_threshold=15,  # 段落至少15个词
    )

    md_generator = DefaultMarkdownGenerator(
        content_filter=content_filter,
        options=super_clean_options
    )

    browser_config = crawler_service._create_browser_config(request.js_enabled)
    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS if request.bypass_cache else CacheMode.ENABLED,
        page_timeout=90000,
        markdown_generator=md_generator,
        wait_for_images=True,
    )

    if request.css_selector:
        config.css_selector = request.css_selector

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=request.url, config=config)

        if not result.success:
            raise CrawlerException(
                message=getattr(result, 'error_message', '超级清理模式获取失败'),
                error_type="crawl_failed"
            )

        # 解析结果
        title = None
        if hasattr(result, 'metadata') and result.metadata:
            title = result.metadata.get('title')

        # 获取清理后的内容
        clean_markdown = None
        if hasattr(result, 'markdown'):
            if hasattr(result.markdown, 'fit_markdown'):
                clean_markdown = result.markdown.fit_markdown
            elif isinstance(result.markdown, str):
                clean_markdown = result.markdown
            else:
                clean_markdown = str(result.markdown)

        # 后处理清理
        if clean_markdown:
            clean_markdown = _post_process_markdown(clean_markdown)

        word_count = len(clean_markdown.split()) if clean_markdown else 0

        return MarkdownData(
            url=request.url,
            status_code=getattr(result, 'status_code', None),
            raw_markdown=None,  # 超级清理模式只返回清理后的内容
            fit_markdown=clean_markdown,
            title=title,
            word_count=word_count
        )


async def _crawl_markdown_with_query(request: MarkdownRequest, query: str) -> MarkdownData:
    """使用BM25查询过滤的内部函数"""
    from crawl4ai.content_filter_strategy import BM25ContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

    # BM25查询配置
    bm25_filter = BM25ContentFilter(
        user_query=query,
        bm25_threshold=0.8,  # 较低阈值，保留更多相关内容
    )

    query_options = {
        "ignore_links": True,
        "escape_html": False,
        "body_width": 0,
        "unicode_snob": True,
        "mark_code": True,
        "default_image_alt": "[图片]",
    }

    md_generator = DefaultMarkdownGenerator(
        content_filter=bm25_filter,
        options=query_options
    )

    browser_config = crawler_service._create_browser_config(request.js_enabled)
    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS if request.bypass_cache else CacheMode.ENABLED,
        page_timeout=90000,
        markdown_generator=md_generator,
        wait_for_images=True,
    )

    if request.css_selector:
        config.css_selector = request.css_selector

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=request.url, config=config)

        if not result.success:
            raise CrawlerException(
                message=getattr(result, 'error_message', 'BM25查询模式获取失败'),
                error_type="crawl_failed"
            )

        # 解析结果
        title = None
        if hasattr(result, 'metadata') and result.metadata:
            title = result.metadata.get('title')

        # 获取查询相关的内容
        query_markdown = None
        if hasattr(result, 'markdown'):
            if hasattr(result.markdown, 'fit_markdown'):
                query_markdown = result.markdown.fit_markdown
            elif isinstance(result.markdown, str):
                query_markdown = result.markdown
            else:
                query_markdown = str(result.markdown)

        # 轻度后处理（保留更多内容，因为是查询相关的）
        if query_markdown:
            query_markdown = _light_post_process_markdown(query_markdown)

        word_count = len(query_markdown.split()) if query_markdown else 0

        return MarkdownData(
            url=request.url,
            status_code=getattr(result, 'status_code', None),
            raw_markdown=None,
            fit_markdown=query_markdown,
            title=title,
            word_count=word_count
        )


def _post_process_markdown(markdown: str) -> str:
    """
    激进的后处理清理 Markdown 内容
    """
    import re

    if not markdown:
        return ""

    # 移除导航和分享相关内容
    navigation_patterns = [
        r'\[Skip to .*?\]\(.*?\)',
        r'\[Accessibility help\]\(.*?\)',
        r'current progress \d+%',
        r'\[.*? on (x|facebook|linkedin|whatsapp).*?\]\(.*?\)',
        r'Jump to comments section',
        r'Print this page',
        r'Reuse this content.*?\n',
        r'Close side navigation menu',
        r'Subscribe for full access',
        r'Follow the topics in this article',
        r'Promoted Content',
        r'Comments\n',
        r'\*\[.*?\]: .*\n',  # 移除引用定义
    ]

    for pattern in navigation_patterns:
        markdown = re.sub(pattern, '', markdown, flags=re.IGNORECASE)

    # 移除重复的社交分享链接块
    markdown = re.sub(
        r'(\* \[.*? on (x|facebook|linkedin|whatsapp).*?\]\(.*?\)\n){2,}', '', markdown, flags=re.IGNORECASE)

    # 移除空的列表项
    markdown = re.sub(r'^\s*\*\s*$', '', markdown, flags=re.MULTILINE)

    # 清理多余的空白
    markdown = re.sub(r'\n\s*\n\s*\n+', '\n\n', markdown)
    markdown = re.sub(r'[ \t]+', ' ', markdown)

    # 移除开头和结尾的空白
    markdown = markdown.strip()

    return markdown


def _light_post_process_markdown(markdown: str) -> str:
    """
    轻度后处理 - 保留更多内容，只移除明显的噪音
    """
    import re

    if not markdown:
        return ""

    # 只移除最明显的导航元素
    light_patterns = [
        r'\[Skip to .*?\]\(.*?\)',
        r'\[Accessibility help\]\(.*?\)',
        r'current progress \d+%',
    ]

    for pattern in light_patterns:
        markdown = re.sub(pattern, '', markdown, flags=re.IGNORECASE)

    # 清理多余的空白
    markdown = re.sub(r'\n\s*\n\s*\n+', '\n\n', markdown)
    markdown = markdown.strip()

    return markdown


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


# 在 app/routers/crawls.py 中添加自动配置插件的功能

@router.post("/auto-configure-extension", response_model=ApiResponse[dict])
async def auto_configure_extension() -> ApiResponse[dict]:
    """
    自动配置 Bypass Paywalls Clean 插件
    启用 custom sites 和其他必要设置，一次性配置，永久生效
    """
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

        if not extension_path:
            return ApiResponse.error_response(
                code=BusinessCode.INTERNAL_ERROR,
                message="未检测到扩展文件，请检查路径"
            )

        # 使用与正常爬取相同的持久化配置
        browser_config = BrowserConfig(
            headless=False,  # 需要可见模式来配置
            java_script_enabled=True,
            viewport={"width": 1280, "height": 800},
            verbose=True,
            user_data_dir="./extension_browser_profile",  # 与正常爬取相同的目录
            use_persistent_context=True,
            extra_args=[
                f"--load-extension={extension_path}",
                f"--disable-extensions-except={extension_path}",
                "--disable-extensions-except-devtools",
                "--enable-extensions",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-default-apps",
            ]
        )

        config_result = {
            "extension_path": extension_path,
            "user_data_dir": "./extension_browser_profile",
            "steps_completed": [],
            "configuration_successful": False
        }

        async with AsyncWebCrawler(config=browser_config) as crawler:
            print("🚀 开始自动配置插件...")

            # 第一步：访问插件配置页面
            print("📋 正在打开插件配置页面...")
            extension_id = "lkbebcjgcmobigpeffafkodonchffocl"  # Bypass Paywalls Clean 的扩展ID
            config_url = f"chrome-extension://{extension_id}/options/options.html"

            config_page_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=15000,
                js_code="""
                // 自动配置插件的JavaScript代码
                async function autoConfigureExtension() {
                    console.log('🔧 开始自动配置插件...');

                    // 等待页面完全加载
                    await new Promise(resolve => setTimeout(resolve, 2000));

                    let configuredOptions = [];

                    // 1. 启用 custom sites
                    const customSitesEnableBtn = document.querySelector('button[onclick="enable_custom_sites()"]');
                    if (customSitesEnableBtn && customSitesEnableBtn.textContent.includes('Enable')) {
                        customSitesEnableBtn.click();
                        configuredOptions.push('custom_sites_enabled');
                        console.log('✅ Custom sites 已启用');
                        await new Promise(resolve => setTimeout(resolve, 1000));
                    }

                    // 2. 启用 setCookie opt-in (如果需要)
                    const setCookieEnableBtn = document.querySelector('button[onclick="enable_setCookie()"]');
                    if (setCookieEnableBtn && setCookieEnableBtn.textContent.includes('Enable')) {
                        setCookieEnableBtn.click();
                        configuredOptions.push('setCookie_enabled');
                        console.log('✅ setCookie 已启用');
                        await new Promise(resolve => setTimeout(resolve, 1000));
                    }

                    // 3. 检查配置状态
                    const customSitesStatus = document.querySelector('body').textContent.includes('custom sites enabled: YES');
                    const setCookieStatus = document.querySelector('body').textContent.includes('setCookie opt-in enabled: YES');

                    console.log('📊 配置状态检查:');
                    console.log('   - Custom sites:', customSitesStatus ? 'YES' : 'NO');
                    console.log('   - setCookie:', setCookieStatus ? 'YES' : 'NO');

                    // 将结果存储到页面，供爬虫读取
                    const resultDiv = document.createElement('div');
                    resultDiv.id = 'auto-config-result';
                    resultDiv.style.display = 'none';
                    resultDiv.textContent = JSON.stringify({
                        configuredOptions: configuredOptions,
                        customSitesEnabled: customSitesStatus,
                        setCookieEnabled: setCookieStatus,
                        success: configuredOptions.length > 0 || (customSitesStatus && setCookieStatus)
                    });
                    document.body.appendChild(resultDiv);

                    console.log('🎉 自动配置完成!');
                    return configuredOptions;
                }

                // 执行配置
                autoConfigureExtension();
                """
            )

            result = await crawler.arun(url=config_url, config=config_page_config)

            if result.success:
                config_result["steps_completed"].append("opened_config_page")

                # 从页面中提取配置结果
                try:
                    import re
                    import json

                    # 查找结果数据
                    result_match = re.search(
                        r'<div id="auto-config-result"[^>]*>([^<]+)</div>', result.html)
                    if result_match:
                        result_data = json.loads(result_match.group(1))
                        config_result.update({
                            "configured_options": result_data.get("configuredOptions", []),
                            "custom_sites_enabled": result_data.get("customSitesEnabled", False),
                            "setCookie_enabled": result_data.get("setCookieEnabled", False),
                            "configuration_successful": result_data.get("success", False)
                        })
                        config_result["steps_completed"].append(
                            "auto_configuration_executed")

                    # 手动检查页面内容
                    page_content = result.html.lower()
                    if "custom sites enabled: yes" in page_content:
                        config_result["custom_sites_enabled"] = True
                    if "setcookie opt-in enabled: yes" in page_content:
                        config_result["setCookie_enabled"] = True

                except Exception as e:
                    print(f"⚠️ 解析配置结果时出错: {str(e)}")
                    config_result["parse_error"] = str(e)

            # 第二步：测试配置是否生效
            print("🧪 测试插件配置...")
            test_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=10000
            )

            test_result = await crawler.arun(url="https://httpbin.org/get", config=test_config)
            if test_result.success:
                config_result["steps_completed"].append(
                    "test_navigation_successful")

            # 保持浏览器打开让用户确认
            print("🔍 保持浏览器打开15秒供您确认配置...")
            print("   请在浏览器中查看插件配置页面确认设置")
            await asyncio.sleep(15)

        # 总结配置结果
        success_indicators = [
            config_result.get("custom_sites_enabled", False),
            config_result.get("setCookie_enabled", False),
            len(config_result.get("configured_options", [])) > 0
        ]

        overall_success = any(success_indicators)
        config_result["overall_success"] = overall_success

        if overall_success:
            message = "🎉 插件自动配置完成！设置已永久保存，后续爬取无需再配置"
        else:
            message = "⚠️ 自动配置可能未完全成功，建议手动检查插件设置"

        return ApiResponse.success_response(
            data=config_result,
            message=message
        )

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"自动配置插件失败: {str(e)}"
        )


@router.post("/debug/extension", response_model=ApiResponse[dict])
async def debug_extension_loading(request: CrawlRequest) -> ApiResponse[dict]:
    """
    调试接口：专用于测试扩展功能 - 强制可见模式
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
            "forced_visible": True,
        }

        if not extension_path:
            return ApiResponse.success_response(
                data=debug_info,
                message="⚠️ 未检测到扩展文件，请检查路径"
            )

        # 🔧 调试专用配置：强制可见模式
        browser_config = BrowserConfig(
            headless=False,  # 调试强制可见
            java_script_enabled=request.js_enabled,
            viewport={"width": 1280, "height": 800},
            verbose=True,
            user_data_dir="./extension_browser_profile",
            use_persistent_context=True,
            extra_args=[
                f"--load-extension={extension_path}",
                f"--disable-extensions-except={extension_path}",
                "--disable-extensions-except-devtools",
                "--enable-extensions",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-default-apps",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
            ]
        )

        print("🚀 启动调试模式（强制可见）...")

        async with AsyncWebCrawler(config=browser_config) as crawler:
            try:
                print("=" * 60)
                print("🔍 调试模式说明：")
                print("   - 浏览器将保持可见状态")
                print("   - 可以手动检查插件是否正常工作")
                print("   - 10秒后将访问目标URL")
                print("=" * 60)

                await asyncio.sleep(10)

                print("🌐 开始访问目标URL...")

                config = CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    page_timeout=60000,
                    wait_for_images=request.include_images,
                )

                if request.css_selector:
                    config.css_selector = request.css_selector

                # 🔧 简化的预热：只用HTTP请求
                print("🔥 扩展预热中...")
                try:
                    warmup_config = CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        page_timeout=10000
                    )
                    await crawler.arun(url="https://httpbin.org/get", config=warmup_config)
                    await asyncio.sleep(2)
                    print("✅ 扩展预热完成")
                except Exception as e:
                    print(f"⚠️ 预热失败，继续测试: {str(e)}")

                # 执行目标URL抓取
                result = await crawler.arun(url=request.url, config=config)

                print(
                    f"📄 页面加载完成，状态码: {getattr(result, 'status_code', 'Unknown')}")

                # 分析结果
                debug_info.update({
                    "crawl_success": result.success,
                    "status_code": getattr(result, 'status_code', None),
                    "content_length": len(result.markdown) if result.markdown else 0,
                    "content_preview": result.markdown[:300] if result.markdown else "No content",
                })

                # 付费墙检测
                if result.markdown:
                    content_lower = result.markdown.lower()
                    paywall_indicators = [
                        "subscribe", "sign in", "premium", "subscription", "paywall"]
                    detected_indicators = [
                        ind for ind in paywall_indicators if ind in content_lower]

                    debug_info["paywall_indicators_found"] = detected_indicators
                    debug_info["paywall_indicators_count"] = len(
                        detected_indicators)
                    debug_info["likely_success"] = len(
                        detected_indicators) <= 2

                    if len(detected_indicators) <= 1:
                        print("🎉 优秀！几乎没有付费墙指标")
                        debug_info["quality_assessment"] = "excellent"
                    elif len(detected_indicators) <= 2:
                        print("🟢 良好！少量付费墙指标")
                        debug_info["quality_assessment"] = "good"
                    elif len(detected_indicators) <= 3:
                        print("🟡 中等，存在一些付费墙指标")
                        debug_info["quality_assessment"] = "medium"
                    else:
                        print(f"🔴 较差，检测到较多付费墙指标: {detected_indicators}")
                        debug_info["quality_assessment"] = "poor"

                if not result.success:
                    debug_info["error_message"] = getattr(
                        result, 'error_message', '未知错误')

                print("🔍 保持浏览器打开20秒供您检查结果...")
                print("   您可以在浏览器中手动查看页面内容")
                await asyncio.sleep(20)

            except Exception as e:
                print(f"❌ 执行过程中出错: {str(e)}")
                debug_info["execution_error"] = str(e)
                await asyncio.sleep(10)

        print("🔚 调试会话结束")

        # 生成建议消息
        quality = debug_info.get("quality_assessment", "unknown")
        if quality == "excellent":
            message = "🎉 调试成功！扩展工作完美，可以直接使用生产接口"
        elif quality == "good":
            message = "✅ 调试成功！扩展工作良好，建议使用生产接口"
        elif quality == "medium":
            message = "🟡 调试显示中等效果，可以尝试生产接口但可能需要优化"
        else:
            message = "🔍 调试完成，请查看详细结果并考虑配置优化"

        return ApiResponse.success_response(
            data=debug_info,
            message=message
        )

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"调试过程中发生错误: {str(e)}"
        )


@router.post("/test/headless-mode", response_model=ApiResponse[dict])
async def test_headless_mode(request: CrawlRequest) -> ApiResponse[dict]:
    """
    测试无头模式效果 - 对比有头和无头模式的差异
    """
    if not is_valid_url(request.url):
        return ApiResponse.error_response(
            code=BusinessCode.INVALID_URL,
            message="无效的URL格式"
        )

    try:
        from app.models.models import MarkdownRequest, MarkdownFormat

        # 转换为MarkdownRequest
        markdown_request = MarkdownRequest(
            url=request.url,
            format=MarkdownFormat.FIT,
            js_enabled=request.js_enabled,
            bypass_cache=request.bypass_cache,
            css_selector=request.css_selector
        )

        test_results = {
            "url": request.url,
            "tests_performed": [],
            "comparison": {}
        }

        try:
            # 测试1：无头模式
            print("🤖 测试无头模式...")
            headless_result = await crawler_service._crawl_markdown_with_mode(markdown_request, headless=True)

            headless_analysis = {
                "success": True,
                "word_count": headless_result.word_count,
                "status_code": headless_result.status_code,
                "content_preview": (headless_result.fit_markdown or headless_result.raw_markdown or "")[:200]
            }

            # 分析付费墙指标
            content = headless_result.fit_markdown or headless_result.raw_markdown or ""
            paywall_indicators = ["subscribe", "sign in",
                                  "premium", "subscription", "paywall"]
            headless_indicators = [
                ind for ind in paywall_indicators if ind in content.lower()]
            headless_analysis["paywall_indicators"] = len(headless_indicators)

            test_results["headless_mode"] = headless_analysis
            test_results["tests_performed"].append("headless")

        except Exception as e:
            test_results["headless_mode"] = {
                "success": False,
                "error": str(e)
            }

        try:
            # 测试2：可见模式
            print("👁️ 测试可见模式...")
            visible_result = await crawler_service._crawl_markdown_with_mode(markdown_request, headless=False)

            visible_analysis = {
                "success": True,
                "word_count": visible_result.word_count,
                "status_code": visible_result.status_code,
                "content_preview": (visible_result.fit_markdown or visible_result.raw_markdown or "")[:200]
            }

            # 分析付费墙指标
            content = visible_result.fit_markdown or visible_result.raw_markdown or ""
            paywall_indicators = ["subscribe", "sign in",
                                  "premium", "subscription", "paywall"]
            visible_indicators = [
                ind for ind in paywall_indicators if ind in content.lower()]
            visible_analysis["paywall_indicators"] = len(visible_indicators)

            test_results["visible_mode"] = visible_analysis
            test_results["tests_performed"].append("visible")

        except Exception as e:
            test_results["visible_mode"] = {
                "success": False,
                "error": str(e)
            }

        # 对比分析
        if "headless" in test_results["tests_performed"] and "visible" in test_results["tests_performed"]:
            headless_data = test_results["headless_mode"]
            visible_data = test_results["visible_mode"]

            if headless_data["success"] and visible_data["success"]:
                comparison = {
                    "word_count_diff": visible_data["word_count"] - headless_data["word_count"],
                    "paywall_indicators_diff": visible_data["paywall_indicators"] - headless_data["paywall_indicators"],
                    "headless_quality": "good" if headless_data["paywall_indicators"] <= 2 else "poor",
                    "visible_quality": "good" if visible_data["paywall_indicators"] <= 2 else "poor",
                    "recommendation": ""
                }

                if headless_data["paywall_indicators"] <= 2:
                    comparison["recommendation"] = "无头模式效果良好，推荐生产环境使用"
                elif visible_data["paywall_indicators"] <= 2:
                    comparison["recommendation"] = "建议使用可见模式，或优化无头模式配置"
                else:
                    comparison["recommendation"] = "两种模式效果都不理想，建议检查扩展配置"

                test_results["comparison"] = comparison

        return ApiResponse.success_response(
            data=test_results,
            message="🧪 无头/可见模式对比测试完成"
        )

    except Exception as e:
        return ApiResponse.error_response(
            code=BusinessCode.INTERNAL_ERROR,
            message=f"测试过程中发生错误: {str(e)}"
        )


@router.post("/markdown/clean", response_model=MarkdownResponse)
async def crawl_markdown_clean(request: MarkdownRequest) -> MarkdownResponse:
    """
    获取超级干净的 Markdown 内容 - 专门用于 LLM 消费

    使用最激进的过滤设置，去除所有链接、导航、广告等噪音
    专门优化用于AI处理的内容
    """
    if not is_valid_url(request.url):
        return ApiResponse.error_response(
            code=BusinessCode.INVALID_URL,
            message="无效的URL格式"
        )

    try:
        # 🔧 创建超级清理版本的请求
        clean_request = MarkdownRequest(
            url=request.url,
            format=MarkdownFormat.FIT,  # 强制使用fit模式
            js_enabled=request.js_enabled,
            bypass_cache=request.bypass_cache,
            css_selector=request.css_selector,
            ignore_links=True,  # 强制忽略链接
            escape_html=False,
            body_width=0,
        )

        # 使用专门的清理配置
        data = await _crawl_markdown_with_clean_config(clean_request)

        return ApiResponse.success_response(
            data=data,
            message="超级清理模式 Markdown 获取成功"
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
            message=f"超级清理模式失败: {str(e)}"
        )


@router.post("/markdown/query", response_model=MarkdownResponse)
async def crawl_markdown_with_query(
    request: MarkdownRequest,
    query: str = Query(..., description="搜索查询，用于BM25内容过滤")
) -> MarkdownResponse:
    """
    基于查询的智能 Markdown 提取

    使用 BM25 算法根据查询内容提取最相关的部分
    例如: query="Trump China trade" 将提取与贸易相关的内容
    """
    if not is_valid_url(request.url):
        return ApiResponse.error_response(
            code=BusinessCode.INVALID_URL,
            message="无效的URL格式"
        )

    try:
        # 创建带查询的请求
        query_request = MarkdownRequest(
            url=request.url,
            format=MarkdownFormat.FIT,
            js_enabled=request.js_enabled,
            bypass_cache=request.bypass_cache,
            css_selector=request.css_selector,
            ignore_links=True,
            escape_html=False,
        )

        data = await _crawl_markdown_with_query(query_request, query)

        return ApiResponse.success_response(
            data=data,
            message=f"基于查询 '{query}' 的智能提取完成"
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
            message=f"智能查询提取失败: {str(e)}"
        )
