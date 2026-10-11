"""Vercel serverless entry point — wraps the FastAPI app for ASGI."""
import sys
from pathlib import Path

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402 — path setup must precede import
