FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 默认使用清华 PyPI 镜像（部分网络环境直连 pypi.org 不稳定）；
# 可通过 --build-arg PIP_INDEX_URL=https://pypi.org/simple 覆盖
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -i "$PIP_INDEX_URL" -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
