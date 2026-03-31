import redis
import os
import logging

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
    
    def add_token(self, token, ttl=3600):
        key = f"token:{token}"
        self.__redis.setex(key, ttl, "1")
        logging.info(f"Added token: {token} under key {key}")
        logging.info(f"Exists after add: {self.__redis.exists(key)}")
    
    def remove_token(self, token):
        key = f"token:{token}"
        self.__redis.delete(key)
    
    def token_exists(self, token):
        key = f"token:{token}"
        exists = self.__redis.exists(key)
        logging.info(f"Checking token: {token}, exists: {exists}")
        return exists