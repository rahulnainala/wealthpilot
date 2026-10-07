"""Run ONCE on the 3070 and forget: waits for the dataset, then trains.

Polls the WealthPilot backend until the training-pair target is reached,
exports the dataset, runs the QLoRA fine-tune (train_lora.py), and creates
the `wealthpilot` model in Ollama. Fully unattended — start it before bed.

    python auto_train.py --backend http://<MAC-LAN-IP>:8000

Prereqs on this machine (one time):
    pip install unsloth requests
    (ollama already installed and serving)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request

TARGET = 1000
POLL_S = 300  # 5 minutes between checks


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.load(r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="http://localhost:8000")
    ap.add_argument("--target", type=int, default=TARGET)
    args = ap.parse_args()
    base = args.backend.rstrip("/")

    print(f"[auto-train] watching {base} for {args.target} pairs …")
    while True:
        try:
            status = get_json(f"{base}/api/ai/status")
            pairs = status["training_pairs"]
            print(f"[auto-train] {time.strftime('%H:%M')} pairs={pairs}", flush=True)
            if pairs >= args.target:
                break
        except Exception as exc:  # noqa: BLE001 — backend asleep? keep waiting
            print(f"[auto-train] backend unreachable ({exc}) — retrying", flush=True)
        time.sleep(POLL_S)

    print("[auto-train] target reached — exporting dataset")
    rows = get_json(f"{base}/api/ai/training-data")
    with open("train.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"messages": r["messages"]}, ensure_ascii=False) + "\n")
    print(f"[auto-train] wrote {len(rows)} pairs to train.jsonl")

    print("[auto-train] starting LoRA fine-tune (this saturates the GPU ~1-2h)")
    subprocess.run([sys.executable, "train_lora.py"], check=True)

    print("[auto-train] creating ollama model `wealthpilot`")
    subprocess.run(["ollama", "create", "wealthpilot", "-f", "Modelfile"], check=True)

    print(
        "\n[auto-train] DONE. Final step (on the Mac): set OLLAMA_MODEL=wealthpilot "
        "in the root .env and run `docker compose up -d backend`. The Learn tab's "
        "MODEL node turns green on its own."
    )


if __name__ == "__main__":
    main()
