from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

ROLES = {
    # role name: actions allowed on every ITAIMS table
    "IT Admin": ["view", "add", "change", "delete"],
    "IT Staff": ["view", "add", "change"],
    "Viewer": ["view"],
}


class Command(BaseCommand):
    help = "Create the three ITAIMS roles (groups) and give each its permissions."

    def handle(self, *args, **options):
        for role, actions in ROLES.items():
            group, _ = Group.objects.get_or_create(name=role)
            perms = Permission.objects.filter(
                content_type__app_label="inventory",
                codename__regex=r"^(%s)_" % "|".join(actions),
            )
            group.permissions.set(perms)
            if options["verbosity"] > 0:
                self.stdout.write(self.style.SUCCESS(f"{role}: {perms.count()} permissions"))
