#!/bin/bash

# 设置颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # 无颜色

# 检查python3是否安装
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到python3。请先安装Python 3.10+${NC}"
    exit 1
fi

# 显示帮助信息的函数
show_help() {
    echo -e "使用方法: $0 [选项]"
    echo -e "选项:"
    echo -e "  --help          显示帮助信息"
    echo -e "  --install-only  只安装依赖，不启动服务"
    echo -e "  --port=NUMBER   指定端口号 (默认: 8001)"
    echo -e "  --no-venv       不使用虚拟环境"
    echo -e ""
    echo -e "注意: 此脚本用于首次安装。日常启动请使用 './start.sh'"
    exit 0
}

# 默认配置
INSTALL_ONLY=false
PORT=8001
USE_VENV=true

# 解析命令行参数
for arg in "$@"; do
    case $arg in
        --help)
            show_help
            ;;
        --install-only)
            INSTALL_ONLY=true
            ;;
        --port=*)
            PORT="${arg#*=}"
            ;;
        --no-venv)
            USE_VENV=false
            ;;
        *)
            echo -e "${YELLOW}警告: 未知选项 $arg${NC}"
            ;;
    esac
done

# 项目目录
PROJECT_DIR=$(pwd)

echo -e "${GREEN}🚀 Crawl4AI API 安装脚本${NC}"
echo -e "${GREEN}==========================${NC}"

# 设置虚拟环境
if [ "$USE_VENV" = true ]; then
    echo -e "${GREEN}📦 设置虚拟环境...${NC}"
    if [ ! -d "venv" ]; then
        echo -e "${YELLOW}创建新的虚拟环境...${NC}"
        python3 -m venv venv
        if [ $? -ne 0 ]; then
            echo -e "${RED}错误: 无法创建虚拟环境${NC}"
            exit 1
        fi
    fi

    # 激活虚拟环境
    source venv/bin/activate
    if [ $? -ne 0 ]; then
        echo -e "${RED}错误: 无法激活虚拟环境${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ 虚拟环境已激活${NC}"
fi

# 升级pip
echo -e "${GREEN}⬆️  升级pip...${NC}"
python3 -m pip install --upgrade pip

# 安装依赖
echo -e "${GREEN}📚 安装项目依赖...${NC}"
python3 -m pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo -e "${RED}错误: 安装依赖失败${NC}"
    exit 1
fi

# 安装Playwright
echo -e "${GREEN}🎭 安装Playwright浏览器...${NC}"
python3 -m playwright install chromium
if [ $? -ne 0 ]; then
    echo -e "${RED}错误: 安装Playwright浏览器失败${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 依赖安装完成!${NC}"

# 如果只是安装依赖，则退出
if [ "$INSTALL_ONLY" = true ]; then
    echo -e "${GREEN}✨ 依赖安装完成。${NC}"
    echo -e "${YELLOW}💡 使用 './start.sh' 快速启动服务${NC}"
    echo -e "${YELLOW}💡 或使用 '$0' 重新安装并启动${NC}"
    if [ "$USE_VENV" = true ]; then
        deactivate
    fi
    exit 0
fi

# 创建.env文件（如果不存在）
if [ ! -f ".env" ]; then
    echo "PORT=$PORT" > .env
    echo "LOG_LEVEL=INFO" >> .env
    echo -e "${GREEN}📝 已创建.env文件${NC}"
fi

echo -e "${GREEN}==========================${NC}"
echo -e "${GREEN}🌐 启动Crawl4AI API服务...${NC}"
echo -e "${YELLOW}📍 服务地址: http://127.0.0.1:$PORT${NC}"
echo -e "${YELLOW}📖 API文档: http://127.0.0.1:$PORT/docs${NC}"
echo -e "${YELLOW}🔧 按Ctrl+C停止服务${NC}"
echo -e "${YELLOW}💡 下次启动可直接使用: ./start.sh${NC}"
echo -e "${GREEN}==========================${NC}"

# 启动应用
python3 -m uvicorn app.main:app --host 127.0.0.1 --port $PORT --reload

# 如果使用了虚拟环境，退出虚拟环境
if [ "$USE_VENV" = true ]; then
    deactivate
fi