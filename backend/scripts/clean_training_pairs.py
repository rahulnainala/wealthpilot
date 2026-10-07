"""One-time data hygiene: normalize the FOLLOW-UPS trailer in stored pairs.

The fine-tuned model learned a messy FOLLOW-UPS format because the training
pairs themselves carried the literal template scaffold. normalize_followups()
fixes replies at inference, but the *next* retrain would relearn the artifact
unless the source data is cleaned. This rewrites each chat_exchanges.reply
through the same normalizer so future exports (and models) are clean by
construction. Idempotent and safe to re-run.

    # preview what would change, no writes:
    docker compose exec backend python scripts/clean_training_pairs.py --dry-run
    # apply:
    docker compose exec backend python scripts/clean_training_pairs.py
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys

sys.path.insert(0, "/app")

# A reply that STILL matches this after normalization is genuinely corrupt (scaffold
# mid-answer, no clean structure) — drop it rather than ship bad training data.
_LEAK_RE = re.compile(
    r"q1\s*\|\s*q2|three short question|naturally ask|ask next|\n---", re.IGNORECASE
)


def _is_corrupt(cleaned: str) -> bool:
    """True when the reply can't be salvaged to a single clean trailer."""
    if _LEAK_RE.search(cleaned):
        return True
    # A body that itself discusses the marker leaves a stray second "FOLLOW-UPS:".
    if len(re.findall(r"FOLLOW-?UPS?:", cleaned, re.IGNORECASE)) > 1:
        return True
    if "FOLLOW-UPS:" in cleaned:
        trailer = cleaned.split("FOLLOW-UPS:", 1)[1]
        if any(not item.strip() for item in trailer.split("|")):
            return True
    return False


async def main(dry_run: bool) -> None:
    from sqlalchemy import select

    from app.db import get_sessionmaker
    from app.models.chat_log import ChatExchange
    from app.services.ai.providers import normalize_followups

    sm = get_sessionmaker()
    total = changed = dropped = 0
    samples: list[tuple[int, str, str]] = []
    dropped_ids: list[int] = []

    async with sm() as db:
        rows = (await db.execute(select(ChatExchange))).scalars().all()
        total = len(rows)
        for row in rows:
            original = row.reply or ""
            cleaned = original
            for _ in range(5):  # iterate to a fixpoint (defensive; nf is idempotent)
                nxt = normalize_followups(cleaned)
                if nxt == cleaned:
                    break
                cleaned = nxt
            if _is_corrupt(cleaned):
                dropped_ids.append(row.id)
                dropped += 1
                if not dry_run:
                    await db.delete(row)
                continue
            if cleaned != original:
                if len(samples) < 3:
                    samples.append((row.id, original, cleaned))
                if not dry_run:
                    row.reply = cleaned
                changed += 1
        if not dry_run:
            await db.commit()

    verb = "would change" if dry_run else "cleaned"
    dverb = "would drop" if dry_run else "dropped"
    kept = total - dropped
    print(
        f"pairs total={total}  {verb}={changed}  {dverb}(corrupt)={dropped}  "
        f"already-clean={kept - changed}  remaining={kept}"
    )
    if dropped_ids:
        print(f"dropped ids: {dropped_ids}")
    for pid, before, after in samples:
        print(f"\n--- id={pid} ---")
        print(f"BEFORE: {before[-160:]!r}")
        print(f"AFTER:  {after[-160:]!r}")
    if dry_run:
        print("\n(dry run — no writes. Re-run without --dry-run to apply.)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="preview changes without writing")
    args = ap.parse_args()
    asyncio.run(main(args.dry_run))
