from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (Asset, Assignment, Category, Department, Employee, Location,
                     LocationHistory, Maintenance)


class BaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles", verbosity=0)
        cls.admin = User.objects.create_superuser("boss", "b@x.com", "pw")
        cls.staff = User.objects.create_user("staff", password="pw")
        cls.staff.groups.add(Group.objects.get(name="IT Staff"))
        cls.viewer = User.objects.create_user("viewer", password="pw")
        cls.viewer.groups.add(Group.objects.get(name="Viewer"))

        cls.laptop = Category.objects.create(name="Laptop")
        cls.store = Location.objects.create(name="IT Store")
        cls.office = Location.objects.create(name="Accounts Office")
        cls.dept = Department.objects.create(name="Accounts")
        cls.emp = Employee.objects.create(staff_id="S1", full_name="Ada Obi", department=cls.dept)
        cls.asset = Asset.objects.create(name="HP EliteBook", category=cls.laptop,
                                         serial_number="SN-1", location=cls.store)


class AssetModelTests(BaseTestCase):
    def test_asset_tag_is_generated_in_sequence(self):
        second = Asset.objects.create(name="Dell", category=self.laptop, serial_number="SN-2")
        self.assertRegex(self.asset.asset_tag, r"^ITA-\d{5}$")
        self.assertNotEqual(self.asset.asset_tag, second.asset_tag)

    def test_serial_number_must_be_unique(self):
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            Asset.objects.create(name="Copy", category=self.laptop, serial_number="SN-1")

    def test_moving_an_asset_is_logged(self):
        self.assertEqual(LocationHistory.objects.filter(asset=self.asset).count(), 1)
        self.asset.location = self.office
        self.asset.save()
        latest = LocationHistory.objects.filter(asset=self.asset).first()
        self.assertEqual((latest.from_location, latest.to_location), (self.store, self.office))

    def test_saving_without_moving_does_not_log(self):
        self.asset.notes = "Just a note"
        self.asset.save()
        self.assertEqual(LocationHistory.objects.filter(asset=self.asset).count(), 1)


class WorkflowTests(BaseTestCase):
    def test_assign_then_return_updates_status(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("assignment_add"), {
            "asset": self.asset.pk, "employee": self.emp.pk,
            "assigned_date": timezone.localdate().isoformat(),
        })
        self.assertRedirects(response, reverse("assignment_list"))
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, Asset.Status.ASSIGNED)
        assignment = Assignment.objects.get()
        self.assertEqual(assignment.assigned_by, self.staff)

        response = self.client.post(reverse("assignment_return", args=[assignment.pk]), {
            "returned_date": timezone.localdate().isoformat(), "condition_on_return": "fair",
        })
        self.assertRedirects(response, reverse("assignment_list"))
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, Asset.Status.AVAILABLE)
        self.assertEqual(self.asset.condition, "fair")

    def test_assigned_asset_cannot_be_assigned_again(self):
        Assignment.objects.create(asset=self.asset, employee=self.emp)
        self.client.force_login(self.staff)
        response = self.client.post(reverse("assignment_add"), {
            "asset": self.asset.pk, "employee": self.emp.pk,
            "assigned_date": timezone.localdate().isoformat(),
        })
        self.assertEqual(response.status_code, 200)   # form redisplayed with an error
        self.assertEqual(Assignment.objects.count(), 1)

    def test_return_date_cannot_precede_assigned_date(self):
        assignment = Assignment.objects.create(asset=self.asset, employee=self.emp)
        self.client.force_login(self.staff)
        yesterday = timezone.localdate() - timedelta(days=1)
        response = self.client.post(reverse("assignment_return", args=[assignment.pk]),
                                    {"returned_date": yesterday.isoformat(), "condition_on_return": "good"})
        self.assertEqual(response.status_code, 200)
        assignment.refresh_from_db()
        self.assertIsNone(assignment.returned_date)

    def test_maintenance_in_progress_sets_and_clears_status(self):
        job = Maintenance.objects.create(asset=self.asset, description="Screen", status="in_progress")
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, Asset.Status.MAINTENANCE)
        job.status = "completed"
        job.save()
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, Asset.Status.AVAILABLE)
        self.assertIsNotNone(job.date_completed)

    def test_finished_repair_returns_asset_to_assigned_if_someone_holds_it(self):
        Assignment.objects.create(asset=self.asset, employee=self.emp)
        job = Maintenance.objects.create(asset=self.asset, description="Fan", status="in_progress")
        job.status = "completed"
        job.save()
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, Asset.Status.ASSIGNED)

    def test_asset_with_history_cannot_be_deleted(self):
        Assignment.objects.create(asset=self.asset, employee=self.emp)
        self.client.force_login(self.admin)
        self.client.post(reverse("asset_delete", args=[self.asset.pk]))
        self.assertTrue(Asset.objects.filter(pk=self.asset.pk).exists())


