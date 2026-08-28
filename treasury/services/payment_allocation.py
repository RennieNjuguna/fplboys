from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from league.models import Member, Gameweek
from treasury.models import Payment, AuditLog


def process_bulk_payment_carryover(member: Member, start_gw: Gameweek, total_amount: Decimal, timestamp=None, mpesa_code=None, notes=None) -> list:
    """
    Processes a lump-sum payment (e.g., Ksh. 300, 600, 1500) and automatically distributes it
    in Ksh. 150 increments to the starting gameweek and subsequent unpaid gameweeks in sequential order.
    Returns the list of created / updated Payment records.
    """
    if timestamp is None:
        timestamp = timezone.now()

    created_payments = []
    remaining_balance = Decimal(str(total_amount))
    standard_rate = Decimal('150.00')

    # Get future gameweeks starting from start_gw.number
    all_future_gws = list(Gameweek.objects.filter(number__gte=start_gw.number).order_by('number'))

    with transaction.atomic():
        for gw in all_future_gws:
            if remaining_balance <= Decimal('0.00'):
                break

            existing_payment = Payment.objects.filter(member=member, gameweek=gw).first()
            if existing_payment and existing_payment.amount_paid >= standard_rate:
                continue  # Already fully paid for this gameweek, proceed to next

            current_paid = existing_payment.amount_paid if existing_payment else Decimal('0.00')
            needed = standard_rate - current_paid
            allocating = min(remaining_balance, needed)

            if existing_payment:
                existing_payment.amount_paid += allocating
                if mpesa_code:
                    existing_payment.mpesa_code = mpesa_code
                if timestamp:
                    existing_payment.timestamp_received = timestamp
                existing_payment.verified = True
                if notes:
                    existing_payment.notes = f"{existing_payment.notes}; {notes}".strip('; ')
                existing_payment.save()
                created_payments.append(existing_payment)
            else:
                is_first = (gw == start_gw)
                ref_suffix = f" (Carryover)" if not is_first and mpesa_code else ""
                custom_notes = notes or (f"Lump sum payment for GW {start_gw.number}" if is_first else f"Auto carryover from GW {start_gw.number} payment")
                
                new_payment = Payment.objects.create(
                    member=member,
                    gameweek=gw,
                    amount_paid=allocating,
                    timestamp_received=timestamp,
                    mpesa_code=f"{mpesa_code}{ref_suffix}" if mpesa_code else None,
                    verified=True,
                    notes=custom_notes
                )
                created_payments.append(new_payment)

            remaining_balance -= allocating

        if remaining_balance > Decimal('0.00') and created_payments:
            last_p = created_payments[-1]
            last_p.amount_paid += remaining_balance
            last_p.save()

        AuditLog.objects.create(
            action='PAYMENT_CREATED',
            description=f"Processed payment of Ksh. {total_amount} for {member.manager_name}. Distributed across {len(created_payments)} gameweeks starting GW {start_gw.number}.",
            performed_by='Treasurer'
        )

    return created_payments


def get_member_available_prize_balance(member: Member) -> Decimal:
    """
    Computes a member's available prize winnings that haven't yet been converted to payments.
    Available = Total Prizes Won - Total Amount Funded from Prizes in Payments.
    """
    total_won = member.total_prizes_won
    reinvested = Payment.objects.filter(
        member=member,
        mpesa_code__icontains="PRIZE",
        verified=True
    ).aggregate(total=models_sum('amount_paid'))['total'] or Decimal('0.00')

    available = total_won - reinvested
    return max(Decimal('0.00'), available)


def models_sum(field_name):
    from django.db.models import Sum
    return Sum(field_name)


def apply_winnings_to_future_gameweeks(member: Member, amount_to_apply: Decimal, start_gw_number=None) -> list:
    """
    Applies a manager's cash prize winnings to cater for future unpaid gameweeks.
    Marks contributions with 'PRIZE-WINNINGS' and clear notes.
    """
    available = get_member_available_prize_balance(member)
    if amount_to_apply > available:
        raise ValueError(f"Cannot apply Ksh. {amount_to_apply}. Only Ksh. {available} available in prize winnings.")

    standard_rate = Decimal('150.00')
    remaining = Decimal(str(amount_to_apply))
    created_payments = []

    # Filter unpaid gameweeks
    query = Gameweek.objects.all().order_by('number')
    if start_gw_number:
        query = query.filter(number__gte=start_gw_number)

    candidate_gws = list(query)

    with transaction.atomic():
        for gw in candidate_gws:
            if remaining <= Decimal('0.00'):
                break

            existing_payment = Payment.objects.filter(member=member, gameweek=gw).first()
            if existing_payment and existing_payment.amount_paid >= standard_rate:
                continue

            current_paid = existing_payment.amount_paid if existing_payment else Decimal('0.00')
            needed = standard_rate - current_paid
            allocating = min(remaining, needed)

            if existing_payment:
                existing_payment.amount_paid += allocating
                existing_payment.mpesa_code = "PRIZE-WINNINGS"
                existing_payment.notes = f"{existing_payment.notes}; Topped up from prize winnings".strip('; ')
                existing_payment.verified = True
                existing_payment.save()
                created_payments.append(existing_payment)
            else:
                new_payment = Payment.objects.create(
                    member=member,
                    gameweek=gw,
                    amount_paid=allocating,
                    timestamp_received=timezone.now(),
                    mpesa_code="PRIZE-WINNINGS",
                    is_late=False,
                    late_fine_amount=Decimal('0.00'),
                    verified=True,
                    notes=f"Funded via tournament prize winnings"
                )
                created_payments.append(new_payment)

            remaining -= allocating

        AuditLog.objects.create(
            action='PAYMENT_CREATED',
            description=f"Applied Ksh. {amount_to_apply} from prize winnings for {member.manager_name} to fund {len(created_payments)} gameweeks.",
            performed_by='Treasurer'
        )

    return created_payments
