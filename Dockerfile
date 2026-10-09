# --- backend ---
FROM python:3.11-slim AS backend
WORKDIR /app
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY backend/ .
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- frontend build ---
FROM node:20-alpine AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# --- serve dashboard ---
FROM node:20-alpine AS dashboard
WORKDIR /app
COPY --from=frontend-build /app/dist ./dist
RUN npm install -g serve@14
EXPOSE 5173
CMD ["serve", "-s", "dist", "-l", "5173"]
