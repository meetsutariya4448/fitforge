FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
# Install torch CPU-only first (~300 MB) to avoid the full CUDA build (~800 MB)
RUN pip install --no-cache-dir torch==2.3.1+cpu \
        --extra-index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
