from datetime import datetime, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
import pytz

from league.models import Member, Gameweek, GameweekResult
from treasury.models import Payment, AuditLog
from league.services.payout_engine import calculate_gameweek_payouts
from league.services.fpl_client import FPLSyncService


SEED_MEMBERS = [
    {"fpl_entry_id": 3232174, "manager_name": "Marve Mathingu", "team_name": "Marve of the Match", "phone_number": "254712345601", "joined_gameweek": 1},
    {"fpl_entry_id": 2473672, "manager_name": "Samuel Wambua", "team_name": "maggry shiners fc", "phone_number": "254712345602", "joined_gameweek": 1},
    {"fpl_entry_id": 8619203, "manager_name": "Renny Muragu", "team_name": "The Young Ones", "phone_number": "254712345603", "joined_gameweek": 1},
    {"fpl_entry_id": 3079178, "manager_name": "Torque Dennis", "team_name": "DenniSkills", "phone_number": "254712345604", "joined_gameweek": 1},
    {"fpl_entry_id": 5249838, "manager_name": "King Chris", "team_name": "The_Painter..", "phone_number": "254712345605", "joined_gameweek": 1},
    {"fpl_entry_id": 6866748, "manager_name": "Erick Muchira", "team_name": "mambaaa", "phone_number": "254712345606", "joined_gameweek": 1},
    {"fpl_entry_id": 2853582, "manager_name": "Benn Mwangi", "team_name": "Benn's Team", "phone_number": "254712345607", "joined_gameweek": 1},
    {"fpl_entry_id": 5622265, "manager_name": "Bright Ottore", "team_name": "Phill Me In FC", "phone_number": "254712345608", "joined_gameweek": 1},
    {"fpl_entry_id": 3271390, "manager_name": "Marvin Owino", "team_name": "Don Bosco", "phone_number": "254712345609", "joined_gameweek": 1},
    {"fpl_entry_id": 9266887, "manager_name": "Aron Mangati", "team_name": "Arons", "phone_number": "254712345610", "joined_gameweek": 2},
]

GW1_SCORES = {
    3232174: {"pts": 61, "hits": 0, "rank": 1605173},
    2473672: {"pts": 56, "hits": 0, "rank": 2401920},
    8619203: {"pts": 55, "hits": 0, "rank": 2600140},
    3079178: {"pts": 52, "hits": 0, "rank": 3205010},
    5249838: {"pts": 50, "hits": 0, "rank": 3701200},
    6866748: {"pts": 50, "hits": 0, "rank": 3701200},
    2853582: {"pts": 47, "hits": 0, "rank": 4400500},
    5622265: {"pts": 45, "hits": 0, "rank": 4900200},
    3271390: {"pts": 36, "hits": 0, "rank": 6800100},
    9266887: {"pts": 0, "hits": 0, "rank": 0},
}


