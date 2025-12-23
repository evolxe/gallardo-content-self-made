#!/usr/bin/env python3
"""
Run the FastAPI video generation service.

Usage:
    python run_api.py
    python run_api.py --host 0.0.0.0 --port 8000
"""

import argparse
import os
import uvicorn
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from api.main import app


def main():
    """Run the FastAPI application."""
    parser = argparse.ArgumentParser(description="Run FastAPI Video Generation Service")
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", 8000)),
        help="Port to bind to (default: 8000 or PORT env var)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Starting FastAPI Video Generation Service")
    print("=" * 80)
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"Reload: {args.reload}")
    print("=" * 80)
    print(f"API Documentation: http://{args.host}:{args.port}/docs")
    print(f"Health Check: http://{args.host}:{args.port}/api/v1/health")
    print("=" * 80)
    
    uvicorn.run(
        "api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()

