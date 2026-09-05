# =============================================================================
# STAGE 1: Build the React/Vite Frontend
# =============================================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# =============================================================================
# STAGE 2: Python 3.11 Runtime + FFmpeg Multimedia Engine
# =============================================================================
FROM python:3.11-slim-bookworm AS runner
WORKDIR /app

# Install system dependencies: FFmpeg (audio extraction & chunking), curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application source files
COPY app.py document_engine.py template_engine.py skills_engine.py \
     ai_providers.py media_processor.py gdrive_service.py ./
COPY templates_store ./templates_store
COPY skills_store ./skills_store
COPY temp_outputs ./temp_outputs
COPY static ./static

# Copy official template file if present
COPY ["EASD Meeting minutes - Template-DDMonthYY.docx", "./"]

# Copy compiled frontend from Stage 1 into frontend/dist
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Configure runtime environment
ENV HOST=0.0.0.0
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/api/document_types || exit 1

CMD ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
