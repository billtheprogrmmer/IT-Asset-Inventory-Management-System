from django.contrib.auth import views as auth_views
from django.urls import path

from . import views as v

urlpatterns = [
    # authentication
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    path("", v.DashboardView.as_view(), name="dashboard"),

    # assets
    path("assets/", v.AssetList.as_view(), name="asset_list"),
    path("assets/add/", v.AssetCreate.as_view(), name="asset_add"),
    path("assets/<int:pk>/", v.AssetDetail.as_view(), name="asset_detail"),
    path("assets/<int:pk>/edit/", v.AssetUpdate.as_view(), name="asset_edit"),
    path("assets/<int:pk>/delete/", v.AssetDelete.as_view(), name="asset_delete"),
    path("assets/<int:pk>/label/", v.AssetLabel.as_view(), name="asset_label"),

    # employees
    path("employees/", v.EmployeeList.as_view(), name="employee_list"),
    path("employees/add/", v.EmployeeCreate.as_view(), name="employee_add"),
    path("employees/<int:pk>/", v.EmployeeDetail.as_view(), name="employee_detail"),
    path("employees/<int:pk>/edit/", v.EmployeeUpdate.as_view(), name="employee_edit"),
    path("employees/<int:pk>/delete/", v.EmployeeDelete.as_view(), name="employee_delete"),

    # assignments
    path("assignments/", v.AssignmentList.as_view(), name="assignment_list"),
    path("assignments/add/", v.AssignmentCreate.as_view(), name="assignment_add"),
    path("assignments/<int:pk>/", v.AssignmentDetail.as_view(), name="assignment_detail"),
    path("assignments/<int:pk>/return/", v.AssignmentReturn.as_view(), name="assignment_return"),
    path("assignments/<int:pk>/delete/", v.AssignmentDelete.as_view(), name="assignment_delete"),

    # maintenance
    path("maintenance/", v.MaintenanceList.as_view(), name="maintenance_list"),
    path("maintenance/add/", v.MaintenanceCreate.as_view(), name="maintenance_add"),
    path("maintenance/<int:pk>/", v.MaintenanceDetail.as_view(), name="maintenance_detail"),
    path("maintenance/<int:pk>/edit/", v.MaintenanceUpdate.as_view(), name="maintenance_edit"),
    path("maintenance/<int:pk>/delete/", v.MaintenanceDelete.as_view(), name="maintenance_delete"),

    # lookups
    path("locations/", v.LocationList.as_view(), name="location_list"),
    path("locations/add/", v.LocationCreate.as_view(), name="location_add"),
    path("locations/<int:pk>/", v.LocationDetail.as_view(), name="location_detail"),
    path("locations/<int:pk>/edit/", v.LocationUpdate.as_view(), name="location_edit"),
    path("locations/<int:pk>/delete/", v.LocationDelete.as_view(), name="location_delete"),
    path("categories/", v.CategoryList.as_view(), name="category_list"),
    path("categories/add/", v.CategoryCreate.as_view(), name="category_add"),
    path("categories/<int:pk>/edit/", v.CategoryUpdate.as_view(), name="category_edit"),
    path("categories/<int:pk>/delete/", v.CategoryDelete.as_view(), name="category_delete"),
    path("departments/", v.DepartmentList.as_view(), name="department_list"),
    path("departments/add/", v.DepartmentCreate.as_view(), name="department_add"),
    path("departments/<int:pk>/edit/", v.DepartmentUpdate.as_view(), name="department_edit"),
    path("departments/<int:pk>/delete/", v.DepartmentDelete.as_view(), name="department_delete"),

    # reports
    path("reports/", v.ReportView.as_view(), name="reports"),
]
