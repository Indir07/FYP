FROM python:3.11-slim

WORKDIR /app

# Install dependencies (separate files let us skip unused heavy deps like torch).
COPY requirements.base.txt /app/requirements.base.txt
COPY requirements.ml.txt /app/requirements.ml.txt
RUN pip install --no-cache-dir -r /app/requirements.base.txt -r /app/requirements.ml.txt

# Copy application code
COPY app /app/app

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

