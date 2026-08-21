# src/intelligence/sentiment.py
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch.nn.functional as F
from typing import List
import warnings

# Suppress model architecture mismatch warnings
warnings.filterwarnings('ignore', category=UserWarning)

# Use a reliable Vietnamese sentiment model that works out-of-the-box
# Options ranked by compatibility:
# 1. "nlptown/bert-base-multilingual-uncased-sentiment" (multilingual, 5-label)
# 2. "distilbert-base-uncased-finetuned-sst-2-english" (2-label fallback)
# 3. "vinai/phobert-base-v2" (requires custom fine-tuning)
MODEL_NAME = "nlptown/bert-base-multilingual-uncased-sentiment"

class SentimentEngine:
    def __init__(self, model_name: str = MODEL_NAME):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"  📊 Loading Sentiment Model '{model_name}' on device: {self.device}")
        
        try:
            # Load tokenizer with legacy_behavior to avoid dict conversion issues
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                use_fast=True,  # Use fast tokenizer by default
                trust_remote_code=False
            )
        except Exception as e:
            print(f"  ⚠️  Fast tokenizer failed, falling back to slow tokenizer: {e}")
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                use_fast=False,
                trust_remote_code=False
            )
        
        # Load model with warning suppression
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.model = AutoModelForSequenceClassification.from_pretrained(
                model_name,
                trust_remote_code=False
            )
        
        self.model.to(self.device)
        self.model.eval()
        
        # Detect number of labels dynamically
        self.num_labels = self.model.config.num_labels
        print(f"  ℹ️  Model has {self.num_labels} sentiment labels")

    def analyze_text(self, text: str) -> float:
        """
        Analyzes string input and returns a float score bounded in [-1.0, +1.0].
          -1.0 = Highly Bearish / Negative
           0.0 = Neutral
          +1.0 = Highly Bullish / Positive
        
        Handles variable label counts dynamically.
        """
        if not text or not text.strip():
            return 0.0

        try:
            inputs = self.tokenizer(
                text, 
                truncation=True, 
                max_length=512, 
                return_tensors="pt"
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = F.softmax(outputs.logits, dim=-1).squeeze().cpu().numpy()
            
            # Handle 1D array (single sample)
            if probs.ndim == 1:
                probs = probs.reshape(1, -1)[0]
            
            score = self._compute_score(probs)
            return round(score, 4)
        
        except Exception as e:
            print(f"  ❌ Error analyzing text: {e}")
            return 0.0

    def _compute_score(self, probs) -> float:
        """
        Converts probability distribution to sentiment score [-1.0, +1.0].
        Handles 2, 3, 5, or variable label models dynamically.
        """
        if self.num_labels == 2:
            # Binary: [Negative, Positive]
            return float(probs[1] - probs[0])
        
        elif self.num_labels == 3:
            # Ternary: [Negative, Neutral, Positive]
            return float(probs[2] - probs[0])
        
        elif self.num_labels == 5:
            # 5-label: typically [1-star, 2-star, 3-star, 4-star, 5-star]
            # Map to [-1, -0.5, 0, 0.5, 1]
            if len(probs) >= 5:
                # Weighted average: negative labels weighted -1 to 0, positive 0 to +1
                score = (
                    probs[0] * (-1.0) +
                    probs[1] * (-0.5) +
                    probs[2] * (0.0) +
                    probs[3] * (0.5) +
                    probs[4] * (1.0)
                )
                return float(score)
        
        # Fallback: assume first is negative, last is positive
        return float(probs[-1] - probs[0])

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
            
            try:
                # Extract indices and texts for tokenization
                indices, clean_texts = zip(*non_empty)
                
                # Tokenize batch
                inputs = self.tokenizer(
                    list(clean_texts),
                    truncation=True,
                    max_length=512,
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
                    score = self._compute_score(probs_row)
                    batch_scores[indices[j]] = round(score, 4)
                
                # Reconstruct in original order, filling empty texts with 0.0
                for idx, text in enumerate(batch_texts):
                    scores.append(batch_scores.get(idx, 0.0))
            
            except Exception as e:
                print(f"  ❌ Error in batch processing: {e}")
                scores.extend([0.0] * len(batch_texts))
        
        return scores
