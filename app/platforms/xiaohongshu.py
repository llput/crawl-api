# app/platforms/xiaohongshu.py (增强版本)
import re
import logging
import asyncio
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
from datetime import datetime

from .base import BasePlatform, PlatformConfig
from app.services.crawler_service import CrawlerException
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

logger = logging.getLogger(__name__)


class XiaohongshuPlatform(BasePlatform):
    """小红书平台实现 - 增强版本，专门处理小红书的特殊需求"""

    def __init__(self, auth_service):
        super().__init__(auth_service)
        self._token_cache = {}  # 简单的token缓存
        self._cache_ttl = 300   # 5分钟缓存

    def get_config(self) -> PlatformConfig:
        return PlatformConfig(
            name="xiaohongshu",
            display_name="小红书",
            enabled=True,
            site_name="xiaohongshu_com",
            default_source_url="https://www.xiaohongshu.com/explore",
            version="1.1.0"
        )

    async def extract_content_links(
        self,
        source_url: Optional[str] = None,
        max_links: int = 20,
        **kwargs
    ) -> Dict[str, Any]:
        """提取小红书笔记链接 - 带调试的修复版本"""
        try:
            if not source_url:
                source_url = self.config.default_source_url

            logger.info(f"🔍 正在从小红书提取链接: {source_url}")

            browser_config = await self._get_xiaohongshu_browser_config()
            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=60000,
                wait_for_images=False,
            )

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=source_url, config=config)

                if not result.success:
                    raise CrawlerException(
                        message=f"访问小红书探索页失败: {result.error_message}",
                        error_type="access_failed"
                    )

                # 🔍 添加HTML内容调试
                html_content = getattr(result, 'html', '')
                logger.info(f"🔍 获取到的HTML长度: {len(html_content)}")

                # 简单检查是否包含小红书笔记链接
                explore_links_count = html_content.count('/explore/')
                logger.info(f"🔍 页面中包含 {explore_links_count} 个 /explore/ 链接")

                # 使用修复后的链接提取逻辑
                notes = self._extract_xiaohongshu_notes_from_html(
                    html_content, source_url, max_links
                )

                # 🔍 详细的notes调试信息
                logger.info(f"🔍 提取到的notes数量: {len(notes)}")
                if notes:
                    logger.info(f"🔍 第一个note示例: {notes[0]}")
                else:
                    logger.warning("⚠️ 没有提取到任何notes!")
                    # 尝试简单的链接提取作为备选
                    notes = self._fallback_extract_links(
                        html_content, source_url, max_links)
                    logger.info(f"🔄 备选方法提取到: {len(notes)} 个链接")

                # 构造raw_links
                raw_links = []
                for note in notes:
                    try:
                        raw_links.append({
                            "url": note.get("url", ""),
                            "note_id": note.get("note_id", ""),
                            "has_token": note.get("has_valid_token", False),
                            "query_params": note.get("tokens", [])
                        })
                    except Exception as e:
                        logger.warning(f"⚠️ 处理note时出错: {str(e)}")
                        continue

                logger.info(f"✅ 成功提取 {len(notes)} 个小红书笔记链接")
                logger.info(f"🔍 raw_links数量: {len(raw_links)}")

                # 确保返回完整的数据结构
                result_data = {
                    "platform": self.config.name,
                    "platform_display_name": self.config.display_name,
                    "source_url": source_url,
                    "notes": notes,  # 确保包含notes
                    "total_count": len(notes),
                    "extracted_at": datetime.now().isoformat(),
                    "raw_links": raw_links  # 确保包含raw_links
                }

                # 🔍 最终数据验证
                logger.info(f"🔍 返回数据keys: {list(result_data.keys())}")
                logger.info(
                    f"🔍 notes字段类型: {type(result_data['notes'])}, 长度: {len(result_data['notes'])}")

                return result_data

        except Exception as e:
            logger.error(f"❌ 小红书链接提取失败: {str(e)}")
            raise CrawlerException(
                message=f"小红书链接提取失败: {str(e)}",
                error_type="extract_failed"
            )

    async def crawl_content_by_id(
        self,
        content_id: str,
        source_url: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """爬取小红书笔记内容 - 增强版本"""
        try:
            logger.info(f"📝 正在爬取小红书笔记: {content_id}")

            # 第一步：获取有效的访问链接
            target_url = await self._get_note_access_url(content_id, source_url)

            if not target_url:
                raise CrawlerException(
                    message=f"无法获取笔记 {content_id} 的有效访问链接",
                    error_type="link_not_found"
                )

            logger.info(f"🔗 构造的访问链接: {target_url}")

            # 第二步：爬取笔记内容
            browser_config = await self._get_xiaohongshu_browser_config()
            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=60000,
                wait_for_images=True,
            )

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=target_url, config=config)

                if not result.success:
                    raise CrawlerException(
                        message=f"爬取笔记内容失败: {result.error_message}",
                        error_type="crawl_failed"
                    )

                # 第三步：解析和格式化数据
                note_data = self._parse_xiaohongshu_note(
                    result, content_id, target_url
                )

                logger.info(f"✅ 小红书笔记 {content_id} 爬取成功")
                return note_data

        except CrawlerException:
            raise
        except Exception as e:
            logger.error(f"❌ 小红书笔记爬取失败: {str(e)}")
            raise CrawlerException(
                message=f"小红书笔记 {content_id} 爬取失败: {str(e)}",
                error_type="crawl_failed"
            )

    async def _get_note_access_url(
        self,
        note_id: str,
        source_url: Optional[str] = None
    ) -> Optional[str]:
        """获取笔记的有效访问URL - 增强版本"""

        logger.info(f"🎯 正在获取笔记 {note_id} 的访问URL")

        # 方法1：从缓存的token构造
        cached_token = self._get_cached_token()
        if cached_token:
            url = self._build_note_url_with_token(note_id, cached_token)
            if url:
                logger.info(f"📦 使用缓存token构造URL: {url}")
                return url

        # 方法2：从探索页提取新token
        try:
            logger.info("🔍 从探索页提取新的token...")
            links_data = await self.extract_content_links(source_url, max_links=50)

            # 🔧 优先查找参数完整的链接
            complete_links = [note for note in links_data["notes"]
                              if note.get("complete_params", False)]
            target_links = complete_links if complete_links else links_data["notes"]

            # 查找目标笔记的直接链接
            for note in target_links:
                if note["note_id"] == note_id:
                    self._cache_token_from_url(note["url"])
                    logger.info(f"🎯 找到目标笔记链接: {note['url']}")
                    return note["url"]

            # 如果没找到目标笔记，使用第一个完整参数的链接构造
            if target_links:
                first_note_url = target_links[0]["url"]
                token_info = self._extract_token_from_url(first_note_url)
                if token_info:
                    self._cache_token(token_info)
                    constructed_url = self._build_note_url_with_token(
                        note_id, token_info)
                    logger.info(f"🔨 使用第一个链接的token构造: {constructed_url}")
                    return constructed_url

        except Exception as e:
            logger.warning(f"⚠️ 从探索页获取token失败: {str(e)}")

        return None

    def _extract_xiaohongshu_notes_from_html(
        self,
        html: str,
        base_url: str,
        max_links: int
    ) -> List[Dict[str, Any]]:
        """从HTML中提取小红书笔记链接 - 改进的调试版本"""
        notes = []

        # 🔍 先检查HTML基本内容
        if not html or len(html) < 1000:
            logger.warning(f"⚠️ HTML内容异常，长度: {len(html)}")
            return notes

        # 检查是否包含小红书相关内容
        if "xiaohongshu" not in html.lower() and "explore" not in html.lower():
            logger.warning("⚠️ HTML中没有发现小红书相关内容")

        # 更精确的链接模式
        patterns = [
            r'href="(/explore/[a-f0-9]{24}\?[^"]*)"',  # 精确匹配24位ID
            r'"(/explore/[a-f0-9]{24}\?[^"]*)"',
            r'data-href="(/explore/[a-f0-9]{24}\?[^"]*)"',
        ]

        all_matches = set()

        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            logger.info(f"🔍 模式 {pattern} 匹配到 {len(matches)} 个链接")
            all_matches.update(matches)

        logger.info(f"🔍 总共去重后有 {len(all_matches)} 个唯一链接")

        for i, match in enumerate(list(all_matches)[:max_links]):
            full_url = urljoin(base_url, match)
            note_id = self.parse_content_id_from_url(full_url)

            if note_id:
                parsed = urlparse(full_url)
                query_params = parse_qs(parsed.query)

                has_xsec_token = "xsec_token" in query_params
                has_xsec_source = "xsec_source" in query_params

                note_info = {
                    "content_id": note_id,
                    "note_id": note_id,
                    "url": full_url,
                    "has_valid_token": has_xsec_token and has_xsec_source,
                    "tokens": list(query_params.keys()),
                    "preview_title": f"小红书笔记 {note_id}",
                    "xsec_token": query_params.get("xsec_token", [None])[0],
                    "xsec_source": query_params.get("xsec_source", [None])[0],
                    "complete_params": has_xsec_token and has_xsec_source
                }

                notes.append(note_info)
                logger.debug(f"🔍 添加note: {note_id}")

        # 优先返回参数完整的链接
        notes.sort(key=lambda x: x["complete_params"], reverse=True)
        logger.info(f"🔍 最终提取并排序后: {len(notes)} 个notes")

        return notes

    def _parse_xiaohongshu_note(
        self,
        crawl_result,
        note_id: str,
        url: str
    ) -> Dict[str, Any]:
        """解析小红书笔记内容 - 专门优化"""

        html = getattr(crawl_result, 'html', '')
        markdown = getattr(crawl_result, 'markdown', '')

        # 提取标题
        title = self._extract_xiaohongshu_title(html, markdown)

        # 提取内容
        content = self._clean_xiaohongshu_content(markdown)

        # 提取作者
        author = self._extract_xiaohongshu_author(html)

        # 提取互动数据
        interaction_data = self._extract_xiaohongshu_interactions(html)

        # 处理媒体
        media_info = self._process_xiaohongshu_media(crawl_result)

        # 检测内容类型
        content_type = self._detect_xiaohongshu_content_type(html, media_info)

        return {
            "platform": self.config.name,
            "platform_display_name": self.config.display_name,
            "content_id": note_id,  # 🆕 添加这行
            "note_id": note_id,
            "url": url,
            "title": title,
            "content": content,
            "content_type": content_type,
            "author": author,
            "status_code": getattr(crawl_result, 'status_code', None),
            "crawled_at": datetime.now().isoformat(),
            "media_info": media_info,
            "raw_data": {
                "html_length": len(html),
                "markdown_length": len(markdown),
                "status_code": getattr(crawl_result, 'status_code', None)
            }
        }

    async def _get_xiaohongshu_browser_config(self) -> BrowserConfig:
        """获取专门针对小红书优化的浏览器配置"""
        return self.auth_service._create_auth_browser_config(
            site_name=self.config.site_name,
            js_enabled=True,
            headless=True
        )

    def parse_content_id_from_url(self, url: str) -> Optional[str]:
        """从URL中解析笔记ID"""
        match = re.search(r'/explore/([a-f0-9]+)', url)
        return match.group(1) if match else None

    def _extract_xiaohongshu_title(self, html: str, markdown: str) -> str:
        """提取小红书笔记标题"""
        # 尝试从HTML中提取title标签
        title_match = re.search(
            r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
            # 清理小红书标题中的后缀
            title = re.sub(r'\s*-\s*小红书.*$', '', title)
            if len(title) > 3:
                return title

        # 从markdown中提取第一行有意义的内容
        if markdown:
            lines = markdown.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and len(line) > 3 and not line.startswith('http'):
                    # 清理markdown格式
                    clean_line = re.sub(r'[#*`\[\]()]', '', line).strip()
                    if len(clean_line) > 3:
                        return clean_line[:50]

        return "小红书笔记"

    def _clean_xiaohongshu_content(self, markdown: str) -> str:
        """清理小红书内容"""
        if not markdown:
            return ""

        # 移除导航链接和无关内容
        lines = markdown.split('\n')
        clean_lines = []

        skip_patterns = [
            r'^https?://',
            r'^\[.*\]\(.*\)$',
            r'^(登录|注册|下载|Sign|Login)',
            r'^小红书',
            r'^Medium Logo'
        ]

        for line in lines:
            line = line.strip()
            if line and not any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
                clean_lines.append(line)

        return '\n'.join(clean_lines)

    def _extract_xiaohongshu_author(self, html: str) -> Optional[str]:
        """提取小红书作者信息"""
        # 多种作者提取模式
        author_patterns = [
            r'"author"\s*:\s*"([^"]+)"',
            r'"nickname"\s*:\s*"([^"]+)"',
            r'data-author="([^"]+)"',
            r'class="[^"]*author[^"]*"[^>]*>([^<]+)</[^>]*>',
        ]

        for pattern in author_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                author = match.group(1).strip()
                if len(author) > 0 and len(author) < 50:
                    return author

        return None

    def _extract_xiaohongshu_interactions(self, html: str) -> Dict[str, Any]:
        """提取小红书互动数据（点赞、评论、收藏）"""
        interactions = {
            "likes_count": None,
            "comments_count": None,
            "collects_count": None,
            "shares_count": None
        }

        # 这里可以添加具体的提取逻辑
        # 由于小红书页面结构复杂，需要根据实际HTML结构调整

        return interactions

    def _process_xiaohongshu_media(self, crawl_result) -> Dict[str, Any]:
        """处理小红书媒体信息"""
        media_info = {
            "images": [],
            "videos": [],
            "total_count": 0
        }

        if hasattr(crawl_result, 'media') and crawl_result.media:
            if "images" in crawl_result.media:
                for img in crawl_result.media["images"]:
                    if isinstance(img, dict) and "src" in img:
                        # 过滤小红书的有效图片
                        src = img["src"]
                        if "xiaohongshu" in src or "xhscdn" in src:
                            media_info["images"].append({
                                "url": src,
                                "alt": img.get("alt", ""),
                                "width": img.get("width"),
                                "height": img.get("height")
                            })

        media_info["total_count"] = len(
            media_info["images"]) + len(media_info["videos"])
        return media_info

    def _detect_xiaohongshu_content_type(self, html: str, media_info: Dict) -> str:
        """检测小红书内容类型"""
        if media_info["total_count"] > 0:
            if len(media_info["videos"]) > 0:
                return "视频"
            elif len(media_info["images"]) > 0:
                return "图文"

        # 从HTML中检测
        if "video" in html.lower() or "视频" in html:
            return "视频"
        elif "image" in html.lower() or "图片" in html:
            return "图文"

        return "文字"

    # Token缓存相关方法
    def _get_cached_token(self) -> Optional[Dict[str, str]]:
        """获取缓存的token"""
        cache_time = self._token_cache.get("timestamp", 0)
        if datetime.now().timestamp() - cache_time < self._cache_ttl:
            return self._token_cache.get("token_info")
        return None

    def _cache_token(self, token_info: Dict[str, str]):
        """缓存token信息"""
        self._token_cache = {
            "token_info": token_info,
            "timestamp": datetime.now().timestamp()
        }

    def _cache_token_from_url(self, url: str):
        """从URL中提取并缓存token"""
        token_info = self._extract_token_from_url(url)
        if token_info:
            self._cache_token(token_info)

    def _extract_token_from_url(self, url: str) -> Optional[Dict[str, str]]:
        """从URL中提取token信息 - 修复版本"""
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        token_info = {}

        # 确保提取所有必要参数
        if "xsec_token" in query_params:
            token_info["xsec_token"] = query_params["xsec_token"][0]

        if "xsec_source" in query_params:
            token_info["xsec_source"] = query_params["xsec_source"][0]
        else:
            # 🔧 如果没有xsec_source，使用默认值
            token_info["xsec_source"] = "pc_feed"

        # 🆕 添加其他可能的参数
        if "channel_id" in query_params:
            token_info["channel_id"] = query_params["channel_id"][0]

        return token_info if "xsec_token" in token_info else None

    def _build_note_url_with_token(self, note_id: str, token_info: Dict[str, str]) -> str:
        """使用token信息构造笔记URL - 修复版本"""
        base_url = f"https://www.xiaohongshu.com/explore/{note_id}"

        params = {}

        # 必须的参数
        if "xsec_token" in token_info:
            params["xsec_token"] = token_info["xsec_token"]

        # 🔧 确保包含xsec_source参数
        if "xsec_source" in token_info:
            params["xsec_source"] = token_info["xsec_source"]
        else:
            params["xsec_source"] = "pc_feed"  # 默认值

        # 可选参数
        if "channel_id" in token_info:
            params["channel_id"] = token_info["channel_id"]

        if params:
            param_string = urlencode(params)
            constructed_url = f"{base_url}?{param_string}"
            logger.info(f"🔗 构造的完整URL: {constructed_url}")
            return constructed_url

        return base_url

    def _validate_note_url(self, url: str) -> bool:
        """验证笔记URL是否包含必要参数"""
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        has_xsec_token = "xsec_token" in query_params
        has_xsec_source = "xsec_source" in query_params

        if not has_xsec_token:
            logger.warning("⚠️ URL缺少xsec_token参数")
        if not has_xsec_source:
            logger.warning("⚠️ URL缺少xsec_source参数")

        return has_xsec_token and has_xsec_source

    def _fallback_extract_links(self, html: str, base_url: str, max_links: int) -> List[Dict[str, Any]]:
        """备选的链接提取方法 - 更宽松的匹配"""
        notes = []

        # 更简单的正则表达式，先确保能提取到基本链接
        simple_patterns = [
            r'/explore/([a-f0-9]+)',  # 最简单的笔记ID匹配
            r'href="[^"]*(/explore/[a-f0-9]+[^"]*)"',  # 带href的链接
        ]

        found_ids = set()

        for pattern in simple_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    note_id = match[0] if match[0] else match[1]
                    full_path = match[1] if len(
                        match) > 1 else f"/explore/{match[0]}"
                else:
                    if match.startswith('/explore/'):
                        note_id = match.replace('/explore/', '').split('?')[0]
                        full_path = match
                    else:
                        note_id = match
                        full_path = f"/explore/{match}"

                if note_id and len(note_id) == 24 and note_id not in found_ids:  # 小红书ID通常是24位
                    found_ids.add(note_id)

                    # 构造完整URL
                    full_url = urljoin(base_url, full_path)

                    note_info = {
                        "content_id": note_id,
                        "note_id": note_id,
                        "url": full_url,
                        "has_valid_token": "xsec_token" in full_path,
                        "tokens": [],
                        "preview_title": f"小红书笔记 {note_id}",
                        "xsec_token": None,
                        "xsec_source": None,
                        "complete_params": False
                    }

                    notes.append(note_info)

                    if len(notes) >= max_links:
                        break

        logger.info(f"🔄 备选方法提取到 {len(notes)} 个基础链接")
        return notes[:max_links]
