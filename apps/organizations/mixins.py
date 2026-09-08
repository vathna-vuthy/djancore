from typing import Any

from django.db import models

from apps.core.models import SoftDeleteManager, SoftDeleteQuerySet
from apps.organizations.context import get_current_organization


class TenantQuerySet(SoftDeleteQuerySet):
    """QuerySet that supports scoping queries by the active tenant."""

    def for_organization(self, organization: Any) -> TenantQuerySet:
        """Filter records belonging exclusively to a specific organization."""
        if organization is None:
            return self.none()
        return self.filter(organization=organization)

    def current_tenant(self) -> TenantQuerySet:
        """Filter records belonging to the currently active tenant in contextvars."""
        active_org = get_current_organization()
        return self.for_organization(active_org)


class TenantManager(SoftDeleteManager):
    """Manager providing tenant-aware querysets."""

    def get_queryset(self) -> TenantQuerySet:
        return TenantQuerySet(self.model, using=self._db).alive()

    def for_organization(self, organization: Any) -> TenantQuerySet:
        return self.get_queryset().for_organization(organization)

    def current_tenant(self) -> TenantQuerySet:
        return self.get_queryset().current_tenant()


class TenantModelMixin(models.Model):
    """
    Abstract mixin that associates any domain model with an Organization tenant
    and automatically assigns the active tenant from context if omitted on save.
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_items",
        help_text="The tenant organization that owns this record.",
    )

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not hasattr(self, "organization") or self.organization_id is None:
            active_org = get_current_organization()
            if active_org:
                self.organization = active_org
        super().save(*args, **kwargs)
