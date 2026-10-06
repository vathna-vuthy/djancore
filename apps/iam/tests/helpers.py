from apps.iam.models import Permission


def grant_permissions(user, *actions):
    """Give API test fixtures explicit policies without bypassing authorization."""
    for action in actions:
        permission, _ = Permission.objects.get_or_create(
            name=f"Test {action}",
            defaults={"action": action, "resource": "*", "effect": "ALLOW"},
        )
        user.direct_permissions.add(permission)
