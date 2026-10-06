from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Category(models.Model):
    """Type of equipment, e.g. Laptop, Printer, Router."""

    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Location(models.Model):
    """A physical place where an asset can be kept."""

    name = models.CharField(max_length=100, help_text="e.g. Server Room, Accounts Office")
    building = models.CharField(max_length=100, blank=True)
    floor = models.CharField(max_length=30, blank=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("name", "building", "floor")]

    def __str__(self):
        parts = [self.name]
        if self.building:
            parts.append(self.building)
        if self.floor:
            parts.append(f"Floor {self.floor}")
        return ", ".join(parts)


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Employee(models.Model):
    staff_id = models.CharField("Staff ID", max_length=30, unique=True)
    full_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees")
    job_title = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(
        "active", default=True, help_text="Untick when the employee leaves the organisation."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.staff_id})"

    def get_absolute_url(self):
        return reverse("employee_detail", args=[self.pk])

    @property
    def active_assignments(self):
        return self.assignments.filter(returned_date__isnull=True)


class Asset(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        ASSIGNED = "assigned", "Assigned"
        MAINTENANCE = "maintenance", "In maintenance"
        RETIRED = "retired", "Retired"
        LOST = "lost", "Lost or stolen"

    class Condition(models.TextChoices):
        NEW = "new", "New"
        GOOD = "good", "Good"
        FAIR = "fair", "Fair"
        POOR = "poor", "Poor"

    asset_tag = models.CharField(max_length=20, unique=True, editable=False)
    name = models.CharField(max_length=150, help_text="e.g. HP EliteBook 840 G8")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="assets")
    brand = models.CharField(max_length=80, blank=True)
    model_name = models.CharField("model", max_length=80, blank=True)
    serial_number = models.CharField(max_length=100, unique=True)
    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    warranty_expiry = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    condition = models.CharField(max_length=10, choices=Condition.choices, default=Condition.NEW)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name="assets")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.asset_tag} - {self.name}"

    def get_absolute_url(self):
        return reverse("asset_detail", args=[self.pk])

    @classmethod
    def next_tag(cls):
        """ITA-00001, ITA-00002 ... based on the highest id so far."""
        last = cls.objects.order_by("-id").values_list("id", flat=True).first() or 0
        return f"ITA-{last + 1:05d}"

    def save(self, *args, **kwargs):
        creating = self.pk is None
        if creating and not self.asset_tag:
            self.asset_tag = self.next_tag()

        # Remember where the asset was, so a move can be logged in LocationHistory.
        old_location_id = None
        if not creating:
            old_location_id = Asset.objects.filter(pk=self.pk).values_list("location_id", flat=True).first()

        super().save(*args, **kwargs)

        if creating and self.location_id:
            LocationHistory.objects.create(asset=self, from_location=None, to_location=self.location)
        elif not creating and old_location_id != self.location_id:
            LocationHistory.objects.create(
                asset=self, from_location_id=old_location_id, to_location=self.location
            )

    @property
    def current_assignment(self):
        return self.assignments.filter(returned_date__isnull=True).select_related("employee").first()

    @property
    def warranty_active(self):
        return bool(self.warranty_expiry and self.warranty_expiry >= timezone.localdate())

    def refresh_status(self):
        """Recalculate status after an assignment or maintenance change.

        Retired and lost assets are left alone: those are set by a person.
        """
        if self.status in (self.Status.RETIRED, self.Status.LOST):
            return
        if self.maintenance_records.filter(status=Maintenance.Status.IN_PROGRESS).exists():
            new_status = self.Status.MAINTENANCE
        elif self.assignments.filter(returned_date__isnull=True).exists():
            new_status = self.Status.ASSIGNED
        else:
            new_status = self.Status.AVAILABLE
        if new_status != self.status:
            self.status = new_status
            self.save(update_fields=["status", "updated_at"])


class LocationHistory(models.Model):
    """One row for every time an asset is placed or moved."""

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="location_history")
    from_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    to_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    moved_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-moved_at", "-id"]
        verbose_name_plural = "location history"

    def __str__(self):
        return f"{self.asset.asset_tag}: {self.from_location or 'New'} -> {self.to_location or 'Unknown'}"


class Assignment(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="assignments")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="assignments")
    assigned_date = models.DateField(default=timezone.localdate)
    expected_return_date = models.DateField(null=True, blank=True)
    returned_date = models.DateField(null=True, blank=True)
    condition_on_assign = models.CharField("condition when assigned", max_length=10,
                                           choices=Asset.Condition.choices, blank=True)
    condition_on_return = models.CharField("condition when returned", max_length=10,
                                           choices=Asset.Condition.choices, blank=True)
    notes = models.TextField(blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assigned_date", "-id"]

    def __str__(self):
        return f"{self.asset.asset_tag} -> {self.employee.full_name}"

    def get_absolute_url(self):
        return reverse("assignment_detail", args=[self.pk])

    @property
    def is_active(self):
        return self.returned_date is None

    @property
    def is_overdue(self):
        return bool(self.is_active and self.expected_return_date and self.expected_return_date < timezone.localdate())

    @property
    def state(self):
        if not self.is_active:
            return "returned"
        return "overdue" if self.is_overdue else "active"

    @property
    def state_label(self):
        return {"returned": "Returned", "overdue": "Overdue", "active": "Assigned"}[self.state]

    def clean(self):
        errors = {}
        if self.returned_date and self.assigned_date and self.returned_date < self.assigned_date:
            errors["returned_date"] = "Return date cannot be before the assigned date."
        if self.expected_return_date and self.assigned_date and self.expected_return_date < self.assigned_date:
            errors["expected_return_date"] = "Expected return cannot be before the assigned date."
        if self._state.adding:
            if self.asset_id and self.asset.status != Asset.Status.AVAILABLE:
                errors["asset"] = f"This asset is {self.asset.get_status_display().lower()} and cannot be assigned."
            if self.employee_id and not self.employee.is_active:
                errors["employee"] = "This employee is marked inactive."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.asset.refresh_status()


class Maintenance(models.Model):
    class Kind(models.TextChoices):
        PREVENTIVE = "preventive", "Preventive service"
        REPAIR = "repair", "Repair"
        UPGRADE = "upgrade", "Upgrade"
        INSPECTION = "inspection", "Inspection"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="maintenance_records")
    kind = models.CharField("type", max_length=20, choices=Kind.choices, default=Kind.REPAIR)
    description = models.TextField(help_text="What is wrong, or what work is being done?")
    technician = models.CharField(max_length=120, blank=True, help_text="Person or company doing the work")
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    date_reported = models.DateField(default=timezone.localdate)
    date_completed = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_reported", "-id"]
        verbose_name_plural = "maintenance records"

    def __str__(self):
        return f"{self.asset.asset_tag} {self.get_kind_display()} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse("maintenance_detail", args=[self.pk])

    def clean(self):
        if self.date_completed and self.date_reported and self.date_completed < self.date_reported:
            raise ValidationError({"date_completed": "Completion date cannot be before the reported date."})

    def save(self, *args, **kwargs):
        if self.status == self.Status.COMPLETED and not self.date_completed:
            self.date_completed = timezone.localdate()
        super().save(*args, **kwargs)
        self.asset.refresh_status()

    def delete(self, *args, **kwargs):
        asset = self.asset
        super().delete(*args, **kwargs)
        asset.refresh_status()
