from apps.notifications.providers.base import BaseNotificationProvider
from apps.notifications.providers.email import EmailNotificationProvider
from apps.notifications.providers.telegram import TelegramNotificationProvider


class ProviderRegistry:
    """Registry maintaining active notification providers per communication channel."""

    _providers: dict[str, BaseNotificationProvider] = {}

    @classmethod
    def register(
        cls,
        channel: str,
        provider: BaseNotificationProvider | type[BaseNotificationProvider],
    ):
        """Register a provider instance or class for a specific channel name."""
        provider_instance = provider() if isinstance(provider, type) else provider
        cls._providers[channel.lower()] = provider_instance

    @classmethod
    def get(cls, channel: str) -> BaseNotificationProvider | None:
        """Retrieve the provider registered for the specified channel."""
        return cls._providers.get(channel.lower())

    @classmethod
    def list_providers(cls) -> dict[str, dict[str, bool]]:
        """Return all registered providers and their configuration readiness."""
        return {
            channel: {
                "configured": provider.is_configured(),
                "class_name": provider.__class__.__name__,
            }
            for channel, provider in cls._providers.items()
        }


# Register default providers
ProviderRegistry.register("email", EmailNotificationProvider)
ProviderRegistry.register("telegram", TelegramNotificationProvider)
