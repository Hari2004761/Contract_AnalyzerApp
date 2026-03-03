from datasets import load_dataset
import pandas as pd
from huggingface_hub import login
import os
labels = {
    0: "Limitation of Liability",
    1: "Unilateral Termination",
    2: "Unilateral Change",
    3: "Content Removal",
    4: "Contract by Using",
    5: "Choice of Law",
    6: "Jurisdiction",
    7: "Arbitration"
}
login(os.getenv("HUGGING_FACE"))

def load_data():
    dataset = load_dataset("coastalcph/lex_glue", "unfair_tos")
    print("Download Complete!\n")

    print(f"Dataset Structure:{dataset}")

    index = 50
    sample = dataset['train'][index]
    print(f"\n--- SAMPLE ROW {index} ---")
    print(f"TEXT: {sample['text']}")
    raw_labels = sample['labels']
    human_readable_labels = []
    for i in raw_labels:
        meaning = labels[i]
        human_readable_labels.append(meaning)

    print(f"Raw numbers for the model:{raw_labels}")
    print(f"Meaning:{human_readable_labels}")


def scan_multiple_clauses():
    dataset = load_dataset("coastalcph/lex_glue", "unfair_tos")

    start = 10
    end = 50

    print(f"Scanning rows {start} to {end}\n")

    for i in range(start, end):

        sample = dataset['train'][i]
        rawlabels = sample['labels']

        if len(rawlabels) == 0:
            continue
        human_readable_labels = []

        for j in rawlabels:
            meaning = labels[j]
            human_readable_labels.append(meaning)

        print(f"Row{i}:")
        print(f"Text:{sample['text']}")
        print(f"⚠️ FOUND: {human_readable_labels}")
        print("-" * 50)


if __name__ == '__main__':
    load_data()
