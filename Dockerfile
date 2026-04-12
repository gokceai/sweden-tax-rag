FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
COPY pyproject.toml ./
COPY src ./src

# requirements.txt is UTF-16 LE encoded; convert to UTF-8 before pip reads it.
RUN python -c "
import pathlib
p = pathlib.Path('requirements.txt')
p.write_text(p.read_text(encoding='utf-16'), encoding='utf-8')
" && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -e .

EXPOSE 8080

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
