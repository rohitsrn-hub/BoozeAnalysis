import sys
import os
from pathlib import Path

# Add the backend directory to sys.path
backend_dir = Path(__file__).parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

# Import the FastAPI app from the backend server
from backend.server import app

# This file acts as a proxy for Render if it's configured to run 'gunicorn server:app'
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
