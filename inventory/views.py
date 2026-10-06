import csv
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count, Q, Sum
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import (CreateView, DeleteView, DetailView, ListView,
                                  TemplateView, UpdateView)

from .forms import (AssetFilterForm, AssetForm, AssignmentFilterForm, AssignmentForm,
                    CategoryForm, DepartmentForm, EmployeeFilterForm, EmployeeForm,
                    LocationForm, MaintenanceFilterForm, MaintenanceForm, ReportFilterForm,
                    ReturnForm)
from .models import (Asset, Assignment, Category, Department, Employee, Location,
                     Maintenance)


# =====================================================================
#  Base classes: every screen requires a login AND the right permission
# =====================================================================
class ModelPermissionMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Checks Django's built-in model permission (view/add/change/delete).

    Roles are groups of these permissions - see the `setup_roles` command.
    """

    perm_action = "view"

    def get_permission_required(self):
        opts = self.model._meta
        return [f"{opts.app_label}.{self.perm_action}_{opts.model_name}"]


class BaseList(ModelPermissionMixin, ListView):
    template_name = "inventory/list.html"
    paginate_by = settings.ITEMS_PER_PAGE
    title = ""
    subtitle = ""
    columns = []
    filter_form_class = None
    add_label = "Add"
    add_url = None
    edit_url = None
    delete_url = None
    row_action_url = None      # optional extra link per row, e.g. "Return"
    row_action_label = ""
    row_action_if = ""         # attribute that must be true for the link to show
    empty_message = "Nothing here yet."

    def get_filter_form(self):
        if not self.filter_form_class:
            return None
        return self.filter_form_class(self.request.GET or None)

    def apply_filters(self, queryset, data):
        return queryset

    def get_queryset(self):
        queryset = super().get_queryset()
        form = self.get_filter_form()
        if form is not None and form.is_valid():
            queryset = self.apply_filters(queryset, form.cleaned_data)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        opts = self.model._meta
        user = self.request.user
        context.update(
            title=self.title, subtitle=self.subtitle, columns=self.columns,
            filter_form=self.get_filter_form(), add_label=self.add_label,
            add_url=self.add_url, edit_url=self.edit_url, delete_url=self.delete_url,
            empty_message=self.empty_message,
            row_action_url=self.row_action_url, row_action_label=self.row_action_label,
            row_action_if=self.row_action_if,
            can_add=user.has_perm(f"inventory.add_{opts.model_name}"),
            can_change=user.has_perm(f"inventory.change_{opts.model_name}"),
            can_delete=user.has_perm(f"inventory.delete_{opts.model_name}"),
            total_count=context["paginator"].count if context.get("paginator") else 0,
        )
        return context


class BaseCreate(ModelPermissionMixin, SuccessMessageMixin, CreateView):
    perm_action = "add"
    template_name = "inventory/form.html"
    title = ""
    submit_label = "Save"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(title=self.title, submit_label=self.submit_label, cancel_url=self.get_cancel_url())
        return context

    def get_cancel_url(self):
        return str(self.success_url) if self.success_url else "/"


class BaseUpdate(ModelPermissionMixin, SuccessMessageMixin, UpdateView):
    perm_action = "change"
    template_name = "inventory/form.html"
    title = ""
    submit_label = "Save changes"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(title=self.title, submit_label=self.submit_label, cancel_url=self.get_cancel_url())
        return context

    def get_cancel_url(self):
        return str(self.success_url) if self.success_url else "/"


class BaseDelete(ModelPermissionMixin, DeleteView):
    perm_action = "delete"
    template_name = "inventory/confirm_delete.html"
    protected_message = "This record is still used elsewhere, so it cannot be deleted."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cancel_url"] = str(self.success_url)
        return context

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, self.protected_message)
            return redirect(str(self.success_url))
        messages.success(self.request, "Deleted.")
        return response


# =====================================================================
#  Dashboard
# =====================================================================
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "inventory/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        assets = Asset.objects.all()
        total = assets.count()

        counts = dict(assets.values_list("status").annotate(n=Count("id")))
        status_rows = []
        for value, label in Asset.Status.choices:
            n = counts.get(value, 0)
            status_rows.append({
                "value": value, "label": label, "count": n,
                "percent": round(n * 100 / total, 1) if total else 0,
            })

        by_category = list(
            Category.objects.annotate(n=Count("assets")).filter(n__gt=0).order_by("-n", "name")[:8]
        )
        by_location = list(
            Location.objects.annotate(n=Count("assets")).filter(n__gt=0).order_by("-n", "name")[:6]
        )
        top_category = by_category[0].n if by_category else 0
        top_location = by_location[0].n if by_location else 0

        context.update(
            total=total,
            available=counts.get("available", 0),
            assigned=counts.get("assigned", 0),
            in_maintenance=counts.get("maintenance", 0),
            employee_count=Employee.objects.filter(is_active=True).count(),
            total_value=assets.exclude(status__in=["retired", "lost"]).aggregate(s=Sum("purchase_cost"))["s"] or 0,
            status_rows=status_rows,
            by_category=[{"obj": c, "percent": round(c.n * 100 / top_category)} for c in by_category],
            by_location=[{"obj": l, "percent": round(l.n * 100 / top_location)} for l in by_location],
            overdue=Assignment.objects.filter(returned_date__isnull=True, expected_return_date__lt=today)
                    .select_related("asset", "employee").order_by("expected_return_date")[:5],
            warranty_soon=assets.filter(warranty_expiry__gte=today, warranty_expiry__lte=today + timedelta(days=60))
                          .exclude(status__in=["retired", "lost"]).order_by("warranty_expiry")[:5],
            open_maintenance=Maintenance.objects.exclude(status="completed")
                             .select_related("asset").order_by("date_reported")[:5],
            recent_assignments=Assignment.objects.select_related("asset", "employee")[:6],
            today=today,
        )
        return context


# =====================================================================
#  Categories, Locations, Departments
# =====================================================================
class CategoryList(BaseList):
    model = Category
    title = "Categories"
    subtitle = "Types of equipment you keep track of."
    add_label = "Add category"
    add_url, edit_url, delete_url = "category_add", "category_edit", "category_delete"
    columns = [
        {"label": "Name", "field": "name"},
        {"label": "Description", "field": "description"},
        {"label": "Assets", "field": "asset_count", "align": "right"},
    ]

    def get_queryset(self):
        return super().get_queryset().annotate(asset_count=Count("assets")).order_by("name")


class CategoryCreate(BaseCreate):
    model, form_class = Category, CategoryForm
    title, success_url, success_message = "Add category", reverse_lazy("category_list"), "Category added."


class CategoryUpdate(BaseUpdate):
    model, form_class = Category, CategoryForm
    title, success_url, success_message = "Edit category", reverse_lazy("category_list"), "Category updated."


class CategoryDelete(BaseDelete):
    model, success_url = Category, reverse_lazy("category_list")
    protected_message = "Assets still use this category, so it cannot be deleted."


class LocationList(BaseList):
    model = Location
    title = "Locations"
    subtitle = "Rooms, offices and stores where assets are kept."
    add_label = "Add location"
    add_url, edit_url, delete_url = "location_add", "location_edit", "location_delete"
    columns = [
        {"label": "Location", "field": "name", "link": "location_detail"},
        {"label": "Building", "field": "building"},
        {"label": "Floor", "field": "floor"},
        {"label": "Assets", "field": "asset_count", "align": "right"},
    ]

    def get_queryset(self):
        return super().get_queryset().annotate(asset_count=Count("assets")).order_by("name")


class LocationDetail(ModelPermissionMixin, DetailView):
    model = Location
    template_name = "inventory/location_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["assets"] = self.object.assets.select_related("category")
        return context


class LocationCreate(BaseCreate):
    model, form_class = Location, LocationForm
    title, success_url, success_message = "Add location", reverse_lazy("location_list"), "Location added."


class LocationUpdate(BaseUpdate):
    model, form_class = Location, LocationForm
    title, success_url, success_message = "Edit location", reverse_lazy("location_list"), "Location updated."


class LocationDelete(BaseDelete):
    model, success_url = Location, reverse_lazy("location_list")


class DepartmentList(BaseList):
    model = Department
    title = "Departments"
    subtitle = "Used to group employees."
    add_label = "Add department"
    add_url, edit_url, delete_url = "department_add", "department_edit", "department_delete"
    columns = [
        {"label": "Name", "field": "name"},
        {"label": "Employees", "field": "employee_count", "align": "right"},
    ]

    def get_queryset(self):
        return super().get_queryset().annotate(employee_count=Count("employees")).order_by("name")


class DepartmentCreate(BaseCreate):
    model, form_class = Department, DepartmentForm
    title, success_url, success_message = "Add department", reverse_lazy("department_list"), "Department added."


class DepartmentUpdate(BaseUpdate):
    model, form_class = Department, DepartmentForm
    title, success_url, success_message = "Edit department", reverse_lazy("department_list"), "Department updated."


class DepartmentDelete(BaseDelete):
    model, success_url = Department, reverse_lazy("department_list")
    protected_message = "Employees still belong to this department, so it cannot be deleted."


# =====================================================================
#  Employees
# =====================================================================
class EmployeeList(BaseList):
    model = Employee
    title = "Employees"
    subtitle = "People who can be given equipment."
    add_label = "Add employee"
    add_url, edit_url, delete_url = "employee_add", "employee_edit", "employee_delete"
    filter_form_class = EmployeeFilterForm
    columns = [
        {"label": "Name", "field": "full_name", "link": "employee_detail"},
        {"label": "Staff ID", "field": "staff_id"},
        {"label": "Department", "field": "department.name"},
        {"label": "Job title", "field": "job_title"},
        {"label": "Assets held", "field": "held", "align": "right"},
        {"label": "Status", "field": "is_active", "kind": "active"},
    ]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("department").annotate(
            held=Count("assignments", filter=Q(assignments__returned_date__isnull=True))
        ).order_by("full_name")
        return queryset

    def apply_filters(self, qs, data):
        if data.get("q"):
            q = data["q"]
            qs = qs.filter(Q(full_name__icontains=q) | Q(staff_id__icontains=q) | Q(email__icontains=q))
        if data.get("department"):
            qs = qs.filter(department=data["department"])
        if data.get("active") in ("0", "1"):
            qs = qs.filter(is_active=data["active"] == "1")
        return qs


class EmployeeDetail(ModelPermissionMixin, DetailView):
    model = Employee
    template_name = "inventory/employee_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        history = self.object.assignments.select_related("asset")
        context["current"] = [a for a in history if a.is_active]
        context["past"] = [a for a in history if not a.is_active]
        return context


class EmployeeCreate(BaseCreate):
    model, form_class = Employee, EmployeeForm
    title, success_url, success_message = "Add employee", reverse_lazy("employee_list"), "Employee added."


class EmployeeUpdate(BaseUpdate):
    model, form_class = Employee, EmployeeForm
    title, success_message = "Edit employee", "Employee updated."

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_cancel_url(self):
        return self.object.get_absolute_url()


class EmployeeDelete(BaseDelete):
    model, success_url = Employee, reverse_lazy("employee_list")
    protected_message = "This employee has assignment history. Untick 'active' instead of deleting."


# =====================================================================
#  Assets
# =====================================================================
class AssetList(BaseList):
    model = Asset
    title = "Assets"
    subtitle = "Every piece of IT equipment in the organisation."
    add_label = "Add asset"
    add_url, edit_url, delete_url = "asset_add", "asset_edit", "asset_delete"
    filter_form_class = AssetFilterForm
    empty_message = "No assets match. Clear the filters or add a new asset."
    columns = [
        {"label": "Tag", "field": "asset_tag", "kind": "tag", "link": "asset_detail"},
        {"label": "Name", "field": "name"},
        {"label": "Category", "field": "category.name"},
        {"label": "Serial number", "field": "serial_number"},
        {"label": "Location", "field": "location.name"},
        {"label": "Status", "field": "status", "kind": "badge", "display": "get_status_display"},
    ]

    def get_queryset(self):
        return super().get_queryset().select_related("category", "location")

    def apply_filters(self, qs, data):
        if data.get("q"):
            q = data["q"]
            qs = qs.filter(
                Q(asset_tag__icontains=q) | Q(name__icontains=q) | Q(serial_number__icontains=q)
                | Q(brand__icontains=q) | Q(model_name__icontains=q)
            )
        for field in ("category", "location"):
            if data.get(field):
                qs = qs.filter(**{field: data[field]})
        for field in ("status", "condition"):
            if data.get(field):
                qs = qs.filter(**{field: data[field]})
        return qs


class AssetDetail(ModelPermissionMixin, DetailView):
    model = Asset
    template_name = "inventory/asset_detail.html"

    def get_queryset(self):
        return super().get_queryset().select_related("category", "location")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        asset = self.object
        context.update(
            current=asset.current_assignment,
            assignments=asset.assignments.select_related("employee")[:10],
            maintenance=asset.maintenance_records.all()[:10],
            movements=asset.location_history.select_related("from_location", "to_location")[:10],
        )
        return context


class AssetLabel(ModelPermissionMixin, DetailView):
    """A printable tag to stick on the equipment."""
    model = Asset
    template_name = "inventory/asset_label.html"


class AssetCreate(BaseCreate):
    model, form_class = Asset, AssetForm
    title, success_message = "Add asset", "Asset registered."

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_cancel_url(self):
        return reverse("asset_list")


class AssetUpdate(BaseUpdate):
    model, form_class = Asset, AssetForm
    title, success_message = "Edit asset", "Asset updated."

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_cancel_url(self):
        return self.object.get_absolute_url()


class AssetDelete(BaseDelete):
    model, success_url = Asset, reverse_lazy("asset_list")
    protected_message = "This asset has assignment history and cannot be deleted. Change its status to Retired instead."


# =====================================================================
#  Assignments
# =====================================================================
class AssignmentList(BaseList):
    model = Assignment
    title = "Assignments"
    subtitle = "Who has which asset, and when it came back."
    add_label = "Assign an asset"
    add_url, delete_url = "assignment_add", "assignment_delete"
    row_action_url, row_action_label, row_action_if = "assignment_return", "Return", "is_active"
    filter_form_class = AssignmentFilterForm
    empty_message = "No assignments match."
    columns = [
        {"label": "Asset", "field": "asset.asset_tag", "kind": "tag", "link": "assignment_detail"},
        {"label": "Name", "field": "asset.name"},
        {"label": "Assigned to", "field": "employee.full_name"},
        {"label": "Assigned", "field": "assigned_date", "kind": "date"},
        {"label": "Due back", "field": "expected_return_date", "kind": "date"},
        {"label": "Returned", "field": "returned_date", "kind": "date"},
        {"label": "State", "field": "state", "kind": "badge", "display": "state_label"},
    ]

    def get_queryset(self):
        return super().get_queryset().select_related("asset", "employee")

    def apply_filters(self, qs, data):
        today = timezone.localdate()
        if data.get("q"):
            q = data["q"]
            qs = qs.filter(
                Q(asset__asset_tag__icontains=q) | Q(asset__name__icontains=q)
                | Q(employee__full_name__icontains=q) | Q(employee__staff_id__icontains=q)
            )
        state = data.get("state")
        if state == "active":
            qs = qs.filter(returned_date__isnull=True)
        elif state == "overdue":
            qs = qs.filter(returned_date__isnull=True, expected_return_date__lt=today)
        elif state == "returned":
            qs = qs.filter(returned_date__isnull=False)
        return qs


class AssignmentDetail(ModelPermissionMixin, DetailView):
    model = Assignment
    template_name = "inventory/assignment_detail.html"

    def get_queryset(self):
        return super().get_queryset().select_related("asset", "employee", "assigned_by")


class AssignmentCreate(BaseCreate):
    model, form_class = Assignment, AssignmentForm
    title, submit_label = "Assign an asset", "Assign asset"
    success_url = reverse_lazy("assignment_list")
    success_message = "Asset assigned."

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get("asset"):
            initial["asset"] = self.request.GET["asset"]
        if self.request.GET.get("employee"):
            initial["employee"] = self.request.GET["employee"]
        return initial

    def form_valid(self, form):
        form.instance.assigned_by = self.request.user
        if not form.instance.condition_on_assign:
            form.instance.condition_on_assign = form.instance.asset.condition
        return super().form_valid(form)


class AssignmentReturn(ModelPermissionMixin, SuccessMessageMixin, UpdateView):
    """Records that an asset has come back."""
    model = Assignment
    perm_action = "change"
    form_class = ReturnForm
    template_name = "inventory/form.html"
    success_url = reverse_lazy("assignment_list")
    success_message = "Return recorded. The asset is available again."

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            assignment = self.get_object()
            if not assignment.is_active:
                messages.info(request, "This asset has already been returned.")
                return redirect(assignment)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        a = self.object
        context.update(
            title=f"Return {a.asset.asset_tag}",
            intro=f"{a.asset.name} was given to {a.employee.full_name} on {a.assigned_date:%d %b %Y}.",
            submit_label="Record return", cancel_url=a.get_absolute_url(),
        )
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        asset = self.object.asset
        asset.condition = self.object.condition_on_return
        asset.save(update_fields=["condition", "updated_at"])
        return response


class AssignmentDelete(BaseDelete):
    model, success_url = Assignment, reverse_lazy("assignment_list")

    def form_valid(self, form):
        asset = self.get_object().asset
        response = super().form_valid(form)
        asset.refresh_from_db()
        asset.refresh_status()
        return response


# =====================================================================
#  Maintenance
# =====================================================================
class MaintenanceList(BaseList):
    model = Maintenance
    title = "Maintenance"
    subtitle = "Repairs, servicing and upgrades."
    add_label = "Log maintenance"
    add_url, edit_url, delete_url = "maintenance_add", "maintenance_edit", "maintenance_delete"
    filter_form_class = MaintenanceFilterForm
    empty_message = "No maintenance records match."
    columns = [
        {"label": "Asset", "field": "asset.asset_tag", "kind": "tag", "link": "maintenance_detail"},
        {"label": "Name", "field": "asset.name"},
        {"label": "Type", "field": "get_kind_display"},
        {"label": "Technician", "field": "technician"},
        {"label": "Reported", "field": "date_reported", "kind": "date"},
        {"label": "Completed", "field": "date_completed", "kind": "date"},
        {"label": "Cost", "field": "cost", "kind": "money", "align": "right"},
        {"label": "Status", "field": "status", "kind": "badge", "display": "get_status_display"},
    ]

    def get_queryset(self):
        return super().get_queryset().select_related("asset")

    def apply_filters(self, qs, data):
        if data.get("q"):
            q = data["q"]
            qs = qs.filter(
                Q(asset__asset_tag__icontains=q) | Q(asset__name__icontains=q) | Q(technician__icontains=q)
            )
        if data.get("status"):
            qs = qs.filter(status=data["status"])
        if data.get("kind"):
            qs = qs.filter(kind=data["kind"])
        return qs


class MaintenanceDetail(ModelPermissionMixin, DetailView):
    model = Maintenance
    template_name = "inventory/maintenance_detail.html"

    def get_queryset(self):
        return super().get_queryset().select_related("asset")


class MaintenanceCreate(BaseCreate):
    model, form_class = Maintenance, MaintenanceForm
    title, success_url, success_message = "Log maintenance", reverse_lazy("maintenance_list"), "Maintenance logged."

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get("asset"):
            initial["asset"] = self.request.GET["asset"]
        return initial


class MaintenanceUpdate(BaseUpdate):
    model, form_class = Maintenance, MaintenanceForm
    title, success_message = "Edit maintenance record", "Maintenance record updated."

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_cancel_url(self):
        return self.object.get_absolute_url()


class MaintenanceDelete(BaseDelete):
    model, success_url = Maintenance, reverse_lazy("maintenance_list")


# =====================================================================
#  Reports
# =====================================================================
def build_report(data):
    """Return (title, headers, rows) for the chosen report."""
    kind = data["report"]
    today = timezone.localdate()
    date_from, date_to = data.get("date_from"), data.get("date_to")

    if kind == "inventory":
        qs = Asset.objects.select_related("category", "location")
        for field in ("category", "location", "status"):
            if data.get(field):
                qs = qs.filter(**{field: data[field]})
        headers = ["Tag", "Name", "Category", "Brand", "Model", "Serial number", "Status",
                   "Condition", "Location", "Purchase date", "Cost (NGN)", "Warranty expiry"]
        rows = [[a.asset_tag, a.name, a.category.name, a.brand, a.model_name, a.serial_number,
                 a.get_status_display(), a.get_condition_display(), a.location.name if a.location else "",
                 a.purchase_date or "", a.purchase_cost if a.purchase_cost is not None else "",
                 a.warranty_expiry or ""] for a in qs.order_by("asset_tag")]
        return "Asset inventory", headers, rows

    if kind == "assignments":
        qs = Assignment.objects.select_related("asset", "employee__department")
        if date_from:
            qs = qs.filter(assigned_date__gte=date_from)
        if date_to:
            qs = qs.filter(assigned_date__lte=date_to)
        headers = ["Tag", "Asset", "Employee", "Staff ID", "Department", "Assigned", "Due back", "Returned", "State"]
        rows = [[a.asset.asset_tag, a.asset.name, a.employee.full_name, a.employee.staff_id,
                 a.employee.department.name, a.assigned_date, a.expected_return_date or "",
                 a.returned_date or "", a.state_label] for a in qs]
        return "Assignment history", headers, rows

    if kind == "maintenance":
        qs = Maintenance.objects.select_related("asset")
        if date_from:
            qs = qs.filter(date_reported__gte=date_from)
        if date_to:
            qs = qs.filter(date_reported__lte=date_to)
        headers = ["Tag", "Asset", "Type", "Technician", "Reported", "Completed", "Status", "Cost (NGN)"]
        rows = [[m.asset.asset_tag, m.asset.name, m.get_kind_display(), m.technician, m.date_reported,
                 m.date_completed or "", m.get_status_display(), m.cost if m.cost is not None else ""] for m in qs]
        return "Maintenance log", headers, rows

    # warranty
    qs = Asset.objects.filter(warranty_expiry__gte=today, warranty_expiry__lte=today + timedelta(days=90)) \
        .select_related("category", "location").order_by("warranty_expiry")
    headers = ["Tag", "Name", "Category", "Serial number", "Location", "Warranty expiry", "Days left"]
    rows = [[a.asset_tag, a.name, a.category.name, a.serial_number, a.location.name if a.location else "",
             a.warranty_expiry, (a.warranty_expiry - today).days] for a in qs]
    return "Warranties expiring within 90 days", headers, rows


class ReportView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "inventory/reports.html"
    permission_required = "inventory.view_asset"

    def get(self, request, *args, **kwargs):
        form = ReportFilterForm(request.GET or None)
        if request.GET.get("export") == "csv" and form.is_valid():
            title, headers, rows = build_report(form.cleaned_data)
            response = HttpResponse(content_type="text/csv")
            filename = f"itaims-{form.cleaned_data['report']}-{timezone.localdate()}.csv"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            writer = csv.writer(response)
            writer.writerow(headers)
            writer.writerows(rows)
            return response

        context = self.get_context_data(form=form)
        if request.GET and form.is_valid():
            title, headers, rows = build_report(form.cleaned_data)
            context.update(report_title=title, headers=headers, rows=rows,
                           generated=timezone.localtime(), generated_by=request.user)
        return self.render_to_response(context)
