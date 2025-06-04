# app/models/platform_models.py
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class PlatformInfo(BaseModel):
    """平台信息模型"""
    name: str = Field(..., description="平台名称")
    display_name: str = Field(..., description="平台显示名称")
    version: str = Field(..., description="模块版本")
    enabled: bool = Field(..., description="是否启用")
    available: bool = Field(..., description="是否可用（认证配置是否存在）")


class ContentLinkInfo(BaseModel):
    """内容链接信息模型"""
    content_id: str = Field(..., description="内容ID")
    url: str = Field(..., description="访问URL")
    has_valid_token: bool = Field(..., description="是否包含有效token")
    tokens: List[str] = Field(default_factory=list, description="token参数列表")
    preview_title: Optional[str] = Field(None, description="预览标题")


class PlatformLinksData(BaseModel):
    """平台链接数据模型"""
    platform: str = Field(..., description="平台名称")
    platform_display_name: str = Field(..., description="平台显示名称")
    source_url: str = Field(..., description="源页面URL")
    total_count: int = Field(..., description="链接总数")
    extracted_at: str = Field(..., description="提取时间")

    notes: List[Dict[str, Any]] = Field(
        default_factory=list, description="提取到的笔记/内容信息列表")
    raw_links: List[Dict[str, Any]] = Field(
        default_factory=list, description="原始链接数据（字典数组）")


class MediaInfo(BaseModel):
    """媒体信息模型"""
    images: List[Dict[str, Any]] = Field(
        default_factory=list, description="图片信息")
    videos: List[Dict[str, Any]] = Field(
        default_factory=list, description="视频信息")
    total_count: int = Field(0, description="媒体文件总数")


class LinksInfo(BaseModel):
    """链接信息模型"""
    internal_links: List[Dict[str, str]] = Field(
        default_factory=list, description="内部链接")
    external_links: List[Dict[str, str]] = Field(
        default_factory=list, description="外部链接")
    total_count: int = Field(0, description="链接总数")


class PlatformContentData(BaseModel):
    """平台内容数据模型"""
    platform: str = Field(..., description="平台名称")
    platform_display_name: str = Field(..., description="平台显示名称")
    content_id: str = Field(..., description="内容ID")
    url: str = Field(..., description="访问URL")
    title: str = Field(..., description="标题")
    content: Optional[str] = Field(None, description="内容（Markdown格式）")
    content_type: str = Field("unknown", description="内容类型")
    author: Optional[str] = Field(None, description="作者")
    status_code: Optional[int] = Field(None, description="HTTP状态码")
    crawled_at: str = Field(..., description="爬取时间")
    media_info: MediaInfo = Field(
        default_factory=MediaInfo, description="媒体信息")
    links_info: LinksInfo = Field(
        default_factory=LinksInfo, description="链接信息")

# 小红书特定模型


class XiaohongshuNote(BaseModel):
    """小红书笔记链接信息 - 修复版本"""
    content_id: str = Field(..., description="内容ID")
    note_id: str = Field(..., description="笔记ID")
    url: str = Field(..., description="访问URL")
    has_valid_token: bool = Field(..., description="是否包含有效token")
    tokens: List[str] = Field(default_factory=list, description="token参数列表")
    preview_title: str = Field(..., description="预览标题")
    xsec_token: Optional[str] = Field(None, description="xsec_token值")
    xsec_source: Optional[str] = Field(None, description="xsec_source值")
    complete_params: bool = Field(False, description="参数是否完整")


class XiaohongshuLinksData(PlatformLinksData):
    """小红书链接数据 - 修复版本"""
    notes: List[XiaohongshuNote] = Field(..., description="笔记信息列表")
    raw_links: List[Dict[str, Any]] = Field(
        default_factory=list, description="原始链接数据（字典数组）")


class XiaohongshuNoteData(PlatformContentData):
    """小红书笔记内容数据"""
    note_id: str = Field(..., description="笔记ID")
    raw_data: Dict[str, Any] = Field(
        default_factory=dict, description="原始爬取数据")

# 请求模型


class PlatformExtractRequest(BaseModel):
    """平台内容提取请求"""
    platform: str = Field(..., description="平台名称")
    source_url: Optional[str] = Field(None, description="源页面URL")
    max_links: int = Field(20, description="最大提取链接数")


class PlatformCrawlRequest(BaseModel):
    """平台内容爬取请求"""
    platform: str = Field(..., description="平台名称")
    content_id: str = Field(..., description="内容ID")
    source_url: Optional[str] = Field(None, description="源页面URL")
