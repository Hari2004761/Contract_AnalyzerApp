from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import torch.nn.functional as F

model_path = "./contract_analysismodel"

try:
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    print("Model loaded successfully!")
except Exception as e:
    print(f"Error: {e}")
    exit()

id2label = {
    0: "Limitation of Liability",
    1: "Unilateral Termination",
    2: "Unilateral Change",
    3: "Content Removal",
    4: "Contract by Using",
    5: "Choice of Law",
    6: "Jurisdiction",
    7: "Arbitration"
}


def predict_unfairness(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs)

    probs = F.softmax(outputs.logits, dim=-1)
    pred_idx = torch.argmax(probs).item()
    confidence = probs[0][pred_idx].item()

    if confidence<0.50:
        return "Fair Contract",confidence

    return id2label[pred_idx], confidence


test_text = "To the fullest extent permitted by law, we shall not be liable for any indirect, incidental, or consequential damages, including loss of profits"
text2="You agree that any legal action or proceeding shall be brought exclusively in the federal or state courts located in Santa Clara County, California."
text3="Any dispute arising from these terms shall be resolved exclusively through binding arbitration, and you waive your right to a trial by jury."
fair_text="You may cancel your subscription at any time by contacting customer support."
label, score = predict_unfairness(text3)


print("-" * 30)
print(f"🔴 RESULT: {label}")
print(f"📊 CONFIDENCE: {score:.1%}")
print("-" * 30)
