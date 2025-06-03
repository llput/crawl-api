.PHONY: install start stop help clean

# 默认目标
help:
	@echo "Crawl4AI API 管理命令:"
	@echo ""
	@echo "  make install    - 安装依赖"
	@echo "  make start      - 启动服务"
	@echo "  make dev        - 开发模式启动"
	@echo "  make setup      - 首次安装并启动"
	@echo "  make clean      - 清理虚拟环境"
	@echo "  make help       - 显示此帮助信息"
	@echo ""

# 首次安装并启动
setup:
	@chmod +x run.sh start.sh
	@./run.sh

# 仅安装依赖
install:
	@chmod +x run.sh
	@./run.sh --install-only

# 启动服务（生产模式）
start:
	@chmod +x start.sh
	@./start.sh --no-dev

# 开发模式启动
dev:
	@chmod +x start.sh
	@./start.sh

# 清理虚拟环境
clean:
	@echo "清理虚拟环境..."
	@rm -rf venv
	@echo "虚拟环境已删除"

# 快速重建
rebuild: clean setup