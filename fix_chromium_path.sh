#!/bin/bash
# 应急修复 - 创建符号链接让 crawl4ai 找到正确的浏览器

echo "⚡ 应急修复：创建符号链接"
echo "=============================="

# 你的实际浏览器路径
ACTUAL_PATH="/Users/M16/Library/Caches/ms-playwright/chromium-1169"

# crawl4ai 期望的路径
EXPECTED_PATH="/Users/M16/Library/Caches/ms-playwright/chromium-1155"

# 检查实际路径是否存在
if [ ! -d "$ACTUAL_PATH" ]; then
    echo "❌ 错误：实际路径不存在 $ACTUAL_PATH"
    exit 1
fi

# 检查期望路径是否已存在
if [ -e "$EXPECTED_PATH" ]; then
    echo "⚠️  目标路径已存在，先备份..."
    mv "$EXPECTED_PATH" "${EXPECTED_PATH}.backup.$(date +%s)"
fi

# 创建符号链接
echo "🔗 创建符号链接: $EXPECTED_PATH -> $ACTUAL_PATH"
ln -s "$ACTUAL_PATH" "$EXPECTED_PATH"

if [ $? -eq 0 ]; then
    echo "✅ 符号链接创建成功！"
    echo "📋 验证链接："
    ls -la "$EXPECTED_PATH"

    echo "🧪 测试浏览器可执行文件："
    BROWSER_EXEC="$EXPECTED_PATH/chrome-mac/Chromium.app/Contents/MacOS/Chromium"
    if [ -x "$BROWSER_EXEC" ]; then
        echo "✅ 浏览器可执行文件正常"
        echo "🎉 修复完成！现在可以重启服务测试"
    else
        echo "❌ 浏览器可执行文件有问题"
        echo "🔧 尝试修复权限..."
        chmod +x "$BROWSER_EXEC"
    fi
else
    echo "❌ 符号链接创建失败"
    exit 1
fi

echo ""
echo "🚀 接下来请："
echo "1. 重启你的 crawl4ai 服务"
echo "2. 测试认证爬取功能"
echo ""
echo "如果问题解决，可以将此修复添加到启动脚本中"