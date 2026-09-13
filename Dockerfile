# Dockerfile
# 多阶段构建

# 构建阶段
FROM python:3.12-slim as builder

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# 运行阶段
FROM python:3.12-slim

WORKDIR /app

# 创建非 root 用户
RUN groupadd -r bookeeper && useradd -r -g bookeeper bookeeper

# 从构建阶段复制依赖
COPY --from=builder /install /usr/local

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p /app/data /app/backups /app/covers && \
    chown -R bookeeper:bookeeper /app

# 切换到非 root 用户
USER bookeeper

# 暴露端口
EXPOSE 8899

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8899/')" || exit 1

# 启动命令
CMD ["python", "main.py"]