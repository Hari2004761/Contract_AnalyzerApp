import os
from datasets import load_dataset
from torch import nn
from transformers import AutoTokenizer, AutoModelForSequenceClassification, TrainingArguments, Trainer
import numpy as np
from huggingface_hub import login
import torch

dataset = load_dataset("coastalcph/lex_glue", "unfair_tos")
tokenizer = AutoTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")
login(os.getenv("HUGGING_FACE"))

def tokenize_function(examples):
    return tokenizer(examples["text"], padding="max_length", truncation=True)


tokenize_dataset = dataset.map(tokenize_function, batched=True)


def multi_label_collator(batch):
    input_ids = torch.tensor([item['input_ids'] for item in batch])
    attention_mask = torch.tensor([item['attention_mask'] for item in batch])

    # Create a vector of zeros [0, 0, 0, 0, 0, 0, 0, 0] for each sentence
    labels = torch.zeros(len(batch), 8)
    for i, item in enumerate(batch):
        # If the dataset has a label like [4], set the 4th position to 1.0
        for label_idx in item['labels']:
            labels[i][label_idx] = 1.0

    return {
        'input_ids': input_ids,
        'attention_mask': attention_mask,
        'labels': labels
    }


weights = torch.tensor([1.0, 3.0, 3.0, 3.0, 3.0, 2.0, 4.0, 8.0])


class WeightedTrainer(Trainer):
    def __init__(self, class_weights, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

        def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):

            labels = inputs.get("labels")
            outputs = model(**inputs)
            logits = outputs.get("logits")

            loss_factor = nn.BCEwithLogitsLoss(pos_weight=weights)
            loss = loss_factor(logits, labels)

            if return_outputs:
                return (loss, outputs)
            else:
                return loss


model = AutoModelForSequenceClassification.from_pretrained("nlpaueb/legal-bert-base-uncased", num_labels=8)

training_arguments = TrainingArguments(
    output_dir="legal_bert_finetuned",
    eval_strategy="epoch",
    save_strategy="epoch",
    learning_rate=2e-5,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    fp16=True,
    num_train_epochs=3,
    weight_decay=0.01,
    load_best_model_at_end=True,
    metric_for_best_model="loss"
)

trainer = WeightedTrainer(
    class_weights=weights,
    model=model,
    args=training_arguments,
    train_dataset=tokenize_dataset["train"].shuffle(seed=42),
    eval_dataset=tokenize_dataset["validation"],
    data_collator=multi_label_collator,
)

trainer.train()

print("Saving the model\n")
model.save_pretrained("./contract_analysismodel")
tokenizer.save_pretrained("./contract_analysismodel")
