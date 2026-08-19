# src/intelligence/embeddings.py
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel
from typing import List

MODEL_NAME = "bkai-foundation-models/vietnamese-bi-encoder"

class EmbeddingEngine:
    def __init__(self, model_name: str = MODEL_NAME):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"  🧠 Loading Embedding Model '{model_name}' on device: {self.device}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(self.device)
        self.model.eval()

    def _mean_pooling(self, model_output, attention_mask):
        """Mean Pooling - Take attention mask into account for correct averaging."""
        token_embeddings = model_output[0] # First element of model_output contains all token embeddings
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

    def generate_embeddings(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Generates 768-dimensional normalized vector embeddings using safe batching."""
        if not texts:
            return []

        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            
            encoded_input = self.tokenizer(
                batch_texts, 
                padding=True, 
                truncation=True, 
                max_length=256, 
                return_tensors="pt"
            ).to(self.device)

            with torch.no_grad():
                model_output = self.model(**encoded_input)

            sentence_embeddings = self._mean_pooling(model_output, encoded_input["attention_mask"])
            sentence_embeddings = F.normalize(sentence_embeddings, p=2, dim=1)
            
            all_embeddings.extend(sentence_embeddings.cpu().tolist())
            
        return all_embeddings