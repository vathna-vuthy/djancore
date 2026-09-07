import json
from typing import Any

from django.core.cache import cache
from django.db import models

from apps.core.models import BaseModel


class ConfigDataType(models.TextChoices):
    STRING = "string", "String"
    INTEGER = "integer", "Integer"
    FLOAT = "float", "Float"
    BOOLEAN = "boolean", "Boolean"
    JSON = "json", "JSON"


class SystemConfig(BaseModel):
    """Dynamic runtime system configuration setting."""

    key = models.CharField(
        max_length=150,
        unique=True,
        db_index=True,
        help_text="Unique configuration key (e.g. MAX_LOGIN_ATTEMPTS, SITE_NAME).",
    )
    raw_value = models.TextField(
        blank=True,
        default="",
        help_text="Serialized string value.",
    )
    data_type = models.CharField(
        max_length=20,
        choices=ConfigDataType.choices,
        default=ConfigDataType.STRING,
        help_text="Type of value for validation and casting.",
    )
    group = models.CharField(
        max_length=100,
        default="general",
        db_index=True,
        help_text="Logical group (e.g. security, billing, email, general).",
    )
    description = models.TextField(
        blank=True,
        help_text="Human-readable description of what this setting controls.",
    )
    is_secret = models.BooleanField(
        default=False,
        help_text="Mask value in APIs and logs to protect sensitive data.",
    )
    is_public = models.BooleanField(
        default=False,
        help_text="Allow unauthenticated clients to read this setting.",
    )

    class Meta(BaseModel.Meta):
        db_table = "system_configs"
        verbose_name = "system configuration"
        verbose_name_plural = "system configurations"
        ordering = ["group", "key"]

    def __str__(self) -> str:
        return f"{self.key} ({self.group}) = {self.masked_value if self.is_secret else self.raw_value}"

    @property
    def typed_value(self) -> Any:
        """Return the configuration value cast to its appropriate Python type."""
        return self.cast_value(self.raw_value, self.data_type)

    @property
    def masked_value(self) -> str:
        """Return masked representation if the setting is marked as secret."""
        if not self.is_secret:
            return self.raw_value
        if len(self.raw_value) <= 6:
            return "******"
        return f"{self.raw_value[:2]}******{self.raw_value[-2:]}"

    @classmethod
    def cast_value(cls, value_str: str, data_type: str) -> Any:
        """Parse raw string value into typed Python object."""
        if value_str is None:
            return None

        if data_type == ConfigDataType.INTEGER:
            try:
                return int(value_str)
            except ValueError, TypeError:
                return 0
        elif data_type == ConfigDataType.FLOAT:
            try:
                return float(value_str)
            except ValueError, TypeError:
                return 0.0
        elif data_type == ConfigDataType.BOOLEAN:
            return value_str.strip().lower() in ("true", "1", "t", "yes", "y", "on")
        elif data_type == ConfigDataType.JSON:
            try:
                return json.loads(value_str)
            except json.JSONDecodeError, TypeError:
                return None
        return value_str

    @classmethod
    def serialize_value(cls, value: Any, data_type: str) -> str:
        """Serialize typed Python object into raw string."""
        if value is None:
            return ""
        if data_type == ConfigDataType.JSON:
            if isinstance(value, (dict, list)):
                return json.dumps(value)
            return str(value)
        if data_type == ConfigDataType.BOOLEAN:
            return "true" if bool(value) else "false"
        return str(value)

    def save(self, *args, **kwargs):
        """Save instance and invalidate cache."""
        super().save(*args, **kwargs)
        self.invalidate_cache()

    def delete(self, *args, **kwargs):
        """Soft delete instance and invalidate cache."""
        super().delete(*args, **kwargs)
        self.invalidate_cache()

    def restore(self):
        """Restore instance and invalidate cache."""
        result = super().restore()
        self.invalidate_cache()
        return result

    def invalidate_cache(self):
        """Invalidate cached value for this setting."""
        cache_key = f"system_config:{self.key}"
        cache.delete(cache_key)
        cache.delete("system_config:all_public")
