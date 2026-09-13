"""Start the portfolio-sim web platform.

    python scripts/serve.py               # http://127.0.0.1:8000
    python scripts/serve.py --port 9000 --reload
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the portfolio-sim platform.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="Auto-reload on code changes (development).")
    args = parser.parse_args()

    import uvicorn

    print(f"portfolio-sim platform -> http://{args.host}:{args.port}")
    uvicorn.run("web.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
