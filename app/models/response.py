# app/models/response.py
from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel
from .models import CrawlData, MarkdownData, ScreenshotData
from .auth_models import AuthProfileListData
from .platform_models import (
    PlatformInfo, PlatformLinksData, PlatformContentData,
    XiaohongshuLinksData, XiaohongshuNoteData
)

T = TypeVar('T')


class ApiResponse(BaseModel, Generic[T]):
    """统一API响应格式"""
    code: int = 200
    message: str = "success"
    data: Optional[T] = None
    success: bool = True

    @classmethod
    def success_response(cls, data: T = None, message: str = "操作成功") -> 'ApiResponse[T]':
        """创建成功响应"""
        return cls(
            code=200,
            message=message,
            data=data,
            success=True
        )

    @classmethod
    def error_response(cls, code: int = 500, message: str = "操作失败", data: T = None) -> 'ApiResponse[T]':
        """创建错误响应"""
        return cls(
            code=code,
            message=message,
            data=data,
            success=False
        )


class ErrorDetail(BaseModel):
    """错误详情"""
    field: Optional[str] = None
    detail: str


class BusinessCode:
    """业务错误码"""
    SUCCESS = 200

    # 客户端错误 4xx
    INVALID_PARAMS = 400
    INVALID_URL = 40001

    # 服务端错误 5xx
    INTERNAL_ERROR = 500
    CRAWL_TIMEOUT = 50001
    CRAWL_FAILED = 50002


# 统一响应类型定义
CrawlResponse = ApiResponse[CrawlData]
MarkdownResponse = ApiResponse[MarkdownData]
ScreenshotResponse = ApiResponse[ScreenshotData]
AuthProfileListResponse = ApiResponse[AuthProfileListData]
HealthResponse = ApiResponse[dict]

# 平台响应类型
PlatformInfoListResponse = ApiResponse[list[PlatformInfo]]
PlatformLinksResponse = ApiResponse[PlatformLinksData]
PlatformContentResponse = ApiResponse[PlatformContentData]
XiaohongshuLinksResponse = ApiResponse[XiaohongshuLinksData]
XiaohongshuNoteResponse = ApiResponse[XiaohongshuNoteData]
