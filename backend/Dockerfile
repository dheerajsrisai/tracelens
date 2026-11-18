FROM python:3.11-slim

# libgl1 / libglib2.0: required by OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app

# CPU-only PyTorch (much smaller than the CUDA build)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the YOLO11 weights into the image so the first analysis does not need internet
RUN python -c "from ultralytics import YOLO; YOLO('yolo11n.pt')" || echo "weights will be downloaded on first use"

COPY app ./app
ENV MEDIA_DIR=/data/media
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
