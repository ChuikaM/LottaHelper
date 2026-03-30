import redis
import os

class RedisManager:
    def __init__(self):
        redis_host = os.getenv('REDIS_HOST', 'redis')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.__redis = redis.StrictRedis(
            host=redis_host,
            port=redis_port,
            db=0,
            decode_responses=True
        )
    
    def add_token(self, token):
        self.__redis.setex(f"token:{token}", 3600, "valid")
    def remove_token(self, token):
        self.__redis.delete(token)
    def token_exists(self, token):
        return self.__redis.exists(token)
