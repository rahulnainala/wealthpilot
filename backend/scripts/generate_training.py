"""CLI entry point for the training-pair generator.

The actual logic lives in ``app.services.ai.train_generator`` so it can also
be started from the API as a background task (the "Push to 3070" button on
the AI panel, via ``/api/ai/train/start``). This script is the original
detached-container workflow, kept for when you'd rather run it from a shell:

    docker compose exec -d backend python scripts/generate_training.py --target 1000

Watch progress on the AI panel or the Learn tab's Custom Model panel.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

sys.path.insert(0, "/app")

from app.services.ai.train_generator import run_generation  # noqa: E402

if __name__ == "__main__":
    # Root logging config belongs at the entry point, not in the service
    # module — the API process (uvicorn) configures its own, and doing it
    # there too would fight over the root logger's handlers.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=1000)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--model", default=None, help="generator-only model override, e.g. qwen2.5:7b")
    args = ap.parse_args()
    asyncio.run(run_generation(args.target, args.concurrency, args.model))
