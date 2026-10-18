FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 MPLBACKEND=Agg
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install -e ".[benchmark]"
COPY app ./app
COPY data ./data
COPY reports ./reports
COPY .streamlit ./.streamlit
RUN useradd --create-home --uid 10002 appuser && mkdir -p /app/.cache && chown -R 10002:10002 /app
USER appuser
EXPOSE 8501
CMD ["streamlit", "run", "app/dashboard.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--server.baseUrlPath=fase2", "--browser.gatherUsageStats=false"]
