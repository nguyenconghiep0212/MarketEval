# src/intelligence/sentiment.py
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch.nn.functional as F
from typing import List

MODEL_NAME = "uitnlp/visobert"  # State-of-the-art Vietnamese social/text encoder
# MODEL_NAME = "vinai/phobert-base-v2" # Can swap with fine-tuned ViFiNBERT

class SentimentEngine:
    def __init__(self, model_name: str = MODEL_NAME):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"  📊 Loading Sentiment Model '{model_name}' on device: {self.device}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name, num_labels=3 # [Negative, Neutral, Positive]
        ).to(self.device)
        self.model.eval()

    def analyze_text(self, text: str) -> float:
        """
        Analyzes string input and returns a float score bounded in [-1.0, +1.0].
          -1.0 = Highly Bearish / Negative
           0.0 = Neutral
          +1.0 = Highly Bullish / Positive
        """
        if not text or not text.strip():
            return 0.0

        inputs = self.tokenizer(
            text, 
            truncation=True, 
            max_length=256, 
            return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = F.softmax(outputs.logits, dim=-1).squeeze().cpu().numpy()

        # Assuming index order: [0: Negative, 1: Neutral, 2: Positive]
        prob_neg, prob_neu, prob_pos = probs[0], probs[1], probs[2]
        
        # Bounded score computation
        score = float(prob_pos - prob_neg)
        return round(score, 4)

    def analyze_texts_batch(self, texts: List[str], batch_size: int = 16) -> List[float]:
        """
        Analyzes multiple texts at once using batch processing.
        
        ✅ Benefits:
           - 5-10x faster than sequential analyze_text() calls
           - Uses GPU parallelization efficiently
           - Processes multiple articles simultaneously
        
        Args:
            texts: List of texts to analyze
            batch_size: Number of texts to process in parallel (adjust based on GPU memory)
        
        Returns:
            List of scores matching input order, same scale as analyze_text()
        
        Example:
            scores = sentiment_engine.analyze_texts_batch(
                ["Article 1 text...", "Article 2 text..."],
                batch_size=32
            )
        """
        if not texts:
            return []
        
        scores = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            
            # Filter out empty texts
            non_empty = [(idx, text) for idx, text in enumerate(batch_texts) if text and text.strip()]
            
            if not non_empty:
                scores.extend([0.0] * len(batch_texts))
                continue
            
            # Extract indices and texts for tokenization
            indices, clean_texts = zip(*non_empty)
            
            # Tokenize batch
            inputs = self.tokenizer(
                list(clean_texts),
                truncation=True,
                max_length=256,
                return_tensors="pt",
                padding=True,
            ).to(self.device)
            
            # Batch inference
            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = F.softmax(outputs.logits, dim=-1).cpu().numpy()
            
            # Compute scores for non-empty texts
            batch_scores = {}
            for j, probs_row in enumerate(probs):
                prob_neg, prob_neu, prob_pos = probs_row[0], probs_row[1], probs_row[2]
                score = float(prob_pos - prob_neg)
                batch_scores[indices[j]] = round(score, 4)
            
            # Reconstruct in original order, filling empty texts with 0.0
            for idx, text in enumerate(batch_texts):
                scores.append(batch_scores.get(idx, 0.0))
        
        return scores