class Command(BaseCommand):
    help = "Seeds all 10 members, Gameweek schedule, GW1 results, realistic M-Pesa payments and late fines."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting FPL Boys Database Seeding..."))

        # 1. First attempt to sync calendar from live FPL API, or fallback to full 38 GW calendar
        service = FPLSyncService()
        gws = service.sync_gameweeks()
        if not gws:
            self.stdout.write("Live API unavailable, creating 38 Gameweeks offline...")
            start_date = timezone.datetime(2026, 8, 21, 17, 30, tzinfo=pytz.UTC)
            for num in range(1, 39):
                dl = start_date + timedelta(days=(num - 1) * 7)
                status = 'finished' if num == 1 else ('active' if num == 2 else 'upcoming')
                Gameweek.objects.update_or_create(
                    number=num,
                    defaults={
                        'name': f"Gameweek {num}",
                        'deadline_time': dl,
                        'status': status,
                        'is_current': (num == 2),
                        'is_next': (num == 3),
                        'month': dl.month,
                        'prize_pool_amount': Decimal('500.00'),
                    }
                )

        # 2. Seed Members
        self.stdout.write("Seeding 10 Members with contact information...")
        member_objs = []
        for m_data in SEED_MEMBERS:
            m, _ = Member.objects.update_or_create(
                fpl_entry_id=m_data['fpl_entry_id'],
                defaults={
                    'manager_name': m_data['manager_name'],
                    'team_name': m_data['team_name'],
                    'phone_number': m_data['phone_number'],
                    'joined_gameweek': m_data.get('joined_gameweek', 1),
                    'is_active': True,
                }
            )
            member_objs.append(m)

        self.stdout.write(self.style.SUCCESS(f"-> Seeded {len(member_objs)} members."))

        # 3. Seed GW 1 Results
        gw1 = Gameweek.objects.filter(number=1).first()
        if gw1:
            gw1.status = 'finished'
            gw1.save()

            self.stdout.write("Seeding GW 1 scores and calculating top 3 payouts...")
            for m in member_objs:
                score_info = GW1_SCORES.get(m.fpl_entry_id, {"pts": 40, "hits": 0, "rank": 5000000})
                GameweekResult.objects.update_or_create(
                    member=m,
                    gameweek=gw1,
                    defaults={
                        'gw_points': score_info['pts'],
                        'transfer_cost': score_info['hits'],
                        'net_points': score_info['pts'] - score_info['hits'],
                        'overall_rank': score_info['rank'],
                    }
                )

            # Trigger payout engine
            calculate_gameweek_payouts(gw1)
            self.stdout.write(self.style.SUCCESS("-> GW 1 payouts calculated and saved."))

            # 4. Seed Realistic Payments for GW 1
            # Deadline was 2026-08-21 17:30 UTC
            deadline = gw1.deadline_time
            on_time_time = deadline - timedelta(hours=4)
            late_time = deadline + timedelta(hours=3)

            # 7 on-time (Ksh. 150)
            # 2 late (Ksh. 200, Ksh. 50 fine)
            # 1 unpaid
            self.stdout.write("Seeding realistic M-Pesa payments for GW 1...")

            on_time_members = member_objs[:7]
            late_members = member_objs[7:9]
            unpaid_member = member_objs[9]  # Aron Mangati (joined recently)

            mpesa_prefixes = ["QJH7829", "QJH8930", "QJH9041", "QJH1152", "QJH2263", "QJH3374", "QJH4485", "QJH5596", "QJH6607"]

            for idx, m in enumerate(on_time_members):
                Payment.objects.update_or_create(
                    member=m,
                    gameweek=gw1,
                    defaults={
                        'amount_paid': Decimal('150.00'),
                        'timestamp_received': on_time_time + timedelta(minutes=idx * 25),
                        'mpesa_code': f"{mpesa_prefixes[idx]}KL",
                        'verified': True,
                        'is_late': False,
                        'late_fine_amount': Decimal('0.00'),
                        'notes': "Paid via M-Pesa on time",
                    }
                )

            for idx, m in enumerate(late_members, start=7):
                Payment.objects.update_or_create(
                    member=m,
                    gameweek=gw1,
                    defaults={
                        'amount_paid': Decimal('200.00'),
                        'timestamp_received': late_time + timedelta(minutes=(idx - 7) * 40),
                        'mpesa_code': f"{mpesa_prefixes[idx]}LM",
                        'verified': True,
                        'is_late': True,
                        'late_fine_amount': Decimal('50.00'),
                        'notes': "Late payment after GW1 deadline (+50 fine into BBQ pot)",
                    }
                )

            # Ensure unpaid member has no payment for GW1
            Payment.objects.filter(member=unpaid_member, gameweek=gw1).delete()

            AuditLog.objects.create(
                action='PAYMENT_CREATED',
                description=f"Initial seed payments recorded for GW 1 (7 on-time, 2 late with fines, 1 unpaid defaulter: {unpaid_member.manager_name}).",
                performed_by='SeedDataCommand'
            )

        self.stdout.write(self.style.SUCCESS("\n[SUCCESS] Seed data completed successfully!"))
