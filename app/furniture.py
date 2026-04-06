import json
import torch
import re

import os
import logging

from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict
from PIL import Image

from transformers import AutoModelForCausalLM, AutoTokenizer
from sentence_transformers import SentenceTransformer, util

from app.db.manager.postgresql_manager import PostgreSQLManager

import socket
import urllib3.util.connection as urllib3_cn

def allowed_gai_family():
    return socket.AF_INET
urllib3_cn.allowed_gai_family = allowed_gai_family



CACHE_DIR = Path("cache")
EMBEDDINGS_CACHE = CACHE_DIR / "embeddings_cache_sql.json"

DEVICE = "cpu"
if torch.cuda.is_available():
    DEVICE = "cuda"
elif torch.backends.mps.is_available():
    DEVICE = "mps"
else:
    DEVICE = "cpu"
    torch.set_num_threads(os.cpu_count())

vision_model_id = os.getenv("VISION_MODEL", "vikhyatk/moondream2")
VISION_MODEL = AutoModelForCausalLM.from_pretrained(
    vision_model_id, 
    trust_remote_code=True, 
    dtype=torch.float16 if DEVICE != "cpu" else torch.float32, 
    device_map={"": DEVICE}
)
tokenizer = AutoTokenizer.from_pretrained(vision_model_id)

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
        
        self.db = PostgreSQLManager(database_url)
        
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
    
    def _load_or_compute_embeddings(self):
        """Load cached embeddings or compute new ones from database"""
        cache_valid = False
        
        if self.use_cache and EMBEDDINGS_CACHE.exists():
            try:
                with open(EMBEDDINGS_CACHE, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                if len(cache_data) == len(self.furniture_items):
                    cache_ids = {item['id'] for item in cache_data}
                    current_ids = {item['id'] for item in self.furniture_items}
                    
                    if cache_ids == current_ids and all('embedding' in item for item in cache_data):
                        id_to_embedding = {
                            item['id']: item['embedding'] for item in cache_data
                        }
                        ordered_tensors: List[torch.Tensor] = []
                        self.embedding_map.clear()
                        cache_valid = True
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
            
            for item, emb in zip(self.furniture_items, embeddings):
                self.embedding_map[item['id']] = emb.to(DEVICE)
            
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
    
    def _get_furniture_description(self) -> List[str]:
        """Get furniture description from OpenAI GPT-4o vision API"""
        if not self.image:
            return []
            
        try:
            self.image.thumbnail((600, 600)) 
            enc_image = VISION_MODEL.encode_image(self.image) 
            prompt = (
                "If the image is not an interior design, return an empty string []. "
                "Identify unique furniture and decor items. "
                "Combine identical or repeating elements (like wall slats) into a single description. "
                "For each UNIQUE item, provide a detailed description (15-20 words) "
                "covering material, color, and texture. Output ONLY a JSON array of strings. "
                "Strictly avoid repeating the same item multiple times in the array."
            )    
            description = VISION_MODEL.answer_question(
                enc_image, 
                prompt, 
                tokenizer, 
                max_new_tokens=256
            )
            
            furniture_list = self._parse_json_output(description)
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
        
        results.sort(key=lambda x: x[1], reverse=True)
        
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