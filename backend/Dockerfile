FROM python:3.11-slim

WORKDIR /app

# Install dependencies.
# Note: we install ML deps in a way that avoids pulling optional GPU packages.
COPY requirements.base.txt /app/requirements.base.txt
COPY requirements.ml.txt /app/requirements.ml.txt
RUN pip install --no-cache-dir -r /app/requirements.base.txt

# Install ML libraries. We install `scikit-learn` normally, then install `xgboost`
# without dependencies to avoid heavy optional CUDA/NVIDIA wheels.
# This matches your host xgboost version (3.2.0).
RUN pip install --no-cache-dir scikit-learn
RUN pip install --no-cache-dir --no-deps xgboost==3.2.0

# Copy application code
COPY app /app/app

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

