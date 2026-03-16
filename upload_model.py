from huggingface_hub import HfApi, login
from dotenv import load_dotenv
import os

load_dotenv()
login(token=os.getenv("HUGGING_FACE_2"))

api = HfApi()

api.create_repo(repo_id="Harinarayanan2994/clausify-contract-analyzer", exist_ok=True)

api.upload_folder(
    folder_path="./contract_analysismodel",
    repo_id="Harinarayanan2994/clausify-contract-analyzer",
    repo_type="model"
)

print("Model uploaded successfully!")