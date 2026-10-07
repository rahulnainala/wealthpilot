#!/bin/sh
# Export Pilot's chat pairs as chat-tuning JSONL. Usage: ./export.sh host:port
set -e
HOST="${1:-localhost:8000}"
curl -s "http://${HOST}/api/ai/training-data" | python3 -c '
import json, sys
rows = json.load(sys.stdin)
for r in rows:
    print(json.dumps({"messages": r["messages"]}, ensure_ascii=False))
' > train.jsonl
echo "wrote $(wc -l < train.jsonl) pairs to train.jsonl"
