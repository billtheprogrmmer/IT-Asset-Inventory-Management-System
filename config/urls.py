from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "ITAIMS Administration"
admin.site.site_title = "ITAIMS Admin"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("inventory.urls")),
]
