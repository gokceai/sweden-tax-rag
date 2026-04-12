FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements ./requirements
COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements/base.in -r requirements/ml.in -r requirements/ui.in && \
    pip install --no-cache-dir -e .

# Run as non-root inside container.
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER 1000

EXPOSE 8080

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
