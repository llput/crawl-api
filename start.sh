#!/bin/bash

# 设置颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # 无颜色

# 显示帮助信息的函数
show_help() {
    echo -e "使用方法: $0 [选项]"
    echo -e "选项:"
    echo -e "  --help          显示帮助信息"
    echo -e "  --port=NUMBER   指定端口号 (默认: 8001)"
    echo -e "  --no-venv       不使用虚拟环境"
    echo -e "  --dev           开发模式（启用reload）"
    echo -e ""
    echo -e "注意: 此脚本假设依赖已安装。如需安装依赖，请使用 run.sh"
    exit 0
}

# 默认配置
PORT=8001
USE_VENV=true
DEV_MODE=true

# 解析命令行参数
for arg in "$@"; do
    case $arg in
        --help)
            show_help
            ;;
        --port=*)
            PORT="${arg#*=}"
            ;;
        --no-venv)
            USE_VENV=false
            ;;
        --dev)
            DEV_MODE=true
            ;;
        --no-dev)
            DEV_MODE=false
            ;;
        *)
            echo -e "${YELLOW}警告: 未知选项 $arg${NC}"
            ;;
    esac
done

echo -e "${GREEN}🚀 Crawl4AI API 快速启动${NC}"
echo -e "${GREEN}=====================${NC}"

# 检查虚拟环境
if [ "$USE_VENV" = true ]; then
    if [ ! -d "venv" ]; then
        echo -e "${RED}错误: 未找到虚拟环境。请先运行 './run.sh --install-only' 安装依赖${NC}"
        exit 1
    fi

    echo -e "${GREEN}📦 激活虚拟环境...${NC}"
    source venv/bin/activate
    if [ $? -ne 0 ]; then
        echo -e "${RED}错误: 无法激活虚拟环境${NC}"
        exit 1
    fi
fi

# 检查python3是否可用
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到python3${NC}"
    exit 1
fi

# 检查必要的包是否已安装
if ! python3 -c "import crawl4ai, fastapi, uvicorn" 2>/dev/null; then
    echo -e "${RED}错误: 缺少必要的依赖包。请先运行 './run.sh --install-only' 安装依赖${NC}"
    exit 1
fi

# 检查.env文件
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}📝 创建.env文件...${NC}"
    echo "PORT=$PORT" > .env
    echo "LOG_LEVEL=INFO" >> .env
fi

# 构建启动参数
UVICORN_ARGS="app.main:app --host 127.0.0.1 --port $PORT"
if [ "$DEV_MODE" = true ]; then
    UVICORN_ARGS="$UVICORN_ARGS --reload"
fi

echo -e "${GREEN}=====================${NC}"
echo -e "${GREEN}🌐 启动Crawl4AI API服务...${NC}"
echo -e "${YELLOW}📍 服务地址: http://127.0.0.1:$PORT${NC}"
echo -e "${YELLOW}📖 API文档: http://127.0.0.1:$PORT/docs${NC}"
if [ "$DEV_MODE" = true ]; then
    echo -e "${YELLOW}🔄 开发模式: 文件变更时自动重载${NC}"
fi
echo -e "${YELLOW}🔧 按Ctrl+C停止服务${NC}"
echo -e "${GREEN}=====================${NC}"

# 启动应用
python3 -m uvicorn $UVICORN_ARGS

# 如果使用了虚拟环境，退出虚拟环境
if [ "$USE_VENV" = true ]; then
    deactivate
fi