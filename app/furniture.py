import json
import torch
import re
import sys
import base64
import io
import os
import logging

from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict
from PIL import Image

from sentence_transformers import SentenceTransformer, util
from openai import OpenAI

from database import DatabaseManager


CACHE_DIR = Path(".cache")
EMBEDDINGS_CACHE = CACHE_DIR / "embeddings_cache_sql.json"

DEVICE = "cpu"
if torch.cuda.is_available():
    DEVICE = "cuda"
elif torch.backends.mps.is_available():
    DEVICE = "mps"

OPENAI_CLIENT = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
SENTENCE_MODEL = SentenceTransformer("all-MiniLM-L6-v2", device=DEVICE)


class FurnitureFinder:
    def __init__(
        self, 
        database_url: str = None,
        image: Image = None,
        use_cache: bool = True
    ):
        self.database_url = database_url
        self.use_cache = use_cache
        self.image = image
        self.furniture_items: List[Dict] = []
        self.embeddings = None
        self.embedding_map: Dict[int, torch.Tensor] = {}
        
        self.db = DatabaseManager(database_url)
        
        CACHE_DIR.mkdir(exist_ok=True)
        self._load_furniture_data()
        self._load_or_compute_embeddings()
    
    def _load_furniture_data(self):
        """Load furniture items from SQL database"""
        try:
            items = self.db.get_furniture_items(has_description=True)
            self.furniture_items = [item.to_dict() for item in items]
            
            if not self.furniture_items:
                logging.warning("No furniture items found in database")
                
        except Exception as e:
            logging.exception(f"Database error: {e}")
            sys.exit(1)
    
    def _load_or_compute_embeddings(self):
        """Load cached embeddings or compute new ones from database"""
        cache_valid = False
        
        if self.use_cache and EMBEDDINGS_CACHE.exists():
            try:
                with open(EMBEDDINGS_CACHE, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                # Validate cache matches current data
                if len(cache_data) == len(self.furniture_items):
                    cache_ids = {item['id'] for item in cache_data}
                    current_ids = {item['id'] for item in self.furniture_items}
                    
                    if cache_ids == current_ids and all('embedding' in item for item in cache_data):
                        # Build a mapping from id to raw embedding from the cache
                        id_to_embedding = {
                            item['id']: item['embedding'] for item in cache_data
                        }
                        ordered_tensors: List[torch.Tensor] = []
                        self.embedding_map.clear()
                        cache_valid = True
                        # Rebuild embeddings tensor in the same order as self.furniture_items
                        for furniture_item in self.furniture_items:
                            fid = furniture_item['id']
                            embedding_data = id_to_embedding.get(fid)
                            if embedding_data is None:
                                cache_valid = False
                                break
                            tensor = torch.tensor(
                                embedding_data,
                                dtype=torch.float32,
                                device=DEVICE,
                            )
                            ordered_tensors.append(tensor)
                            self.embedding_map[fid] = tensor
                        if cache_valid and ordered_tensors:
                            self.embeddings = torch.stack(ordered_tensors)
                            logging.info(f"Loaded {len(cache_data)} embeddings from cache")
                        
            except Exception as e:
                logging.exception(f"Cache load error ({type(e).__name__}): {e} - recomputing...")
        
        if not cache_valid:
            logging.info(f"Computing embeddings for {len(self.furniture_items)} items...")
            descriptions = [item['description'] for item in self.furniture_items]
            
            embeddings = SENTENCE_MODEL.encode(
                descriptions,
                convert_to_tensor=True,
                show_progress_bar=True,
                normalize_embeddings=True
            )
            self.embeddings = embeddings.to(DEVICE)
            
            # Build lookup map
            for item, emb in zip(self.furniture_items, embeddings):
                self.embedding_map[item['id']] = emb.to(DEVICE)
            
            # Save to cache
            if self.use_cache:
                try:
                    cache_data = [
                        {
                            'id': item['id'],
                            'furniture_name': item['furniture_name'],
                            'embedding': emb.cpu().numpy().tolist()
                        }
                        for item, emb in zip(self.furniture_items, embeddings)
                    ]
                    with open(EMBEDDINGS_CACHE, 'w', encoding='utf-8') as f:
                        json.dump(cache_data, f, ensure_ascii=False, separators=(',', ':'))
                    logging.info(f"Saved embeddings cache to {EMBEDDINGS_CACHE}")
                except Exception as e:
                    logging.exception(f"Failed to save cache: {e}")
    
    def _pil_to_base64(self, image: Image, format: str = "JPEG", max_size: int = 1024) -> str:
        """Convert PIL image to base64 string for OpenAI API"""
        # Resize if too large to reduce token cost and API payload
        if max(image.size) > max_size:
            image = image.copy()
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        # Convert to RGB if needed (for JPEG compatibility)
        if image.mode in ("RGBA", "P", "LA"):
            image = image.convert("RGB")
        
        buffered = io.BytesIO()
        image.save(buffered, format=format, quality=85, optimize=True)
        return base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    def _get_furniture_description(self) -> List[str]:
        """Get furniture description from OpenAI GPT-4o vision API"""
        if not self.image:
            return []
            
        try:
            # Convert image to base64
            image_base64 = self._pil_to_base64(self.image)
            
            prompt = (
                "Identify all furniture items in this interior design image. "
                "Provide a detailed description for each item. "
                "Output the result strictly as a JSON array of strings. "
                "Do not include any markdown formatting or extra text outside the JSON array.\n"
                "Example: [\"Modern grey sofa with chrome legs\", \"Round wooden coffee table with glass top\"]"
            )
            
            response = OPENAI_CLIENT.chat.completions.create(
                model=VISION_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}",
                                    "detail": "auto"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1024,
                temperature=0.1
            )
            
            final_answer = response.choices[0].message.content.strip()
            furniture_list = self._parse_json_output(final_answer)
            return furniture_list

        except Exception as e:
            logging.exception(f"OpenAI API Error: {e}")
            return []

    def _parse_json_output(self, text: str) -> List[str]:
        """Helper to clean and parse JSON from model output"""
        try:
            clean_text = re.sub(r'```json\s*', '', text)
            clean_text = re.sub(r'```\s*', '', clean_text)
            clean_text = clean_text.strip()
            
            data = json.loads(clean_text)       
            if isinstance(data, list):
                cleaned = []
                for item in data:
                    item_str = str(item).strip()
                    item_str = item_str.strip('"\'').rstrip(',').strip()
                    if item_str and len(item_str) > 3:
                        cleaned.append(item_str)
                return cleaned
            else:
                return [clean_text] if clean_text else []
                
        except json.JSONDecodeError:
            # Fallback parsing
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            ignore_words = ['here', 'list', 'items', 'output']
            filtered_lines = []
            for line in lines:
                clean_line = line.strip('"\'').rstrip(',').strip()
                if (not any(word in clean_line.lower() for word in ignore_words) 
                    and len(clean_line) > 3 
                    and clean_line not in filtered_lines):
                    filtered_lines.append(clean_line)
            return filtered_lines if filtered_lines else [text]
        
        except Exception as e:
            logging.exception(f"Parse Error: {e}")
            return [text] if text else []
    
    def find_similar(
        self, 
        similarity_threshold: float = 0.0, 
        max_per_category: int = 3
    ) -> List[Tuple[Dict, float]]:
        """
        Find similar furniture items using cosine similarity on embeddings.
        """
        if not self.furniture_items or self.embeddings is None:
            return []

        descriptions = self._get_furniture_description()
        if not descriptions:
            return []
    
        results = []
        seen_items = set()
        
        for query in descriptions:
            try:
                query_embedding = SENTENCE_MODEL.encode(
                    query, 
                    convert_to_tensor=True,
                    normalize_embeddings=True
                ).to(DEVICE)
                
                cos_scores = util.cos_sim(query_embedding, self.embeddings)[0]
                
                for idx, score in enumerate(cos_scores):
                    score_float = float(score)
                    if score_float >= similarity_threshold:
                        item = self.furniture_items[idx]
                        item_key = item['id']
                        
                        if item_key not in seen_items:
                            seen_items.add(item_key)
                            results.append((item, score_float))
            
            except Exception as e:
                logging.exception(f"Error processing query '{query}': {e}")
                continue
        
        # Sort by similarity score descending
        results.sort(key=lambda x: x[1], reverse=True)
        
        # Group by category and limit per category
        category_results = defaultdict(list)
        for item, score in results:
            category = item.get('category') or 'uncategorized'
            category_results[category].append((item, score))

        final_results = []
        for category, items in category_results.items():
            for item, score in items[:max_per_category]:
                final_results.append((item, score))

        final_results.sort(key=lambda x: x[1], reverse=True)
        return final_results
    
    def close(self):
        """Cleanup resources"""
        if hasattr(self, 'db'):
            self.db.close_session()