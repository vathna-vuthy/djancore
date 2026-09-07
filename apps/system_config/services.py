import json
from typing import Any

from django.core.cache import cache

from apps.system_config.models import ConfigDataType, SystemConfig

CACHE_TIMEOUT = 3600 * 24  # 24 hours (invalidated on write)


class ConfigService:
    """Service layer managing dynamic configuration access with multi-layer caching."""

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """
        Retrieve typed configuration value by key.
        Checks cache first, then database, then returns default.
        """
        cache_key = f"system_config:{key}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            config = SystemConfig.objects.get(key=key)
            val = config.typed_value
            cache.set(cache_key, val, timeout=CACHE_TIMEOUT)
            return val
        except SystemConfig.DoesNotExist:
            return default

    @classmethod
    def get_bool(cls, key: str, default: bool = False) -> bool:
        """Retrieve configuration value cast to boolean."""
        val = cls.get(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            return val.strip().lower() in ("true", "1", "t", "yes", "y", "on")
        return bool(val)

    @classmethod
    def get_int(cls, key: str, default: int = 0) -> int:
        """Retrieve configuration value cast to integer."""
        val = cls.get(key, default)
        try:
            return int(val)
        except ValueError, TypeError:
            return default

    @classmethod
    def get_float(cls, key: str, default: float = 0.0) -> float:
        """Retrieve configuration value cast to float."""
        val = cls.get(key, default)
        try:
            return float(val)
        except ValueError, TypeError:
            return default

    @classmethod
    def get_json(cls, key: str, default: Any = None) -> Any:
        """Retrieve configuration value parsed as JSON."""
        val = cls.get(key, default)
        if isinstance(val, (dict, list)):
            return val
        if isinstance(val, str):
            try:
                return json.loads(val)
            except json.JSONDecodeError, TypeError:
                return default
        return val if val is not None else default

    @classmethod
    def set(
        cls,
        key: str,
        value: Any,
        data_type: str | None = None,
        group: str = "general",
        description: str = "",
        is_secret: bool = False,
        is_public: bool = False,
    ) -> SystemConfig:
        """Create or update a system configuration."""
        # Auto-detect type if not provided
        if data_type is None:
            if isinstance(value, bool):
                data_type = ConfigDataType.BOOLEAN
            elif isinstance(value, int):
                data_type = ConfigDataType.INTEGER
            elif isinstance(value, float):
                data_type = ConfigDataType.FLOAT
            elif isinstance(value, (dict, list)):
                data_type = ConfigDataType.JSON
            else:
                data_type = ConfigDataType.STRING

        raw_str = SystemConfig.serialize_value(value, data_type)

        config, _ = SystemConfig.all_objects.update_or_create(
            key=key,
            defaults={
                "raw_value": raw_str,
                "data_type": data_type,
                "group": group,
                "description": description,
                "is_secret": is_secret,
                "is_public": is_public,
                "is_deleted": False,
                "deleted_at": None,
            },
        )
        return config

    @classmethod
    def get_public_configs(cls) -> dict[str, Any]:
        """Return all public configuration settings as a key-value dictionary."""
        cache_key = "system_config:all_public"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        configs = SystemConfig.objects.filter(is_public=True)
        res = {c.key: c.typed_value for c in configs}
        cache.set(cache_key, res, timeout=CACHE_TIMEOUT)
        return res

    @classmethod
    def purge_cache(cls):
        """Purge all cached configuration keys."""
        for config in SystemConfig.all_objects.all():
            cache.delete(f"system_config:{config.key}")
        cache.delete("system_config:all_public")


# Convenience top-level functions
get_config = ConfigService.get
get_bool_config = ConfigService.get_bool
get_int_config = ConfigService.get_int
get_float_config = ConfigService.get_float
get_json_config = ConfigService.get_json
set_config = ConfigService.set
