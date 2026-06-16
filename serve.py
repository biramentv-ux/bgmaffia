"""Production entrypoint. Starts the background scheduler once, then serves
the app with Waitress (a pure-Python WSGI server, no C deps).

    python serve.py            # serves on 0.0.0.0:5000
    PORT=8080 python serve.py  # custom port

Set SECRET_KEY in the environment for a stable session secret across restarts.
"""
import os
from waitress import serve

from app import app, start_scheduler

if __name__ == "__main__":
    start_scheduler()
    port = int(os.environ.get("PORT", "5000"))
    print(f"Concrete Empire serving on http://0.0.0.0:{port}")
    serve(app, host="0.0.0.0", port=port, threads=8)
