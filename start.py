#!/usr/bin/env python3
"""
Cognitive Canvas — Single Full-Stack Bundle Launcher.
Automatically verifies/builds the React frontend and launches the unified backend.
"""

import os
import sys
import subprocess
from pathlib import Path

root_dir = Path(__file__).resolve().parent
frontend_dir = root_dir / "frontend"
dist_dir = frontend_dir / "dist"


def ensure_frontend_built():
    if not (dist_dir / "index.html").exists():
        print("📦 Building React Frontend bundle (npm run build)...")
        subprocess.run(["npm", "run", "build"], cwd=str(frontend_dir), check=True)
    else:
        print(f"✅ Found existing frontend bundle in: {dist_dir}")


def main():
    ensure_frontend_built()

    # Add project root to sys.path
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")

    print(f"\n🚀 Cognitive Canvas Unified App is running!")
    print(f"👉 Access the complete application at: http://localhost:{port}\n")

    import uvicorn
    from cognitive_canvas.server import app
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
