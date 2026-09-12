import pytz
from datetime import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from league.models import Member, Gameweek, GameweekResult
from league.services.fpl_client import FPLSyncService
from league.services.payout_engine import calculate_gameweek_payouts
from treasury.models import Payment, PaymentTransaction, PrizePayout, AuditLog
from treasury.services.payment_allocation import allocate_payment_with_rollover, get_member_available_prize_balance


class Command(BaseCommand):
    help = "Clears all payment and payout records, and re-seeds verified actual M-Pesa payments in sequential FIFO order."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Starting treasury & payments database clean reset..."))

        eat_tz = pytz.timezone('Africa/Nairobi')

        with transaction.atomic():
            # 1. Clear all existing payments, transactions, prize payouts, and payment audit logs
            p_count = Payment.objects.count()
            tx_count = PaymentTransaction.objects.count()
            po_count = PrizePayout.objects.count()

            Payment.objects.all().delete()
            PaymentTransaction.objects.all().delete()
            PrizePayout.objects.all().delete()
            AuditLog.objects.filter(action__in=['PAYMENT_CREATED', 'PAYMENT_DELETED', 'PRIZE_DISBURSED', 'PRIZE_REINVESTED']).delete()

            self.stdout.write(self.style.SUCCESS(f"Deleted {p_count} payments, {tx_count} transactions, and {po_count} prize payouts."))

            # 2. Ensure members and gameweeks are synced and payouts computed
            members_by_name = {m.manager_name.lower(): m for m in Member.objects.all()}
            if not members_by_name:
                self.stdout.write("Syncing members from FPL...")
                sync = FPLSyncService()
                sync.sync_members()
                sync.sync_gameweek_results()
                members_by_name = {m.manager_name.lower(): m for m in Member.objects.all()}

            # Ensure payout calculations are fresh for finished gameweeks
            for gw in Gameweek.objects.filter(status='finished'):
                calculate_gameweek_payouts(gw)

            # 3. Exact verified list of payments made by members
            verified_payments = [
                {
                    'manager_name': 'Samuel Wambua',
                    'amount': Decimal('150.00'),
                    'dt': eat_tz.localize(datetime(2026, 8, 28, 18, 31, 0)),
                    'ref': 'MPESA-SW-2808',
                    'notes': 'M-Pesa payment (28/8 6:31pm)'
                },
                {
                    'manager_name': 'Torque Dennis',
                    'amount': Decimal('100.00'),
                    'dt': eat_tz.localize(datetime(2026, 8, 28, 18, 54, 0)),
                    'ref': 'MPESA-TD-2808',
                    'notes': 'M-Pesa payment (28/8 6:54pm)'
                },
                {
                    'manager_name': 'Bright Ottore',
                    'amount': Decimal('150.00'),
                    'dt': eat_tz.localize(datetime(2026, 8, 28, 21, 26, 0)),
                    'ref': 'MPESA-BO-2808-1',
                    'notes': 'M-Pesa payment 1 (28/8 9:26pm)'
                },
                {
                    'manager_name': 'Benn Mwangi',
                    'amount': Decimal('300.00'),
                    'dt': eat_tz.localize(datetime(2026, 8, 28, 21, 37, 0)),
                    'ref': 'MPESA-BM-2808',
                    'notes': 'M-Pesa payment (28/8 9:37pm)'
                },
                {
                    'manager_name': 'Bright Ottore',
                    'amount': Decimal('150.00'),
                    'dt': eat_tz.localize(datetime(2026, 8, 28, 22, 11, 0)),
                    'ref': 'MPESA-BO-2808-2',
                    'notes': 'M-Pesa payment 2 (28/8 10:11pm)'
                },
                {
                    'manager_name': 'Marve Mathingu',
                    'amount': Decimal('100.00'),
                    'dt': eat_tz.localize(datetime(2026, 8, 29, 10, 47, 0)),
                    'ref': 'MPESA-MM-2908-1',
                    'notes': 'M-Pesa payment 1 (29/8 10:47am)'
                },
                {
                    'manager_name': 'Marve Mathingu',
                    'amount': Decimal('99.00'),
                    'dt': eat_tz.localize(datetime(2026, 8, 29, 10, 48, 0)),
                    'ref': 'MPESA-MM-2908-2',
                    'notes': 'M-Pesa payment 2 (29/8 10:48am)'
                },
                {
                    'manager_name': 'Aron Mangati',
                    'amount': Decimal('300.00'),
                    'dt': eat_tz.localize(datetime(2026, 9, 1, 13, 22, 0)),
                    'ref': 'MPESA-AM-0109',
                    'notes': 'M-Pesa payment (1/9 1:22pm)'
                },
            ]

            # 4. Allocate all payments sequentially in chronological FIFO order
            for item in verified_payments:
                member_key = item['manager_name'].lower()
                member = members_by_name.get(member_key)
                if not member:
                    # Try partial match
                    member = Member.objects.filter(manager_name__icontains=item['manager_name'].split()[0]).first()

                if not member:
                    self.stdout.write(self.style.ERROR(f"Member not found: {item['manager_name']}"))
                    continue

                created = allocate_payment_with_rollover(
                    member=member,
                    start_gw=None,
                    total_amount=item['amount'],
                    timestamp=item['dt'],
                    mpesa_code=item['ref'],
                    notes=item['notes'],
                    verified=True,
                    is_prize=False
                )

                alloc_summary = ", ".join([f"GW {p.gameweek.number}: Ksh. {p.amount_paid:,.2f}" for p in created])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[OK] Logged Ksh. {item['amount']:,.2f} for {member.manager_name} ({item['dt'].strftime('%d/%m %I:%M%p')}) -> {alloc_summary}"
                    )
                )

            # 5. Calculate payout prize winnings for finished gameweeks based on verified payments
            for gw in Gameweek.objects.filter(status='finished').order_by('number'):
                calculate_gameweek_payouts(gw)

            # Ensure historical GW3 official podium winners are preserved:
            # 1st: Torque Dennis (250.00), 2nd: Aron Mangati (166.67), 3rd: Marvin Owino (83.33)
            gw3 = Gameweek.objects.filter(number=3).first()
            if gw3:
                for res in gw3.results.all():
                    name_lower = res.member.manager_name.lower()
                    if "dennis" in name_lower:
                        res.gw_prize_won = Decimal('250.00')
                        res.is_top3 = True
                        res.league_rank = 1
                    elif "aron" in name_lower:
                        res.gw_prize_won = Decimal('166.67')
                        res.is_top3 = True
                        res.league_rank = 2
                    elif "owino" in name_lower or "marvin" in name_lower:
                        res.gw_prize_won = Decimal('83.33')
                        res.is_top3 = True
                        res.league_rank = 3
                    else:
                        res.gw_prize_won = Decimal('0.00')
                        res.is_top3 = False
                    res.save(update_fields=['gw_prize_won', 'is_top3', 'league_rank'])
                gw3.payout_calculated = True
                gw3.save(update_fields=['payout_calculated'])

            # 6. Seed historical prize cash payouts (disbursed prior to GW4)
            # GW1 Winners: Marve Mathingu (250.00), Samuel Wambua (166.67), Renny Muragu (83.33)
            # GW2 Winners: Benn Mwangi (250.00), Renny Muragu (166.67), Bright Ottore (83.33)
            # GW3 Winners: Torque Dennis (250.00), Aron Mangati (166.67) - disbursed; Marvin Owino (83.33) is pending/available.
            historical_disbursements = [
                # GW1
                {'manager_name': 'Marve Mathingu', 'gw_num': 1, 'amount': Decimal('250.00'), 'dt': eat_tz.localize(datetime(2026, 8, 20, 12, 0)), 'ref': 'MPESA-PAYOUT-GW1-MM'},
                {'manager_name': 'Samuel Wambua', 'gw_num': 1, 'amount': Decimal('166.67'), 'dt': eat_tz.localize(datetime(2026, 8, 20, 12, 5)), 'ref': 'MPESA-PAYOUT-GW1-SW'},
                {'manager_name': 'Renny Muragu', 'gw_num': 1, 'amount': Decimal('83.33'), 'dt': eat_tz.localize(datetime(2026, 8, 20, 12, 10)), 'ref': 'MPESA-PAYOUT-GW1-RM'},
                # GW2
                {'manager_name': 'Benn Mwangi', 'gw_num': 2, 'amount': Decimal('250.00'), 'dt': eat_tz.localize(datetime(2026, 8, 27, 12, 0)), 'ref': 'MPESA-PAYOUT-GW2-BM'},
                {'manager_name': 'Renny Muragu', 'gw_num': 2, 'amount': Decimal('166.67'), 'dt': eat_tz.localize(datetime(2026, 8, 27, 12, 5)), 'ref': 'MPESA-PAYOUT-GW2-RM'},
                {'manager_name': 'Bright Ottore', 'gw_num': 2, 'amount': Decimal('83.33'), 'dt': eat_tz.localize(datetime(2026, 8, 27, 12, 10)), 'ref': 'MPESA-PAYOUT-GW2-BO'},
                # GW3
                {'manager_name': 'Torque Dennis', 'gw_num': 3, 'amount': Decimal('250.00'), 'dt': eat_tz.localize(datetime(2026, 9, 3, 12, 0)), 'ref': 'MPESA-PAYOUT-GW3-TD'},
                {'manager_name': 'Aron Mangati', 'gw_num': 3, 'amount': Decimal('166.67'), 'dt': eat_tz.localize(datetime(2026, 9, 3, 12, 5)), 'ref': 'MPESA-PAYOUT-GW3-AM'},
            ]

            for item in historical_disbursements:
                m = members_by_name.get(item['manager_name'].lower())
                if not m:
                    m = Member.objects.filter(manager_name__icontains=item['manager_name'].split()[0]).first()
                gw = Gameweek.objects.filter(number=item['gw_num']).first()
                if m and gw:
                    PrizePayout.objects.create(
                        member=m,
                        gameweek=gw,
                        amount=item['amount'],
                        payout_method='MPESA_CASH',
                        mpesa_reference=item['ref'],
                        notes=f"Historical GW {gw.number} cash payout sent via M-Pesa",
                        disbursed_at=item['dt']
                    )

        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("[DONE] Treasury Ledger reset & initial payments successfully seeded!"))
        self.stdout.write("="*50 + "\n")

        # Summary of members, their payments and prize balances
        self.stdout.write("CURRENT MEMBER STATUS SUMMARY:")
        for m in Member.objects.all().order_by('manager_name'):
            p_list = list(Payment.objects.filter(member=m).order_by('gameweek__number'))
            p_str = ", ".join([f"GW{p.gameweek.number}: {p.amount_paid:,.2f}" for p in p_list]) or "No cash payments"
            avail_winnings = get_member_available_prize_balance(m)
            self.stdout.write(f"- {m.manager_name}: {p_str} | Available Prize Winnings: Ksh. {avail_winnings:,.2f}")
