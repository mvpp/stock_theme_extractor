# Core extraction library — for batch processing jobs
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY stock_themes/ ./stock_themes/
COPY scripts/ ./scripts/
RUN pip install --no-cache-dir -e .
CMD ["python", "-m", "stock_themes"]
