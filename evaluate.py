import torch
import numpy as np
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from datasets import load_dataset
from sklearn.metrics import (
    f1_score,
    precision_score,
    recall_score,
    accuracy_score,
    classification_report,
)

MODEL_PATH = "./contract_analysismodel"
NUM_LABELS = 8
THRESHOLD = 0.5
BATCH_SIZE = 16

label_names = [
    "Limitation of Liability",
    "Unilateral Termination",
    "Unilateral Change",
    "Content Removal",
    "Contract by Using",
    "Choice of Law",
    "Jurisdiction",
    "Arbitration",
]

print(f"Loading model from {MODEL_PATH} ...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
model.eval()

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
print(f"Model loaded on {device}.\n")

print("Loading LexGLUE (unfair_tos) test split ...")
dataset = load_dataset("coastalcph/lex_glue", "unfair_tos", split="test")
print(f"Test set size: {len(dataset)} examples.\n")

all_logits = []

print("Running inference ...")
for start in range(0, len(dataset), BATCH_SIZE):
    batch = dataset[start: start + BATCH_SIZE]
    texts = batch["text"]

    inputs = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="pt",
    ).to(device)

    with torch.no_grad():
        outputs = model(**inputs)

    all_logits.append(outputs.logits.cpu())

    if (start // BATCH_SIZE) % 10 == 0:
        print(f"  Processed {min(start + BATCH_SIZE, len(dataset))}/{len(dataset)}")

logits = torch.cat(all_logits, dim=0)
probs = torch.sigmoid(logits).numpy()
y_pred = (probs >= THRESHOLD).astype(int)

y_true = np.zeros((len(dataset), NUM_LABELS), dtype=int)
for i, label_indices in enumerate(dataset["labels"]):
    for idx in label_indices:
        y_true[i][idx] = 1

weighted_f1 = f1_score(y_true, y_pred, average="weighted", zero_division=0)
weighted_precision = precision_score(y_true, y_pred, average="weighted", zero_division=0)
weighted_recall = recall_score(y_true, y_pred, average="weighted", zero_division=0)
exact_accuracy = accuracy_score(y_true, y_pred)

print("\n" + "=" * 60)
print("EVALUATION RESULTS")
print("=" * 60)
print(f"Weighted F1 Score  : {weighted_f1:.4f}")
print(f"Weighted Precision : {weighted_precision:.4f}")
print(f"Weighted Recall    : {weighted_recall:.4f}")
print(f"Exact Match Accuracy: {exact_accuracy:.4f}")
print("=" * 60)

print("\nPer-class Classification Report:")
print(
    classification_report(
        y_true,
        y_pred,
        target_names=label_names,
        zero_division=0,
    )
)
