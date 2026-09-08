from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from apps.organizations.models import (
    InvitationStatus,
    Organization,
    OrganizationInvitation,
    OrganizationMember,
    OrganizationRole,
)

User = get_user_model()


class OrganizationModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="StrongPassword123!",
        )
        self.member_user = User.objects.create_user(
            email="member@example.com",
            password="StrongPassword123!",
        )

    def test_organization_creation_and_auto_slug(self):
        org1 = Organization.objects.create(
            name="Acme Corporation",
            owner=self.owner,
        )
        self.assertEqual(org1.slug, "acme-corporation")

        # Test duplicate slug auto-incrementing
        org2 = Organization.objects.create(
            name="Acme Corporation",
            owner=self.owner,
        )
        self.assertEqual(org2.slug, "acme-corporation-1")

    def test_organization_membership_and_roles(self):
        org = Organization.objects.create(
            name="Dev Squad",
            owner=self.owner,
        )
        # Owner check
        self.assertTrue(org.is_member(self.owner))
        self.assertTrue(org.is_admin(self.owner))
        self.assertEqual(org.get_member_role(self.owner), OrganizationRole.OWNER)

        # Add regular member
        OrganizationMember.objects.create(
            organization=org,
            user=self.member_user,
            role=OrganizationRole.MEMBER,
        )
        self.assertTrue(org.is_member(self.member_user))
        self.assertFalse(org.is_admin(self.member_user))
        self.assertEqual(org.get_member_role(self.member_user), OrganizationRole.MEMBER)

        # Unique constraint
        with self.assertRaises(IntegrityError):
            OrganizationMember.objects.create(
                organization=org,
                user=self.member_user,
                role=OrganizationRole.ADMIN,
            )

    def test_organization_invitation_lifecycle(self):
        org = Organization.objects.create(
            name="Marketing Team",
            owner=self.owner,
        )
        invite = OrganizationInvitation.objects.create(
            organization=org,
            invited_by=self.owner,
            email="invitee@example.com",
            role=OrganizationRole.ADMIN,
        )
        self.assertTrue(invite.token.startswith("djc_inv_"))
        self.assertTrue(invite.is_valid)
        self.assertEqual(invite.status, InvitationStatus.PENDING)

        # Accept invite
        new_user = User.objects.create_user(
            email="invitee@example.com",
            password="StrongPassword123!",
        )
        member = invite.accept(new_user)
        self.assertEqual(member.role, OrganizationRole.ADMIN)
        self.assertEqual(invite.status, InvitationStatus.ACCEPTED)
        self.assertFalse(invite.is_valid)

    def test_organization_soft_delete_and_restore(self):
        org = Organization.objects.create(
            name="Sunset Corp",
            owner=self.owner,
        )
        org.delete()
        self.assertFalse(Organization.objects.filter(id=org.id).exists())
        self.assertTrue(Organization.all_objects.filter(id=org.id).exists())

        org.restore()
        self.assertTrue(Organization.objects.filter(id=org.id).exists())
