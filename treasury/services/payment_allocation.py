from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from league.models import Member, Gameweek
from treasury.models import Payment, AuditLog, PrizePayout, PaymentTransaction


def models_sum(field_name):
    return Sum(field_name)


def get_member_available_prize_balance(member: Member) -> Decimal:
    """
    Computes a member's available prize winnings that haven't yet been disbursed or converted to payments.
    Available = Total Prizes Won - Cash Disbursed (M-Pesa) - Reinvested in Payments.
    """
    total_won = member.total_prizes_won

    cash_disbursed = PrizePayout.objects.filter(
        member=member,
        payout_method='MPESA_CASH'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    reinvested_payouts = PrizePayout.objects.filter(
        member=member,
        payout_method='REINVESTED'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Fallback for any legacy prize payments that lack PrizePayout records
    legacy_reinvested = Payment.objects.filter(
        member=member,
        mpesa_code__icontains="PRIZE",
        verified=True
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')

    total_reinvested = max(reinvested_payouts, legacy_reinvested)
    available = total_won - cash_disbursed - total_reinvested
    return max(Decimal('0.00'), available)


def record_cash_payout(member: Member, amount: Decimal, gameweek=None, mpesa_reference=None, notes=None):
    """
    Records a cash prize payout sent directly to the winner via M-Pesa.
    Deducts the amount from their available prize balance.
    """
    available = get_member_available_prize_balance(member)
    if amount > available:
        raise ValueError(f"Cannot disburse Ksh. {amount}. Only Ksh. {available} available in prize balance.")

    payout = PrizePayout.objects.create(
        member=member,
        gameweek=gameweek,
        amount=amount,
        payout_method='MPESA_CASH',
        mpesa_reference=mpesa_reference,
        notes=notes or "Cash prize disbursed via M-Pesa",
        disbursed_at=timezone.now()
    )

    AuditLog.objects.create(
        action='PRIZE_DISBURSED',
        description=f"Disbursed Ksh. {amount:,.2f} cash prize to {member.manager_name} via M-Pesa. Ref: {mpesa_reference or 'N/A'}",
        performed_by='Treasurer'
    )
    return payout


def allocate_payment_with_rollover(
    member: Member,
    start_gw: Gameweek = None,
    total_amount: Decimal = Decimal('150.00'),
    timestamp=None,
    mpesa_code: str = None,
    notes: str = None,
    verified: bool = True,
    is_prize: bool = False,
    transaction_obj: PaymentTransaction = None
) -> list:
    """
    Unified payment and prize rollover allocation engine:
    1. Records the parent PaymentTransaction capturing the exact incoming payment amount (e.g. Ksh. 400).
    2. Distributes funds starting at start_gw in increments up to standard Ksh. 150.00 per GW using FIFO.
    3. Correctly adds to existing partial payments (e.g. 83.33 + 66.67 = 150.00) without overwriting.
    4. Automatically cascades any excess funds (> 150.00 or balance excess) forward to subsequent unpaid/partially paid GWs.
    5. Guarantees no single GW payment exceeds Ksh. 150.00 standard contribution.
    6. Links all per-GW allocation records to the parent PaymentTransaction.
    """
    if timestamp is None:
        timestamp = timezone.now()

    total_amount_dec = Decimal(str(total_amount))
    remaining_balance = total_amount_dec
    standard_rate = Decimal('150.00')
    created_payments = []

    # Query candidate gameweeks starting from start_gw.number (or member's joined_gameweek)
    min_gw = getattr(member, 'joined_gameweek', 1)
    if start_gw:
        min_gw = max(start_gw.number, min_gw)
    query = Gameweek.objects.filter(number__gte=min_gw).order_by('number')

    candidate_gws = list(query)
    start_gw_target = start_gw

    with transaction.atomic():
        if transaction_obj is None:
            tx_type = 'PRIZE_ROLLOVER' if is_prize else 'MPESA'
            transaction_obj = PaymentTransaction.objects.create(
                member=member,
                amount=total_amount_dec,
                starting_gameweek=start_gw_target,
                mpesa_code=mpesa_code or ("PRIZE-WINNINGS" if is_prize else None),
                timestamp_received=timestamp,
                transaction_type=tx_type,
                notes=notes or "",
                verified=verified
            )

        first_allocated_gw = None
        for gw in candidate_gws:
            if remaining_balance <= Decimal('0.00'):
                break

            existing_payment = Payment.objects.filter(member=member, gameweek=gw).first()
            current_paid = existing_payment.amount_paid if existing_payment else Decimal('0.00')

            if current_paid >= standard_rate:
                continue  # Already fully paid, rollover to next GW

            needed = standard_rate - current_paid
            allocating = min(remaining_balance, needed)
            if allocating <= Decimal('0.00'):
                continue

            if first_allocated_gw is None:
                first_allocated_gw = gw
                if transaction_obj and (transaction_obj.starting_gameweek is None or start_gw is None):
                    transaction_obj.starting_gameweek = gw
                    transaction_obj.save(update_fields=['starting_gameweek'])

            is_first = (gw == first_allocated_gw)

            if existing_payment:
                existing_payment.amount_paid += allocating
                if existing_payment.amount_paid > standard_rate:
                    existing_payment.amount_paid = standard_rate

                if timestamp:
                    existing_payment.timestamp_received = timestamp

                existing_payment.transaction = transaction_obj

                if is_prize:
                    if not existing_payment.mpesa_code:
                        existing_payment.mpesa_code = "PRIZE-WINNINGS"
                    elif "PRIZE" not in existing_payment.mpesa_code:
                        existing_payment.mpesa_code = f"{existing_payment.mpesa_code} / PRIZE"
                else:
                    if mpesa_code:
                        if existing_payment.mpesa_code and "PRIZE" in existing_payment.mpesa_code:
                            if mpesa_code not in existing_payment.mpesa_code:
                                existing_payment.mpesa_code = f"PRIZE / {mpesa_code}"
                        elif existing_payment.mpesa_code and mpesa_code not in existing_payment.mpesa_code:
                            existing_payment.mpesa_code = f"{existing_payment.mpesa_code}, {mpesa_code}"
                        else:
                            existing_payment.mpesa_code = mpesa_code

                if notes:
                    existing_payment.notes = f"{existing_payment.notes}; {notes}".strip('; ')

                existing_payment.verified = verified
                existing_payment.save()
                created_payments.append(existing_payment)
            else:
                if is_prize:
                    ref_code = "PRIZE-WINNINGS"
                    custom_notes = notes or f"Funded via tournament prize winnings"
                else:
                    ref_suffix = " (Carryover)" if not is_first and mpesa_code else ""
                    ref_code = f"{mpesa_code}{ref_suffix}" if mpesa_code else None
                    custom_notes = notes or (f"Payment for GW {gw.number}" if is_first else f"Auto carryover payment for GW {gw.number}")

                new_payment = Payment.objects.create(
                    transaction=transaction_obj,
                    member=member,
                    gameweek=gw,
                    amount_paid=allocating,
                    timestamp_received=timestamp,
                    mpesa_code=ref_code,
                    verified=verified,
                    notes=custom_notes
                )
                created_payments.append(new_payment)

            if is_prize:
                PrizePayout.objects.create(
                    member=member,
                    gameweek=gw,
                    amount=allocating,
                    payout_method='REINVESTED',
                    notes=f"Reinvested prize into GW {gw.number} contribution",
                    disbursed_at=timestamp
                )

            remaining_balance -= allocating

        source_desc = "prize winnings" if is_prize else f"payment of Ksh. {total_amount}"
        start_gw_num = first_allocated_gw.number if first_allocated_gw else (candidate_gws[0].number if candidate_gws else 1)
        AuditLog.objects.create(
            action='PAYMENT_CREATED',
            description=f"Processed {source_desc} for {member.manager_name} (Tx #{transaction_obj.id}). Allocated Ksh. {total_amount_dec - remaining_balance:,.2f} across {len(created_payments)} gameweeks starting GW {start_gw_num}.",
            performed_by='Treasurer'
        )

    return created_payments


def process_bulk_payment_carryover(member: Member, start_gw: Gameweek, total_amount: Decimal, timestamp=None, mpesa_code=None, notes=None) -> list:
    """
    Processes a lump-sum or rollover payment (e.g., Ksh. 300, 600, 1500) and automatically distributes it
    in Ksh. 150 increments to the starting gameweek and subsequent unpaid gameweeks in sequential order.
    Returns the list of created / updated Payment records.
    """
    return allocate_payment_with_rollover(
        member=member,
        start_gw=start_gw,
        total_amount=total_amount,
        timestamp=timestamp,
        mpesa_code=mpesa_code,
        notes=notes,
        verified=True,
        is_prize=False
    )


def apply_winnings_to_future_gameweeks(member: Member, amount_to_apply: Decimal, start_gw_number=None) -> list:
    """
    Applies a manager's cash prize winnings to cater for future unpaid gameweeks.
    Marks contributions with 'PRIZE-WINNINGS' and tracks reinvestments in PrizePayout.
    """
    available = get_member_available_prize_balance(member)
    if amount_to_apply > available:
        raise ValueError(f"Cannot apply Ksh. {amount_to_apply}. Only Ksh. {available} available in prize winnings.")

    start_gw = None
    if start_gw_number:
        start_gw = Gameweek.objects.filter(number=start_gw_number).first()
    else:
        # Find earliest unpaid/partial GW
        standard_rate = Decimal('150.00')
        min_gw = getattr(member, 'joined_gameweek', 1)
        for gw in Gameweek.objects.filter(number__gte=min_gw).order_by('number'):
            p = Payment.objects.filter(member=member, gameweek=gw).first()
            if not p or p.amount_paid < standard_rate:
                start_gw = gw
                break

    return allocate_payment_with_rollover(
        member=member,
        start_gw=start_gw,
        total_amount=amount_to_apply,
        verified=True,
        is_prize=True
    )
