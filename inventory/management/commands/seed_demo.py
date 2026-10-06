from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from inventory.models import (Asset, Assignment, Category, Department, Employee,
                              Location, Maintenance)


class Command(BaseCommand):
    help = "Fill the database with sample data and three demo users."

    def handle(self, *args, **options):
        if Asset.objects.exists():
            self.stdout.write("Data already present - nothing added.")
            return

        call_command("setup_roles", verbosity=0)
        today = timezone.localdate()
        d = lambda days: today + timedelta(days=days)

        # ---- users -----------------------------------------------------
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@example.com", "admin12345")
        for username, role in (("itstaff", "IT Staff"), ("viewer", "Viewer")):
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password(f"{username}12345")
                user.save()
            user.groups.add(Group.objects.get(name=role))

        # ---- lookups ---------------------------------------------------
        cats = {n: Category.objects.create(name=n, description=x) for n, x in [
            ("Laptop", "Portable computers"), ("Desktop", "Desktop computers"),
            ("Printer", "Printers and scanners"), ("Router", "Routers and gateways"),
            ("Switch", "Network switches"), ("Monitor", "Displays"),
            ("Server", "Rack and tower servers"), ("Access Point", "Wireless access points"),
        ]}
        locs = {n: Location.objects.create(name=n, building=b, floor=f) for n, b, f in [
            ("IT Store", "Main Building", "Ground"), ("Server Room", "Main Building", "1"),
            ("Accounts Office", "Main Building", "2"), ("HR Office", "Annex", "1"),
            ("Reception", "Main Building", "Ground"), ("Operations Floor", "Annex", "2"),
        ]}
        deps = {n: Department.objects.create(name=n) for n in
                ["IT", "Accounts", "Human Resources", "Operations", "Administration"]}

        # ---- employees ---------------------------------------------------
        emp_rows = [
            ("STF-001", "Adaeze Okonkwo", "adaeze.okonkwo@example.com", "IT", "Systems Administrator"),
            ("STF-002", "Tunde Bakare", "tunde.bakare@example.com", "Accounts", "Senior Accountant"),
            ("STF-003", "Chiamaka Eze", "chiamaka.eze@example.com", "Human Resources", "HR Officer"),
            ("STF-004", "Ibrahim Musa", "ibrahim.musa@example.com", "Operations", "Operations Lead"),
            ("STF-005", "Funke Adeyemi", "funke.adeyemi@example.com", "Administration", "Receptionist"),
            ("STF-006", "Emeka Nwosu", "emeka.nwosu@example.com", "IT", "Network Engineer"),
            ("STF-007", "Halima Yusuf", "halima.yusuf@example.com", "Accounts", "Accounts Assistant"),
        ]
        emps = {row[0]: Employee.objects.create(
            staff_id=row[0], full_name=row[1], email=row[2], department=deps[row[3]], job_title=row[4]
        ) for row in emp_rows}
        Employee.objects.create(staff_id="STF-008", full_name="Segun Ogunleye", department=deps["Operations"],
                                job_title="Driver / Dispatcher", is_active=False)

        # ---- assets ------------------------------------------------------
        A = Asset.Condition
        rows = [
            # name, cat, brand, model, serial, bought(days ago), cost, warranty(days from today), loc, cond
            ("HP EliteBook 840 G8", "Laptop", "HP", "EliteBook 840 G8", "5CG1234A01", 420, 850000, 310, "IT Store", A.GOOD),
            ("Dell Latitude 5420", "Laptop", "Dell", "Latitude 5420", "DL5420-7781", 300, 780000, 430, "IT Store", A.NEW),
            ("Lenovo ThinkPad T14", "Laptop", "Lenovo", "ThinkPad T14", "PF3XK901", 700, 720000, 25, "IT Store", A.GOOD),
            ("Dell OptiPlex 7090", "Desktop", "Dell", "OptiPlex 7090", "OPT7090-3321", 500, 640000, 230, "Accounts Office", A.GOOD),
            ("HP ProDesk 400 G7", "Desktop", "HP", "ProDesk 400 G7", "PD400-9912", 520, 560000, 210, "HR Office", A.GOOD),
            ("HP LaserJet Pro M404dn", "Printer", "HP", "LaserJet Pro M404dn", "VNB3K11223", 380, 310000, 350, "Accounts Office", A.GOOD),
            ("Canon imageRUNNER 2625i", "Printer", "Canon", "iR 2625i", "CN2625-5510", 900, 1250000, -100, "Operations Floor", A.FAIR),
            ("MikroTik RB4011", "Router", "MikroTik", "RB4011iGS+", "MT4011-1187", 600, 210000, 130, "Server Room", A.GOOD),
            ("Cisco Catalyst 2960-X", "Switch", "Cisco", "WS-C2960X-24TS", "FOC2211X0AB", 1100, 950000, -20, "Server Room", A.GOOD),
            ("TP-Link EAP245", "Access Point", "TP-Link", "EAP245", "TPL-EAP-4432", 250, 68000, 480, "Operations Floor", A.NEW),
            ("Dell P2422H Monitor", "Monitor", "Dell", "P2422H", "CN0P2422-101", 480, 145000, 250, "Accounts Office", A.GOOD),
            ("Dell P2422H Monitor", "Monitor", "Dell", "P2422H", "CN0P2422-102", 480, 145000, 250, "IT Store", A.GOOD),
            ("Dell PowerEdge T40", "Server", "Dell", "PowerEdge T40", "PET40-6673", 800, 1450000, 60, "Server Room", A.GOOD),
            ("HP ProBook 450 G8", "Laptop", "HP", "ProBook 450 G8", "5CD2298B7", 610, 690000, 120, "Reception", A.FAIR),
            ("Epson L3250 Printer", "Printer", "Epson", "L3250", "EPL3250-8890", 150, 185000, 580, "HR Office", A.NEW),
            ("Old Dell Vostro 3500", "Laptop", "Dell", "Vostro 3500", "VOS3500-0021", 1500, 420000, -900, "IT Store", A.POOR),
        ]
        assets = {}
        for name, cat, brand, model, serial, bought, cost, warranty, loc, cond in rows:
            asset = Asset.objects.create(
                name=name, category=cats[cat], brand=brand, model_name=model, serial_number=serial,
                purchase_date=d(-bought), purchase_cost=cost, warranty_expiry=d(warranty),
                location=locs[loc], condition=cond,
            )
            assets[serial] = asset

        # ---- assignments -------------------------------------------------
        def assign(serial, staff, days_ago, due=None, returned=None):
            a = assets[serial]
            Assignment.objects.create(
                asset=a, employee=emps[staff], assigned_date=d(-days_ago), expected_return_date=due,
                returned_date=returned, condition_on_assign=a.condition,
                condition_on_return=a.condition if returned else "",
                assigned_by=User.objects.get(username="admin"),
            )

        assign("OPT7090-3321", "STF-002", 480)
        assign("PD400-9912", "STF-003", 500)
        assign("5CD2298B7", "STF-005", 400)
        assign("CN0P2422-101", "STF-002", 470)
        assign("5CG1234A01", "STF-004", 60, due=d(-10))          # overdue
        assign("PF3XK901", "STF-006", 120, due=d(90))
        assign("MT4011-1187", "STF-001", 300)
        assign("DL5420-7781", "STF-007", 200, returned=d(-150))   # history
        assign("VOS3500-0021", "STF-004", 1000, returned=d(-400))

        # ---- maintenance -------------------------------------------------
        def maint(serial, kind, text, tech, status, ago, cost=None, done=None):
            Maintenance.objects.create(
                asset=assets[serial], kind=kind, description=text, technician=tech, status=status,
                date_reported=d(-ago), date_completed=done, cost=cost,
            )

        maint("CN2625-5510", "repair", "Paper jam and drum unit replacement.", "OfficeTech Nigeria", "in_progress", 3, 45000)
        maint("FOC2211X0AB", "preventive", "Firmware update and fan cleaning.", "Emeka Nwosu", "scheduled", -5)
        maint("PET40-6673", "upgrade", "RAM upgrade from 16GB to 32GB.", "Emeka Nwosu", "completed", 90, 62000, d(-88))
        maint("VNB3K11223", "repair", "Replaced fuser assembly.", "PrintCare Ltd", "completed", 200, 38000, d(-196))

        self.stdout.write(self.style.SUCCESS("Demo data created."))
        self.stdout.write("Logins -> admin/admin12345 (Admin), itstaff/itstaff12345 (IT Staff), viewer/viewer12345 (Viewer)")
