# Build Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Build Backend
FROM python:3.11-slim
WORKDIR /app

# Install dependencies
COPY backend/requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt

# Copy backend
COPY backend/ ./backend/
COPY data/ ./data/

# Copy frontend build
COPY --from=frontend-builder /app/dist /app/frontend/dist

ENV PYTHONPATH=/app/backend
ENV APP_ENV=production
ENV VITE_API_BASE_URL=http://localhost:8000
ENV CORS_ALLOWED_ORIGINS=http://localhost:8000,http://localhost:3000

# Expose backend port
EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
