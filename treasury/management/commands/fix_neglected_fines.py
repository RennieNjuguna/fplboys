from django.core.management.base import BaseCommand
from league.models import Member
from treasury.services.payment_allocation import audit_and_fix_neglected_fines


class Command(BaseCommand):
    help = (
        "Audits and repairs neglected late fines where a member has unpaid fines on earlier gameweeks "
        "while advance contributions roll forward into future gameweeks. Rebalances funds from the furthest "
        "advance gameweek back to settle the late fine."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--member',
            type=str,
            default=None,
            help="Optional manager name or FPL entry ID to audit a specific member only."
        )

    def handle(self, *args, **options):
        member_arg = options.get('member')
        target_member = None

        if member_arg:
            if member_arg.isdigit():
                target_member = Member.objects.filter(fpl_entry_id=int(member_arg)).first()
            if not target_member:
                target_member = Member.objects.filter(manager_name__icontains=member_arg).first()

            if not target_member:
                self.stderr.write(self.style.ERROR(f"Member '{member_arg}' not found."))
                return

            self.stdout.write(self.style.NOTICE(f"Auditing neglected late fines for {target_member.manager_name}..."))
        else:
            self.stdout.write(self.style.NOTICE("Auditing neglected late fines across all league members..."))

        repairs = audit_and_fix_neglected_fines(member=target_member)

        if not repairs:
            self.stdout.write(self.style.SUCCESS("[OK] All late fines are properly settled. No neglected fines found."))
        else:
            self.stdout.write(self.style.SUCCESS(f"[OK] Successfully resolved {len(repairs)} neglected fine(s):"))
            for r in repairs:
                self.stdout.write(
                    f"  - {r['member']}: Transferred Ksh. {r['amount']:,.2f} from GW {r['donor_gw']} advance "
                    f"to settle GW {r['late_gw']} late fine (Tx #{r['tx_id']})."
                )
