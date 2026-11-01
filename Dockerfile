# ===== 多阶段构建（M4）=====
# 阶段一：node 构建 Vue3 前端 → dist
# 阶段二：python 运行时 + 前端 dist

# ---------- 前端构建 ----------
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json ./
# 国内网络使用 npmmirror 镜像；海外构建可去掉 --registry 参数
RUN npm install --registry=https://registry.npmmirror.com --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- Python 运行时 ----------
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 先装依赖（利用层缓存）
COPY pyproject.toml ./
COPY README.md ./
COPY app ./app
# 语义检索依赖（fastembed + ONNX）会让镜像增大约 200MB，默认不装；
# 需要时 docker compose build --build-arg INSTALL_SEMANTIC=true
ARG INSTALL_SEMANTIC=false
RUN if [ "$INSTALL_SEMANTIC" = "true" ]; then \
        pip install --no-cache-dir ".[semantic]"; \
    else \
        pip install --no-cache-dir .; \
    fi

# 前端构建产物（M4 起为 Vue3 dist）
COPY --from=frontend /frontend/dist ./frontend/dist

# 非 root 运行（坑 #3：PUID/PGID 映射）
RUN useradd -m -u 1000 appuser && mkdir -p /vault /data && chown -R appuser:appuser /app /vault /data
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
