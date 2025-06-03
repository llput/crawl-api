from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class MarkdownFormat(str, Enum):
    """Markdown格式类型"""
    RAW = "raw"              # 原始markdown
    FIT = "fit"              # 经过内容过滤的markdown，更适合AI处理
    BOTH = "both"            # 返回两种格式


class CrawlRequest(BaseModel):
    """基础爬取请求模型"""
    url: str = Field(..., description="要爬取的URL")
    js_enabled: bool = Field(True, description="是否启用JavaScript")
    bypass_cache: bool = Field(False, description="是否绕过缓存")
    include_images: bool = Field(True, description="是否包含图片信息")
    css_selector: Optional[str] = Field(None, description="CSS选择器，用于选择特定内容")


class MarkdownRequest(BaseModel):
    """Markdown专用请求模型"""
    url: str = Field(..., description="要爬取的URL")
    format: MarkdownFormat = Field(
        MarkdownFormat.RAW, description="Markdown格式类型")
    js_enabled: bool = Field(True, description="是否启用JavaScript")
    bypass_cache: bool = Field(False, description="是否绕过缓存")
    css_selector: Optional[str] = Field(None, description="CSS选择器，用于选择特定内容")
    ignore_links: bool = Field(False, description="是否忽略链接")
    escape_html: bool = Field(True, description="是否转义HTML")
    body_width: Optional[int] = Field(None, description="文本换行宽度")


class CrawlData(BaseModel):
    """完整爬取结果模型"""
    url: str = Field(..., description="爬取的URL")
    status_code: Optional[int] = Field(None, description="HTTP状态码")
    markdown: Optional[str] = Field(None, description="Markdown内容")
    media: Optional[Dict[str, Any]] = Field(None, description="媒体信息")
    links: Optional[Dict[str, Any]] = Field(None, description="链接信息")


class MarkdownData(BaseModel):
    """Markdown响应模型"""
    url: str = Field(..., description="爬取的URL")
    status_code: Optional[int] = Field(None, description="HTTP状态码")
    raw_markdown: Optional[str] = Field(None, description="原始Markdown内容")
    fit_markdown: Optional[str] = Field(None, description="经过过滤的Markdown内容")
    title: Optional[str] = Field(None, description="页面标题")
    word_count: Optional[int] = Field(None, description="内容字数")


class ScreenshotRequest(BaseModel):
    """截图请求模型"""
    url: str = Field(..., description="要截图的URL")
    js_enabled: bool = Field(True, description="是否启用JavaScript")
    bypass_cache: bool = Field(False, description="是否绕过缓存")
    css_selector: Optional[str] = Field(None, description="CSS选择器，用于截取页面特定部分")
    full_page: bool = Field(True, description="是否截取整个页面")
    viewport_width: Optional[int] = Field(1280, description="视窗宽度")
    viewport_height: Optional[int] = Field(720, description="视窗高度")
    wait_for: Optional[str] = Field(None, description="等待特定条件，如'networkidle'")


class ScreenshotData(BaseModel):
    """截图响应数据模型"""
    url: str = Field(..., description="截图的URL")
    status_code: Optional[int] = Field(None, description="HTTP状态码")
    screenshot_base64: Optional[str] = Field(None, description="截图的base64编码数据")
    error_message: Optional[str] = Field(None, description="错误信息")
