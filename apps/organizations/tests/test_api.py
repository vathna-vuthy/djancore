from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.organizations.models import (
    OrganizationMember,
    OrganizationRole,
)
from apps.organizations.services import OrganizationService

User = get_user_model()


class OrganizationAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="api_org_owner@example.com",
            password="StrongPassword123!",
        )
        self.member_user = User.objects.create_user(
            email="api_org_member@example.com",
            password="StrongPassword123!",
        )
        self.client.force_authenticate(user=self.owner)

        self.org = OrganizationService.create_organization(
            owner=self.owner,
            name="Apex Systems",
            slug="apex-systems",
        )
        self.member_record = OrganizationMember.objects.create(
            organization=self.org,
            user=self.member_user,
            role=OrganizationRole.MEMBER,
        )

    def test_list_and_create_organization(self):
        url = reverse("organizations:organization-list")

        # 1. List organizations
        list_res = self.client.get(url)
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertTrue(list_res.data["success"])
        self.assertEqual(len(list_res.data["data"]), 1)
        self.assertEqual(list_res.data["data"][0]["name"], "Apex Systems")
        self.assertEqual(list_res.data["data"][0]["user_role"], OrganizationRole.OWNER)

        # 2. Create another organization
        create_payload = {
            "name": "Beta Workspace",
            "description": "Secondary test tenant",
        }
        create_res = self.client.post(url, create_payload, format="json")
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_res.data["data"]["name"], "Beta Workspace")
        self.assertEqual(create_res.data["data"]["slug"], "beta-workspace")

    def test_switch_workspace_action(self):
        url = reverse("organizations:organization-switch", kwargs={"pk": self.org.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers["X-Organization-ID"], str(self.org.id))

    def test_list_and_invite_members(self):
        members_url = reverse(
            "organizations:organization-members", kwargs={"pk": self.org.id}
        )

        # List members
        get_res = self.client.get(members_url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(get_res.data["data"]), 2)  # owner + member_user

        # Invite new member
        invite_payload = {
            "email": "contractor@example.com",
            "role": OrganizationRole.BILLING,
        }
        post_res = self.client.post(members_url, invite_payload, format="json")
        self.assertEqual(post_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(post_res.data["data"]["email"], "contractor@example.com")
        self.assertEqual(post_res.data["data"]["role"], OrganizationRole.BILLING)

    def test_manage_member_role_and_removal(self):
        manage_url = reverse(
            "organizations:organization-manage-member",
            kwargs={"pk": self.org.id, "member_id": self.member_record.id},
        )

        # Update role to ADMIN
        patch_res = self.client.patch(
            manage_url, {"role": OrganizationRole.ADMIN}, format="json"
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.member_record.refresh_from_db()
        self.assertEqual(self.member_record.role, OrganizationRole.ADMIN)

        # Remove member
        del_res = self.client.delete(manage_url)
        self.assertEqual(del_res.status_code, status.HTTP_200_OK)
        self.member_record.refresh_from_db()
        self.assertTrue(self.member_record.is_deleted)

    def test_invitation_accept_flow(self):
        invite = OrganizationService.invite_member(
            organization=self.org,
            invited_by=self.owner,
            email="newhire@example.com",
            role=OrganizationRole.MEMBER,
        )

        # Switch client to newhire
        newhire = User.objects.create_user(
            email="newhire@example.com",
            password="StrongPassword123!",
        )
        self.client.force_authenticate(user=newhire)

        # Accept invitation
        accept_url = reverse("organizations:invitation-accept")
        accept_res = self.client.post(
            accept_url, {"token": invite.token}, format="json"
        )
        self.assertEqual(accept_res.status_code, status.HTTP_200_OK)
        self.assertTrue(
            OrganizationMember.objects.filter(
                organization=self.org,
                user=newhire,
                is_active=True,
            ).exists()
        )
