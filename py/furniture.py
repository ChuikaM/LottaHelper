import json
from transformers import AutoProcessor, LlavaForConditionalGeneration
import base64
from PIL import Image
import torch

model_id = "llava-hf/llava-1.5-7b-hf"
processor = AutoProcessor.from_pretrained(model_id)
model = LlavaForConditionalGeneration.from_pretrained(
    model_id, 
    torch_dtype=torch.float16, 
    low_cpu_mem_usage=True, 
    device_map="auto"
)
def get_furniture_description(image : Image) -> str:
    try:
        prompt = "USER: <image>\nDescribe this item and give recommendations based on its style.\nASSISTANT:"
        inputs = processor(text=prompt, images=image, return_tensors="pt").to("cuda", torch.float16)
        generate_ids = model.generate(**inputs, max_new_tokens=200)
        output = processor.batch_decode(generate_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
        final_answer = output.split("ASSISTANT:")[-1].strip()
    except Exception as e:
        return f"An error occurred: {e}"
    return final_answer

import sys
from pathlib import Path
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer, util

CACHE_DIR = Path(".cache")
EMBEDDINGS_CACHE = CACHE_DIR / "embeddings_cache.json"
class FurnitureFinder:
    def __init__(self, json_path: str, use_cache: bool = True):
        self.json_path = Path(json_path)
        self.use_cache = use_cache
        self.furniture_items = []
        self.embeddings = None
        
        CACHE_DIR.mkdir(exist_ok=True)
        
        self._load_furniture_data()
        self.model = SentenceTransformer("./all-MiniLM-L6-v2", local_files_only=True)
        self._load_or_compute_embeddings()
    
    def _load_furniture_data(self):
        """Load furniture items from JSON file"""
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict) and 'items' in data:
                items = data['items']
            elif isinstance(data, list):
                items = data
            else:
                raise ValueError("Unsupported JSON structure")
            
            self.furniture_items = [
                item for item in items 
                if item.get('description') and isinstance(item['description'], str)
            ]     
                
        except FileNotFoundError:
            print(f"❌ JSON file not found: {self.json_path}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON format: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error loading JSON: {e}")
            sys.exit(1)
    
    def _load_or_compute_embeddings(self):
        """Load cached embeddings or compute new ones"""
        cache_valid = False
        if self.use_cache and EMBEDDINGS_CACHE.exists():
            try:
                with open(EMBEDDINGS_CACHE, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                if (len(cache_data) == len(self.furniture_items) and
                    all('embedding' in item for item in cache_data)):
                    self.embeddings = torch.tensor(
                        [item['embedding'] for item in cache_data],
                        dtype=torch.float32
                    )
                    cache_valid = True
            except Exception as e:
                print(f"⚠️  Cache load error ({type(e).__name__}): {e} - recomputing embeddings...")
        
        if not cache_valid:
            descriptions = [item['description'] for item in self.furniture_items]
            self.embeddings = self.model.encode(
                descriptions,
                convert_to_tensor=True,
                show_progress_bar=True,
                normalize_embeddings=True
            )
            
            if self.use_cache:
                try:
                    cache_data = [
                        {
                            'id': item.get('id', idx),
                            'furniture_name': item.get('furniture_name', 'Unknown'),
                            'embedding': emb.cpu().numpy().tolist()
                        }
                                                for idx, (item, emb) in enumerate(zip(self.furniture_items, self.embeddings))
                    ]
                    with open(EMBEDDINGS_CACHE, 'w', encoding='utf-8') as f:
                        json.dump(cache_data, f, ensure_ascii=False, separators=(',', ':'))
                except Exception as e:
                    print(f"⚠️  Failed to save cache ({type(e).__name__}): {e}")
    
    def find_similar(self, query: str, top_k: int = 5) -> List[Tuple[Dict, float]]:
        """Find top-k most similar furniture items to the query description"""
        if not self.furniture_items or self.embeddings is None:
            return []
        
        query_embedding = self.model.encode(
            query, 
            convert_to_tensor=True,
            normalize_embeddings=True
        )
        
        cos_scores = util.cos_sim(query_embedding, self.embeddings)[0]
        top_results = torch.topk(cos_scores, k=min(top_k, len(cos_scores)))
        results = []
        for score, idx in zip(top_results[0], top_results[1]):
            results.append((
                self.furniture_items[idx],
                float(score)
            ))
        
        return results