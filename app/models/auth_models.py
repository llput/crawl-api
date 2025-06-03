# app/models/auth_models.py
from typing import Dict, Optional
from pydantic import BaseModel, Field


class AuthSetupRequest(BaseModel):
    """认证设置请求模型"""
    site_name: str = Field(..., description="站点名称，用作配置文件标识")
    login_url: str = Field(..., description="登录页面URL")
    test_url: str = Field(..., description="用于测试登录状态的URL")
    setup_timeout: int = Field(300, description="设置超时时间（秒）")


class AuthCrawlRequest(BaseModel):
    """认证爬取请求模型"""
    site_name: str = Field(..., description="使用的认证配置名称")
    url: str = Field(..., description="要爬取的URL")
    js_enabled: bool = Field(True, description="是否启用JavaScript")
    bypass_cache: bool = Field(False, description="是否绕过缓存")
    include_images: bool = Field(True, description="是否包含图片信息")
    css_selector: Optional[str] = Field(None, description="CSS选择器，用于选择特定内容")


class AuthMarkdownRequest(BaseModel):
    """认证Markdown请求模型"""
    site_name: str = Field(..., description="使用的认证配置名称")
    url: str = Field(..., description="要爬取的URL")
    js_enabled: bool = Field(True, description="是否启用JavaScript")
    bypass_cache: bool = Field(False, description="是否绕过缓存")
    css_selector: Optional[str] = Field(None, description="CSS选择器，用于选择特定内容")


class AuthSetupData(BaseModel):
    """认证设置响应数据模型"""
    status: str = Field(..., description="设置状态")
    message: str = Field(..., description="设置结果消息")
    profile_path: str = Field(..., description="认证配置文件路径")


class AuthProfileData(BaseModel):
    """认证配置信息模型"""
    site_name: str = Field(..., description="站点名称")
    profile_path: str = Field(..., description="配置文件路径")
    created_time: float = Field(..., description="创建时间戳")


class AuthProfileListData(BaseModel):
    """认证配置列表数据模型"""
    profiles: Dict[str, AuthProfileData] = Field(..., description="认证配置列表")
    total_count: int = Field(..., description="总数量")
