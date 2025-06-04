# app/main.py
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import crawls, auth_crawls, platforms

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# 创建FastAPI应用
app = FastAPI(
    title="Crawl4AI API",
    description="基于Crawl4AI的RESTful API服务，提供网页爬取功能、认证爬取功能和平台特定爬取功能。",
    version="0.1.0",
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加路由
app.include_router(crawls.router)
app.include_router(auth_crawls.router)
app.include_router(platforms.router)


@app.get("/")
async def root():
    """API根路径"""
    # 获取支持的平台信息
    from app.routers.platforms import SUPPORTED_PLATFORMS

    supported_platforms_info = {}
    for name, platform in SUPPORTED_PLATFORMS.items():
        config = platform.config
        supported_platforms_info[name] = {
            "display_name": config.display_name,
            "version": config.version,
            "enabled": config.enabled,
            "available": platform.is_available()
        }

    return {
        "message": "欢迎使用Crawl4AI API - 平台模块化版本",
        "docs_url": "/docs",
        "version": app.version,
        "features": [
            "普通网页爬取",
            "认证网页爬取",
            "Markdown内容提取",
            "页面截图",
            "平台特定内容爬取"
        ],
        "supported_platforms": supported_platforms_info,
        "api_routes": {
            "basic_crawl": "/api/v1/crawl/*",
            "auth_crawl": "/api/v1/auth-crawl/*",
            "platforms": "/api/v1/platforms/*"
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, reload=True)
