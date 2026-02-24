import json
import torch
from transformers import AutoProcessor, LlavaForConditionalGeneration
from PIL import Image
from pathlib import Path
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer, util
import sys

if torch.cuda.is_available():
    device = "cuda"
    torch_dtype = torch.float16
elif torch.backends.mps.is_available():
    device = "mps"
    torch_dtype = torch.float16
else:
    device = "cpu"
    torch_dtype = torch.float32

print(f"Using device for LLaVA: {device}")

model_id = "llava-hf/llava-1.5-7b-hf"
processor = AutoProcessor.from_pretrained(model_id)

model = LlavaForConditionalGeneration.from_pretrained(
    model_id, 
    torch_dtype=torch_dtype, 
    low_cpu_mem_usage=False, 
    device_map=None
)
model.to(device)

def get_furniture_description(image: Image) -> str:
    """Get furniture description from LLaVA model"""
    try:
        prompt = "USER: <image>\nDescribe this furniture item in 2-3 sentences. Mention style, color, and type.\nASSISTANT:"
        inputs = processor(text=prompt, images=image, return_tensors="pt").to(device, torch_dtype)    
        generate_ids = model.generate(**inputs, max_new_tokens=200)
        output = processor.batch_decode(generate_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
        final_answer = output.split("ASSISTANT:")[-1].strip()
        return final_answer
    except Exception as e:
        print(f"LLaVA Error: {e}")
        return "modern furniture"


FINDER_DEVICE = "cpu"

CACHE_DIR = Path(".cache")
EMBEDDINGS_CACHE = CACHE_DIR / "embeddings_cache.json"

class FurnitureFinder:
    def __init__(self, json_path: str, use_cache: bool = True):
        self.json_path = Path(json_path)
        self.use_cache = use_cache
        self.furniture_items = []
        self.embeddings = None
        self.device = FINDER_DEVICE
        
        CACHE_DIR.mkdir(exist_ok=True)
        
        self._load_furniture_data()
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
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
            sys.exit(1)
        except json.JSONDecodeError as e:
            sys.exit(1)
        except Exception as e:
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
                        dtype=torch.float32,
                        device=self.device
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
            self.embeddings = self.embeddings.to(self.device)
            
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
        query_embedding = query_embedding.to(self.device)
        cos_scores = util.cos_sim(query_embedding, self.embeddings)[0]
        top_results = torch.topk(cos_scores, k=min(top_k, len(cos_scores)))
        
        results = []
        for score, idx in zip(top_results[0], top_results[1]):
            results.append((
                self.furniture_items[idx],
                float(score)
            ))
        
        return results