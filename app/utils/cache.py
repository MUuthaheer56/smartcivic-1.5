import time
import threading

class MemoryCache:
    def __init__(self):
        self._store = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key in self._store:
                val, expires = self._store[key]
                if expires is None or expires > time.time():
                    return val
                else:
                    # Expired
                    del self._store[key]
            return None

    def set(self, key, value, ttl=300):
        with self._lock:
            expires = time.time() + ttl if ttl else None
            self._store[key] = (value, expires)

    def delete(self, key):
        with self._lock:
            self._store.pop(key, None)

    def clear(self):
        with self._lock:
            self._store.clear()

# Global cache instance
cache = MemoryCache()
