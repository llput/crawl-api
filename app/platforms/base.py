# app/platforms/base.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from pydantic import BaseModel


class PlatformConfig(BaseModel):
    """平台配置基类"""
    name: str
    display_name: str
    enabled: bool = True
    site_name: str  # 对应认证配置中的site_name
    default_source_url: str
    version: str = "1.0.0"


class BasePlatform(ABC):
    """平台基类 - 基于现有auth_crawler_service扩展"""

    def __init__(self, auth_service):
        self.auth_service = auth_service
        self.config = self.get_config()

    @abstractmethod
    def get_config(self) -> PlatformConfig:
        """获取平台配置"""
        pass

    @abstractmethod
    async def extract_content_links(
        self,
        source_url: Optional[str] = None,
        max_links: int = 20,
        **kwargs
    ) -> Dict[str, Any]:
        """提取内容链接"""
        pass

    @abstractmethod
    async def crawl_content_by_id(
        self,
        content_id: str,
        source_url: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """根据内容ID爬取内容"""
        pass

    @abstractmethod
    def parse_content_id_from_url(self, url: str) -> Optional[str]:
        """从URL中解析内容ID"""
        pass

    def is_available(self) -> bool:
        """检查平台是否可用（认证配置是否存在）"""
        import os
        profile_path = self.auth_service.get_profile_path(
            self.config.site_name)
        return os.path.exists(profile_path)
