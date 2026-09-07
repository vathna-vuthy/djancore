import uuid
from typing import Self

from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet supporting soft delete filtering and operations."""

    def delete(self):
        """Soft delete all records in the QuerySet."""
        return self.update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        """Permanently delete records from the database."""
        return super().delete()

    def restore(self):
        """Restore soft-deleted records."""
        return self.update(is_deleted=False, deleted_at=None)

    def alive(self):
        """Return only non-deleted records."""
        return self.filter(is_deleted=False)

    def dead(self):
        """Return only soft-deleted records."""
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    """Manager returning only non-deleted instances by default."""

    def get_queryset(self) -> SoftDeleteQuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db).alive()

    def all_with_deleted(self) -> SoftDeleteQuerySet:
        """Return all instances including soft-deleted ones."""
        return SoftDeleteQuerySet(self.model, using=self._db)

    def deleted(self) -> SoftDeleteQuerySet:
        """Return only soft-deleted instances."""
        return SoftDeleteQuerySet(self.model, using=self._db).dead()


class TimeStampedModel(models.Model):
    """An abstract base model providing self-updating timestamp fields."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class UUIDModel(models.Model):
    """An abstract base model providing a UUID primary key."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """An abstract base model providing soft-delete functionality."""

    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    def delete(self, using=None, keep_parents=False):
        """Soft delete the instance."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])

    def hard_delete(self, using=None, keep_parents=False):
        """Permanently delete the instance from the database."""
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self) -> Self:
        """Restore a soft-deleted instance."""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at"])
        return self


class BaseModel(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """Abstract base model combining UUID primary key, timestamps, and soft delete."""

    class Meta:
        abstract = True
        ordering = ["-created_at"]
