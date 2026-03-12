import json
import torch
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

from transformers import AutoProcessor, LlavaForConditionalGeneration
from PIL import Image
from sentence_transformers import SentenceTransformer, util

from database import DatabaseManager, FurnitureItem

CACHE_DIR = Path(".cache")
EMBEDDINGS_CACHE = CACHE_DIR / "embeddings_cache_sql.json"


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
        self.embedding_map: Dict[int, torch.Tensor] = {}  # id -> embedding
        
        # Device configuration
        self.device = "cpu"
        if torch.cuda.is_available():
            self.device_description = "cuda"
            self.torch_dtype = torch.float16
        elif torch.backends.mps.is_available():
            self.device_description = "mps"
            self.torch_dtype = torch.float16
        else:
            self.device_description = "cpu"
            self.torch_dtype = torch.float32

        # Load LLaVA model for image description
        self.processor = AutoProcessor.from_pretrained("llava-hf/llava-1.5-7b-hf")
        self.model_describer = LlavaForConditionalGeneration.from_pretrained(
            "llava-hf/llava-1.5-7b-hf", 
            torch_dtype=self.torch_dtype, 
            low_cpu_mem_usage=False, 
            device_map=None
        )
        self.model_describer.to(self.device_description)
        
        # Initialize database
        self.db = DatabaseManager(database_url)
        
        # Load sentence transformer for embeddings
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Load data and compute embeddings
        CACHE_DIR.mkdir(exist_ok=True)
        self._load_furniture_data()
        self._load_or_compute_embeddings()
    
    def _load_furniture_data(self):
        """Load furniture items from SQL database"""
        try:
            items = self.db.get_furniture_items(has_description=True)
            self.furniture_items = [item.to_dict() for item in items]
            
            if not self.furniture_items:
                print("⚠️  No furniture items found in database")
                
        except Exception as e:
            print(f"❌ Database error: {e}")
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
                        self.embeddings = torch.tensor(
                            [item['embedding'] for item in cache_data],
                            dtype=torch.float32,
                            device=self.device
                        )
                        # Build lookup map
                        for item in cache_data:
                            self.embedding_map[item['id']] = torch.tensor(
                                item['embedding'], dtype=torch.float32, device=self.device
                            )
                        cache_valid = True
                        print(f"✅ Loaded {len(cache_data)} embeddings from cache")
                        
            except Exception as e:
                print(f"⚠️  Cache load error ({type(e).__name__}): {e} - recomputing...")
        
        if not cache_valid:
            print(f"🔄 Computing embeddings for {len(self.furniture_items)} items...")
            descriptions = [item['description'] for item in self.furniture_items]
            
            embeddings = self.model.encode(
                descriptions,
                convert_to_tensor=True,
                show_progress_bar=True,
                normalize_embeddings=True
            )
            self.embeddings = embeddings.to(self.device)
            
            # Build lookup map
            for item, emb in zip(self.furniture_items, embeddings):
                self.embedding_map[item['id']] = emb.to(self.device)
            
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
                    print(f"💾 Saved embeddings cache to {EMBEDDINGS_CACHE}")
                except Exception as e:
                    print(f"⚠️  Failed to save cache: {e}")
    
    def _get_furniture_description(self) -> List[str]:
        """Get furniture description from LLaVA model"""
        try:
            prompt = (
                "USER: <image>\n"
                "Identify all furniture items in this interior design image. "
                "Provide a detailed description for each item. "
                "Output the result strictly as a JSON array of strings. "
                "Do not include any markdown formatting or extra text outside the JSON array.\n"
                "Example: [\"Modern grey sofa\", \"Wooden coffee table\"]\n"
                "ASSISTANT:"
            )
            
            inputs = self.processor(
                text=prompt, 
                images=self.image, 
                return_tensors="pt"
            ).to(self.device_description, self.torch_dtype)    
            
            generate_ids = self.model_describer.generate(
                **inputs, 
                max_new_tokens=512,
                do_sample=False,
                temperature=0.1
            )
            
            output = self.processor.batch_decode(
                generate_ids, 
                skip_special_tokens=True, 
                clean_up_tokenization_spaces=False
            )[0]
            
            final_answer = output.split("ASSISTANT:")[-1].strip()
            furniture_list = self._parse_json_output(final_answer)
            return furniture_list

        except Exception as e:
            print(f"[_get_furniture_description] LLaVA Error: {e}")
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
            print(f"[Parse Error] {e}")
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
                query_embedding = self.model.encode(
                    query, 
                    convert_to_tensor=True,
                    normalize_embeddings=True
                ).to(self.device)
                
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
                print(f"Error processing query '{query}': {e}")
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
    
    def search_by_text(self, query: str, top_k: int = 10) -> List[Tuple[Dict, float]]:
        """Direct text search using embeddings (without image)"""
        if not self.furniture_items or self.embeddings is None:
            return []
        
        query_embedding = self.model.encode(
            query,
            convert_to_tensor=True,
            normalize_embeddings=True
        ).to(self.device)
        
        cos_scores = util.cos_sim(query_embedding, self.embeddings)[0]
        top_results = torch.topk(cos_scores, k=min(top_k, len(cos_scores)))
        
        results = []
        for score, idx in zip(top_results.values, top_results.indices):
            item = self.furniture_items[idx]
            results.append((item, float(score)))
        
        return results
    
    def close(self):
        """Cleanup resources"""
        if hasattr(self, 'db'):
            self.db.close_session()