from django import forms
from django.utils import timezone

from .models import (Asset, Assignment, Category, Department, Employee, Location,
                     Maintenance)


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        kwargs.setdefault("format", "%Y-%m-%d")
        super().__init__(**kwargs)


class StyledFormMixin:
    """Adds the CSS classes the templates expect to every field."""

    def _style_fields(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "check")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "input select")
            else:
                widget.attrs.setdefault("class", "input")
            if isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("rows", 3)


class StyledModelForm(StyledFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class StyledForm(StyledFormMixin, forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


# ---------------------------------------------------------------- lookups
class CategoryForm(StyledModelForm):
    class Meta:
        model = Category
        fields = ["name", "description"]


class LocationForm(StyledModelForm):
    class Meta:
        model = Location
        fields = ["name", "building", "floor", "description"]


class DepartmentForm(StyledModelForm):
    class Meta:
        model = Department
        fields = ["name"]


# -------------------------------------------------------------- employees
class EmployeeForm(StyledModelForm):
    class Meta:
        model = Employee
        fields = ["staff_id", "full_name", "email", "phone", "department", "job_title", "is_active"]


# ----------------------------------------------------------------- assets
class AssetForm(StyledModelForm):
    class Meta:
        model = Asset
        fields = [
            "name", "category", "brand", "model_name", "serial_number",
            "purchase_date", "purchase_cost", "warranty_expiry",
            "status", "condition", "location", "notes",
        ]
        widgets = {
            "purchase_date": DateInput(),
            "warranty_expiry": DateInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Assigned and In-maintenance are set automatically by the system,
        # so they are not offered when a person edits the asset by hand.
        automatic = {Asset.Status.ASSIGNED, Asset.Status.MAINTENANCE}
        current = self.instance.status if self.instance.pk else None
        if current not in automatic:
            self.fields["status"].choices = [c for c in Asset.Status.choices if c[0] not in automatic]
        else:
            self.fields["status"].disabled = True
            self.fields["status"].help_text = "Status changes automatically while the asset is assigned or in maintenance."

    def clean(self):
        data = super().clean()
        purchase, warranty = data.get("purchase_date"), data.get("warranty_expiry")
        if purchase and warranty and warranty < purchase:
            self.add_error("warranty_expiry", "Warranty cannot expire before the purchase date.")
        return data


# ------------------------------------------------------------ assignments
class AssignmentForm(StyledModelForm):
    class Meta:
        model = Assignment
        fields = ["asset", "employee", "assigned_date", "expected_return_date", "condition_on_assign", "notes"]
        widgets = {
            "assigned_date": DateInput(),
            "expected_return_date": DateInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset"].queryset = Asset.objects.filter(status=Asset.Status.AVAILABLE).order_by("asset_tag")
        self.fields["employee"].queryset = Employee.objects.filter(is_active=True)
        self.fields["asset"].empty_label = "Choose an available asset"
        self.fields["employee"].empty_label = "Choose an employee"


class ReturnForm(StyledModelForm):
    class Meta:
        model = Assignment
        fields = ["returned_date", "condition_on_return", "notes"]
        widgets = {"returned_date": DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["returned_date"].required = True
        self.fields["returned_date"].initial = timezone.localdate()
        self.fields["condition_on_return"].required = True
        self.fields["condition_on_return"].choices = [("", "Choose condition")] + list(Asset.Condition.choices)


# ------------------------------------------------------------ maintenance
class MaintenanceForm(StyledModelForm):
    class Meta:
        model = Maintenance
        fields = ["asset", "kind", "description", "technician", "cost", "date_reported", "date_completed", "status"]
        widgets = {
            "date_reported": DateInput(),
            "date_completed": DateInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset"].queryset = Asset.objects.exclude(
            status__in=[Asset.Status.RETIRED, Asset.Status.LOST]
        ).order_by("asset_tag")


# ---------------------------------------------------------------- filters
class AssetFilterForm(StyledForm):
    q = forms.CharField(required=False, label="Search",
                        widget=forms.TextInput(attrs={"placeholder": "Tag, name, serial number or brand"}))
    category = forms.ModelChoiceField(Category.objects.all(), required=False, empty_label="All categories")
    status = forms.ChoiceField(required=False, choices=[("", "All statuses")] + list(Asset.Status.choices))
    location = forms.ModelChoiceField(Location.objects.all(), required=False, empty_label="All locations")
    condition = forms.ChoiceField(required=False, choices=[("", "Any condition")] + list(Asset.Condition.choices))


class EmployeeFilterForm(StyledForm):
    q = forms.CharField(required=False, label="Search",
                        widget=forms.TextInput(attrs={"placeholder": "Name, staff ID or email"}))
    department = forms.ModelChoiceField(Department.objects.all(), required=False, empty_label="All departments")
    active = forms.ChoiceField(required=False, choices=[("", "Active and inactive"), ("1", "Active only"), ("0", "Inactive only")])


class AssignmentFilterForm(StyledForm):
    q = forms.CharField(required=False, label="Search",
                        widget=forms.TextInput(attrs={"placeholder": "Asset tag, asset name or employee"}))
    state = forms.ChoiceField(required=False, choices=[
        ("", "All assignments"), ("active", "Currently assigned"),
        ("overdue", "Overdue for return"), ("returned", "Returned"),
    ])


class MaintenanceFilterForm(StyledForm):
    q = forms.CharField(required=False, label="Search",
                        widget=forms.TextInput(attrs={"placeholder": "Asset tag, asset name or technician"}))
    status = forms.ChoiceField(required=False, choices=[("", "All statuses")] + list(Maintenance.Status.choices))
    kind = forms.ChoiceField(required=False, choices=[("", "All types")] + list(Maintenance.Kind.choices))


class ReportFilterForm(StyledForm):
    REPORTS = [
        ("inventory", "Asset inventory"),
        ("assignments", "Assignment history"),
        ("maintenance", "Maintenance log"),
        ("warranty", "Warranty expiring within 90 days"),
    ]
    report = forms.ChoiceField(choices=REPORTS)
    category = forms.ModelChoiceField(Category.objects.all(), required=False, empty_label="All categories")
    status = forms.ChoiceField(required=False, choices=[("", "All statuses")] + list(Asset.Status.choices))
    location = forms.ModelChoiceField(Location.objects.all(), required=False, empty_label="All locations")
    date_from = forms.DateField(required=False, widget=DateInput(), label="From")
    date_to = forms.DateField(required=False, widget=DateInput(), label="To")
