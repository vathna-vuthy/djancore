from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.organizations.models import (
    InvitationStatus,
    OrganizationMember,
    OrganizationRole,
)
from apps.organizations.services import OrganizationService

User = get_user_model()


class OrganizationServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="service_owner@example.com",
            password="StrongPassword123!",
        )
        self.user2 = User.objects.create_user(
            email="service_user2@example.com",
            password="StrongPassword123!",
        )

    def test_create_organization(self):
        org = OrganizationService.create_organization(
            owner=self.owner,
            name="Cloud Labs",
            description="Next-gen cloud platform",
        )
        self.assertEqual(org.name, "Cloud Labs")
        self.assertEqual(org.owner, self.owner)
        self.assertTrue(
            OrganizationMember.objects.filter(
                organization=org,
                user=self.owner,
                role=OrganizationRole.OWNER,
            ).exists()
        )

    def test_invite_member_and_accept(self):
        org = OrganizationService.create_organization(
            owner=self.owner,
            name="Dev Hub",
        )
        invite = OrganizationService.invite_member(
            organization=org,
            invited_by=self.owner,
            email="service_user2@example.com",
            role=OrganizationRole.ADMIN,
        )
        self.assertEqual(invite.status, InvitationStatus.PENDING)

        # Cannot invite already active member
        with self.assertRaises(ValidationError):
            OrganizationService.invite_member(
                organization=org,
                invited_by=self.owner,
                email="service_owner@example.com",
            )

        # Accept invitation
        member = OrganizationService.accept_invitation(
            token=invite.token,
            user=self.user2,
        )
        self.assertEqual(member.role, OrganizationRole.ADMIN)
        self.assertEqual(member.organization, org)

    def test_transfer_ownership(self):
        org = OrganizationService.create_organization(
            owner=self.owner,
            name="FinTech Corp",
        )
        # Add user2 as member first
        OrganizationMember.objects.create(
            organization=org,
            user=self.user2,
            role=OrganizationRole.MEMBER,
        )

        # Transfer ownership to user2
        updated_org = OrganizationService.transfer_ownership(
            organization=org,
            current_owner=self.owner,
            new_owner=self.user2,
        )
        self.assertEqual(updated_org.owner, self.user2)

        # Check new owner member role
        new_owner_member = OrganizationMember.objects.get(
            organization=org, user=self.user2
        )
        self.assertEqual(new_owner_member.role, OrganizationRole.OWNER)

        # Check prior owner is now ADMIN
        old_owner_member = OrganizationMember.objects.get(
            organization=org, user=self.owner
        )
        self.assertEqual(old_owner_member.role, OrganizationRole.ADMIN)
