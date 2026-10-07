# WealthPilot custom model — fine-tuning kit (runs on the 3070)

Turns your accumulated Pilot conversations into a LoRA-tuned local model
named `wealthpilot`. The app auto-detects it (AI tab → Custom Model) and
you switch by setting `OLLAMA_MODEL=wealthpilot` in the root `.env`.

**When**: wait until the AI tab shows ~1000+ training pairs. Under that,
RAG grounding already carries the quality; fine-tuning adds voice and
domain shorthand, not facts.

**Base model**: Qwen2.5-7B-Instruct — deliberately NOT deepseek-r1:14b:
a 7B QLoRA fits the 3070's 8GB VRAM (4-bit, batch 1–2), trains in ~1–2h,
and Qwen is a stronger instruction-follower for tool-style outputs. Your
day-to-day chat model stays whatever OLLAMA_MODEL says.

## Steps (on the 3070, PowerShell/WSL)

1. Export data (from any machine on the LAN):
   `./export.sh 192.168.1.x:8000` → writes `train.jsonl`
2. Install once: `pip install unsloth` (needs CUDA torch)
3. Train: `python train_lora.py` (reads train.jsonl, writes ./out-gguf)
4. Create the ollama model:
   `ollama create wealthpilot -f Modelfile`
5. Point the app at it: root `.env` → `OLLAMA_MODEL=wealthpilot`,
   then `docker compose up -d backend`.

Re-run any time; each run retrains from the full, larger dataset.

## RAG-grounded training (Phase 25)

`/api/ai/training-data` now prefixes every example with the grounding **system
prompt** (`?grounded=true`, the default), so each pair is
`[system, user, assistant]`. The fine-tune therefore learns to answer *only from
provided numbers, cite sources, and keep a clean FOLLOW-UPS trailer* — a
grounded model rather than a free-associating one. `export.sh` picks this up
automatically. Pass `?grounded=false` only if you want the bare Q&A form.

The dataset is also kept scaffold-clean at the source
(`scripts/clean_training_pairs.py`), and model quality is tracked across retrains
on the Learn tab (Model Quality card → `POST /api/ai/run-eval`).
