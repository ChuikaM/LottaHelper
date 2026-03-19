import redis

class RedisManager:
    def __init__(self):
        self.__redis = redis.StrictRedis(
            host='localhost', 
            port=6379, 
            db=0)
    
    def add_token(self, token):
        self.__redis.set('token', token)
    def remove_token(self, token):
        self.__redis.delete(token)
    def token_exists(self, token):
        return self.__redis.exists(token)
