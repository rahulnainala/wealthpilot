"""QLoRA fine-tune of WealthPilot's custom model on the 3070 (8GB VRAM).

Reads train.jsonl (from export.sh), tunes Qwen2.5-7B-Instruct with 4-bit
QLoRA via unsloth, and exports a GGUF ready for `ollama create wealthpilot
-f Modelfile`. Expect ~1-2h for ~1k pairs on an RTX 3070.

Run:  pip install unsloth  &&  python train_lora.py
"""

from unsloth import FastLanguageModel
import json

MAX_SEQ = 2048
BASE = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit"

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=BASE,
    max_seq_length=MAX_SEQ,
    load_in_4bit=True,  # fits the 3070's 8GB
)
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    lora_alpha=16,
    lora_dropout=0.0,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
)

with open("train.jsonl", encoding="utf-8") as f:
    rows = [json.loads(line) for line in f if line.strip()]
print(f"training on {len(rows)} conversations")

texts = [
    tokenizer.apply_chat_template(r["messages"], tokenize=False, add_generation_prompt=False)
    for r in rows
]

from datasets import Dataset
from trl import SFTConfig, SFTTrainer

dataset = Dataset.from_dict({"text": texts})
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    args=SFTConfig(
        dataset_text_field="text",
        max_seq_length=MAX_SEQ,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        num_train_epochs=2,
        learning_rate=2e-4,
        logging_steps=10,
        output_dir="out-checkpoints",
        optim="adamw_8bit",
        seed=42,
    ),
)
trainer.train()

# Export GGUF for ollama (q4_k_m balances quality and the 3070's memory).
model.save_pretrained_gguf(
    "out-gguf", tokenizer, quantization_method="q4_k_m"
)

# unsloth writes the quantized file into a SIBLING dir it names itself
# (out-gguf_gguf/Qwen2.5-7B-Instruct.Q4_K_M.gguf), but Modelfile's FROM expects
# out-gguf/wealthpilot.gguf. Without this, `ollama create` sees a missing path
# and 400s with "invalid model name" — so move the q4_k_m artifact into place.
import glob
import os
import shutil

os.makedirs("out-gguf", exist_ok=True)
target = os.path.join("out-gguf", "wealthpilot.gguf")
found = glob.glob("out-gguf*/**/*.gguf", recursive=True)
q4 = [g for g in found if "q4_k_m" in g.lower()]
src = next(iter(q4 or found), None)
if src and os.path.abspath(src) != os.path.abspath(target):
    shutil.move(src, target)
    print(f"moved {src} -> {target}")
print("done — now: ollama create wealthpilot -f Modelfile")
