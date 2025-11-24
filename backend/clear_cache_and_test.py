"""Clear cache and test if requirements work."""

from api.services.cache import clear_cache

print("[CACHE] Clearing all caches...")
clear_cache()
print("[CACHE] Cache cleared!")
print("[CACHE] Please restart the backend server to use fresh data.")
