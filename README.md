```bash
# 基础爬取
curl -X POST http://127.0.0.1:8001/api/v1/crawl/url \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://httpbin.org/html",
    "js_enabled": true,
    "bypass_cache": false,
    "include_images": true
  }'
```
