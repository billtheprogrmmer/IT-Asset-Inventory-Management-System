from django.contrib import admin

from .models import (Asset, Assignment, Category, Department, Employee, Location,
                     LocationHistory, Maintenance)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("asset_tag", "name", "category", "status", "location", "serial_number")
    list_filter = ("status", "category", "location")
    search_fields = ("asset_tag", "name", "serial_number", "brand")
    readonly_fields = ("asset_tag",)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("full_name", "staff_id", "department", "is_active")
    list_filter = ("department", "is_active")
    search_fields = ("full_name", "staff_id", "email")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("asset", "employee", "assigned_date", "expected_return_date", "returned_date")
    list_filter = ("assigned_date",)
    search_fields = ("asset__asset_tag", "employee__full_name")


@admin.register(Maintenance)
class MaintenanceAdmin(admin.ModelAdmin):
    list_display = ("asset", "kind", "status", "technician", "date_reported", "cost")
    list_filter = ("status", "kind")


admin.site.register(Category)
admin.site.register(Location)
admin.site.register(Department)
admin.site.register(LocationHistory)
