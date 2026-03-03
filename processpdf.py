import os.path
import re
import fitz
import pdfplumber
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import torch.nn.functional as F

model_path = "./contract_analysismodel"
print(f"⏳ Loading model from {model_path}...")

try:
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    print("✅ Model loaded successfully!")
except Exception as e:
    print(f" Error loading model: {e}")
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


# 2. HELPER FUNCTION: Analyze ONE small piece of text
def analyze_chunk(text):
    # Prepare the text for the model
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)

    with torch.no_grad():
        outputs = model(**inputs)

    # Calculate scores
    probs = F.softmax(outputs.logits, dim=-1)
    pred_idx = torch.argmax(probs).item()
    confidence = probs[0][pred_idx].item()

    if confidence < 0.20:
        return None, 0.0

    return id2label[pred_idx], confidence


def find_sentence(chunk_text, target_label):
    sentences = re.split(r'(?<=[.!?]) +', chunk_text)
    best_sentence = chunk_text
    highest_score = 0.0

    for sentence in sentences:
        if len(sentence) < 10:
            continue
        label, score = analyze_chunk(sentence)

        if label == target_label and score > highest_score:
            highest_score = score
            best_sentence = sentence
    return best_sentence


def highlight_risks(pdf_path, risks_found,ouput_pdfpath):

    doc=fitz.open(pdf_path)

    for page in doc:
        for risk in risks_found:
            text_instances=page.search_for(risk['text_snippet'])

            for instance in text_instances:
                highlight = page.add_highlight_annot(instance)
                highlight.set_colors(stroke=(1, 1, 0))  # RGB for Yellow
                highlight.update()

    doc.save(ouput_pdfpath)
    doc.close()
    print(f"Saved highlighted pdf to:{ouput_pdfpath}")

def process_pdf(file_path,ouput_pdf_path="highlighted_contract.pdf"):
    full_text = ""
    try:

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:

                text = page.extract_text(x_tolerance=2)
                if text:
                    full_text += text + " "

    except Exception as e:
        print(f"Error while reading file: {e}")
        return

    print(f"Extracted {len(full_text)} charecters.")
    print("\n" + "=" * 40)
    print("🔍 RAW TEXT DUMP (First 500 chars):")
    print("=" * 40)
    print(full_text[:5000])
    print("=" * 40 + "\n")

    if len(full_text) == 0:
        print("Warning: No text found in pdf, is it a scanned image file?")
        return

    words = full_text.split()
    current_position = 0
    chunk_size = 300
    overlap = 50

    risks_found = []

    while current_position < len(words):

        chunk_words = []

        for j in range(chunk_size):
            target_index = current_position + j
            if target_index < len(words):
                word_to_add = words[target_index]
                chunk_words.append(word_to_add)
            else:
                break

        chunk_text = " ".join(chunk_words)

        label, score = analyze_chunk(chunk_text)

        if label and score > 0.40:

            risky_sentence = find_sentence(chunk_text, label)

            is_duplicate = False
            for r in risks_found:
                if risky_sentence in r['text_snippet']:
                    is_duplicate = True
                    break

            if not is_duplicate:
                risks_found.append({
                    "type": label,
                    "confidence": score,
                    "text_snippet": risky_sentence
                })

        current_position += (chunk_size - overlap)

    if risks_found:
        highlight_risks(file_path,risks_found,ouput_pdf_path)

    # Results
    return risks_found


if __name__ == '__main__':

    pdf_filename = "American_Express_Cash_Magnet_Card_Cardmember_Agreement.pdf-255462.pdf"

    if os.path.exists(pdf_filename):
        process_pdf(pdf_filename)
    else:
        print("File not found")
