# syntax=docker/dockerfile:1
# Build from the repo root:  docker build -f docker/Dockerfile -t plpr:2.0 .
# One image runs both the API (default CMD) and the edge agent (python -m server.agent ...).

# ---- stage 1: export ONNX from the .pt weights. Torch lives only here, never in the runtime image.
FROM python:3.12-slim AS export
WORKDIR /src
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
# CPU wheels first, so the train extra doesn't pull the multi-GB CUDA build of torch
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchvision
COPY pyproject.toml README.md ./
COPY plpr ./plpr
# yolov5 also imports pandas/seaborn/scipy/tqdm, which ultralytics no longer pulls in
RUN pip install --no-cache-dir ".[train]" pandas seaborn scipy tqdm
COPY yolov5 ./yolov5
COPY scripts/export_onnx.py ./scripts/
COPY model/plateYolo.pt model/CharsYolo.pt ./model/
RUN python scripts/export_onnx.py --out model/onnx

# ---- stage 2: slim runtime (onnxruntime + FastAPI)
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PLPR_DATA_DIR=/data PLPR_DATABASE_URL=sqlite:////data/plpr.db PLPR_MODEL_DIR=/app/model/onnx
WORKDIR /app
COPY pyproject.toml README.md ./
COPY plpr ./plpr
# psycopg: lets PLPR_DATABASE_URL point at the postgres profile without rebuilding
RUN pip install --no-cache-dir ".[server]" "psycopg[binary]>=3.2" \
 && useradd --system --uid 10001 --home-dir /app plpr \
 && mkdir -p /data && chown plpr /data
COPY server ./server
COPY --from=export /src/model/onnx ./model/onnx
USER plpr
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
