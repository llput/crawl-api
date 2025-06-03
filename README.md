# Crawl4AI API

## 快速启动

### 方式一：使用 Makefile（推荐）

```bash
# 首次安装并启动
make setup

# 日常开发启动
make dev

# 生产模式启动
make start

# 仅安装依赖
make install

# 查看所有命令
make help
```

### 方式二：直接使用脚本

```bash
# 给脚本执行权限（首次需要）
chmod +x run.sh start.sh
```

#### 首次使用（安装 + 启动）

```bash
# 首次安装并启动
./run.sh
```

#### 日常启动（仅启动服务）

```bash
# 快速启动（推荐用于日常开发）
./start.sh

# 或指定端口
./start.sh --port=8002
```

#### 仅安装依赖

```bash
# 只安装依赖，不启动服务
./run.sh --install-only
```

## 脚本说明

- **`run.sh`**: 完整的安装+启动流程，适合首次使用或重新安装依赖
- **`start.sh`**: 纯启动脚本，假设依赖已安装，启动速度更快，适合日常开发

### 脚本选项

**run.sh 选项：**

```bash
./run.sh --help              # 显示帮助信息
./run.sh --install-only      # 只安装依赖，不启动
./run.sh --port=8002         # 指定端口号
./run.sh --no-venv           # 不使用虚拟环境
```

**start.sh 选项：**

```bash
./start.sh --help           # 显示帮助信息
./start.sh --port=8002      # 指定端口号
./start.sh --no-venv        # 不使用虚拟环境
./start.sh --no-dev         # 禁用开发模式（不自动重载）
```

## API 使用示例

## 基础爬取接口

```bash
# 基础爬取
curl -X POST http://127.0.0.1:8001/api/v1/crawl/url \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://news.ycombinator.com",
    "js_enabled": true,
    "bypass_cache": false,
    "include_images": true
  }'
```

## Markdown 专用接口

### 获取原始 Markdown 内容

```bash
curl -X POST http://127.0.0.1:8001/api/v1/crawl/markdown \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://news.ycombinator.com",
    "format": "raw",
    "js_enabled": true,
    "bypass_cache": false
  }'
```

### 获取经过内容过滤的 Markdown（更适合 AI 处理）

```bash
curl -X POST http://127.0.0.1:8001/api/v1/crawl/markdown \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://news.ycombinator.com",
    "format": "fit",
    "js_enabled": true,
    "bypass_cache": true
  }'
```

### 同时获取两种格式的 Markdown

```bash
curl -X POST http://127.0.0.1:8001/api/v1/crawl/markdown \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://news.ycombinator.com",
    "format": "both",
    "js_enabled": true,
    "bypass_cache": true
  }'
```

### 自定义 Markdown 生成选项

```bash
curl -X POST http://127.0.0.1:8001/api/v1/crawl/markdown \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://news.ycombinator.com",
    "format": "raw",
    "js_enabled": true,
    "bypass_cache": false,
    "ignore_links": true,
    "escape_html": false,
    "body_width": 80,
    "css_selector": ".main-content"
  }'
```

## 接口说明

### `/api/v1/crawl/url` - 完整爬取接口

返回完整的爬取结果，包括 HTML、Markdown、媒体信息、链接信息等。

### `/api/v1/crawl/markdown` - Markdown 专用接口

专门用于获取页面的 Markdown 内容，支持多种格式选项：

**格式类型 (format)：**

- `raw`: 原始 Markdown 内容
- `fit`: 经过内容过滤的 Markdown，移除噪音内容，更适合 AI 处理
- `both`: 同时返回两种格式

**Markdown 生成选项：**

- `ignore_links`: 是否忽略链接（默认：false）
- `escape_html`: 是否转义 HTML（默认：true）
- `body_width`: 文本换行宽度（可选）
- `css_selector`: CSS 选择器，用于选择特定内容（可选）

**响应示例：**

```json
{
  "url": "https://news.ycombinator.com",
  "success": true,
  "status_code": 200,
  "raw_markdown": "# Example Domain\n\nThis domain is for use in illustrative examples...",
  "fit_markdown": "# Example Domain\n\nThis domain is for use in illustrative examples...",
  "title": "Example Domain",
  "word_count": 156,
  "error_message": null
}
```

## 健康检查

```bash
curl http://127.0.0.1:8001/api/v1/crawl/health
```

## 项目管理

### 清理项目

```bash
# 清理虚拟环境
make clean

# 或手动删除
rm -rf venv
```

### 重建环境

```bash
# 清理并重新安装
make rebuild

# 或分步执行
make clean
make setup
```

## API 文档

启动服务后，访问 http://127.0.0.1:8001/docs 查看完整的 API 文档。

## 响应格式示例

成功响应：

```json
{
  "code": 200,
  "message": "爬取成功",
  "success": true,
  "data": {
    "url": "https://example.com",
    "status_code": 200,
    "markdown": "# Example...",
    "media": {...},
    "links": {...}
  }
}
```

错误响应：

```json
{
  "code": 50001,
  "message": "爬取超时，请稍后重试",
  "success": false,
  "data": null
}
```