class AccessControlTests(BaseTestCase):
    def test_anonymous_users_are_sent_to_login(self):
        for name in ("dashboard", "asset_list", "employee_list", "reports"):
            response = self.client.get(reverse(name))
            self.assertRedirects(response, f"{reverse('login')}?next={reverse(name)}")

    def test_viewer_can_read_but_not_write(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("asset_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("asset_detail", args=[self.asset.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("asset_add")).status_code, 403)
        self.assertEqual(self.client.get(reverse("asset_edit", args=[self.asset.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("asset_delete", args=[self.asset.pk])).status_code, 403)

    def test_staff_can_add_but_not_delete(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("asset_add")).status_code, 200)
        self.assertEqual(self.client.get(reverse("asset_delete", args=[self.asset.pk])).status_code, 403)

    def test_admin_can_delete(self):
        spare = Asset.objects.create(name="Spare", category=self.laptop, serial_number="SN-9")
        self.client.force_login(self.admin)
        self.client.post(reverse("asset_delete", args=[spare.pk]))
        self.assertFalse(Asset.objects.filter(pk=spare.pk).exists())

    def test_buttons_are_hidden_from_viewers(self):
        self.client.force_login(self.viewer)
        page = self.client.get(reverse("asset_list"))
        self.assertNotContains(page, reverse("asset_add"))
        self.assertNotContains(page, reverse("asset_edit", args=[self.asset.pk]))


class ScreenSmokeTests(BaseTestCase):
    """Every screen should open without an error for a user allowed to see it."""

    def setUp(self):
        self.assignment = Assignment.objects.create(asset=self.asset, employee=self.emp)
        self.job = Maintenance.objects.create(asset=self.asset, description="Check", status="scheduled")

    def test_all_screens_open(self):
        self.client.force_login(self.admin)
        urls = [
            reverse("dashboard"), reverse("asset_list"), reverse("asset_add"),
            reverse("asset_detail", args=[self.asset.pk]), reverse("asset_edit", args=[self.asset.pk]),
            reverse("asset_label", args=[self.asset.pk]), reverse("employee_list"), reverse("employee_add"),
            reverse("employee_detail", args=[self.emp.pk]), reverse("employee_edit", args=[self.emp.pk]),
            reverse("assignment_list"), reverse("assignment_add"),
            reverse("assignment_detail", args=[self.assignment.pk]),
            reverse("assignment_return", args=[self.assignment.pk]),
            reverse("maintenance_list"), reverse("maintenance_add"),
            reverse("maintenance_detail", args=[self.job.pk]), reverse("maintenance_edit", args=[self.job.pk]),
            reverse("location_list"), reverse("location_add"), reverse("location_detail", args=[self.store.pk]),
            reverse("category_list"), reverse("category_add"),
            reverse("department_list"), reverse("department_add"), reverse("reports"),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_search_and_filters(self):
        self.client.force_login(self.viewer)
        hit = self.client.get(reverse("asset_list"), {"q": "SN-1"})
        self.assertContains(hit, self.asset.asset_tag)
        miss = self.client.get(reverse("asset_list"), {"q": "no-such-thing"})
        self.assertNotContains(miss, self.asset.asset_tag)
        by_status = self.client.get(reverse("asset_list"), {"status": "lost"})
        self.assertNotContains(by_status, self.asset.asset_tag)

    def test_reports_and_csv_export(self):
        self.client.force_login(self.viewer)
        for kind in ("inventory", "assignments", "maintenance", "warranty"):
            with self.subTest(kind=kind):
                self.assertEqual(self.client.get(reverse("reports"), {"report": kind}).status_code, 200)
                csv_response = self.client.get(reverse("reports"), {"report": kind, "export": "csv"})
                self.assertEqual(csv_response["Content-Type"], "text/csv")
        body = self.client.get(reverse("reports"), {"report": "inventory", "export": "csv"}).content.decode()
        self.assertIn(self.asset.asset_tag, body)

    def test_login_and_logout(self):
        response = self.client.post(reverse("login"), {"username": "staff", "password": "pw"})
        self.assertRedirects(response, reverse("dashboard"))
        self.client.post(reverse("logout"))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
