from decimal import Decimal
from django.utils import timezone
from league.models import Member, Gameweek, GameweekResult
from treasury.models import Payment, WAIVED_FINE_GAMEWEEKS


def build_financial_ledger_matrix(max_gws=38):
    """
    Builds an Excel-style 2D matrix of Members (rows) x Gameweeks (columns).
    Provides color status, amounts, late flags, prizes, row totals, and column totals.
    """
    members = list(Member.objects.filter(is_active=True).order_by('manager_name'))
    gameweeks = list(Gameweek.objects.all().order_by('number')[:max_gws])

    # Pre-fetch all payments and results to avoid N+1 queries
    all_payments = {(p.member_id, p.gameweek_id): p for p in Payment.objects.filter(verified=True)}
    all_results = {(r.member_id, r.gameweek_id): r for r in GameweekResult.objects.all()}

    now = timezone.now()

    rows = []
    col_totals = {
        gw.id: {
            'gw': gw,
            'total_collected': Decimal('0.00'),
            'total_fines': Decimal('0.00'),
            'total_prizes': Decimal('0.00'),
            'paid_count': 0,
            'late_count': 0,
            'unpaid_count': 0,
            'expected_count': sum(1 for m in members if getattr(m, 'joined_gameweek', 1) <= gw.number),
        }
        for gw in gameweeks
    }

    for member in members:
        row_cells = []
        row_total_paid = Decimal('0.00')
        row_total_fines = Decimal('0.00')
        row_total_prizes = Decimal('0.00')
        row_unpaid_count = 0
        row_late_count = 0

        for gw in gameweeks:
            payment = all_payments.get((member.id, gw.id))
            gw_res = all_results.get((member.id, gw.id))

            is_pardon = (gw.number < getattr(member, 'joined_gameweek', 1))
            is_due = not is_pardon and ((gw.status in ['finished', 'active']) or (gw.deadline_time and now > gw.deadline_time))
            prize_won = Decimal(str(gw_res.gw_prize_won)) if gw_res else Decimal('0.00')
            net_points = gw_res.net_points if gw_res else 0

            standard_due = Decimal('150.00')
            if is_pardon:
                amount_paid = Decimal('0.00')
                late_fine = Decimal('0.00')
                balance_due = Decimal('0.00')
                status = 'PARDON'
            elif payment:
                amount_paid = payment.amount_paid
                late_fine = payment.late_fine_amount if payment.is_late else Decimal('0.00')
                balance_due = max(Decimal('0.00'), standard_due - amount_paid)
                
                if payment.is_late:
                    status = 'LATE'
                    row_late_count += 1
                    col_totals[gw.id]['late_count'] += 1
                elif amount_paid < standard_due:
                    status = 'PARTIAL'
                else:
                    status = 'PAID'
                    col_totals[gw.id]['paid_count'] += 1

                row_total_paid += amount_paid
                row_total_fines += late_fine
                col_totals[gw.id]['total_collected'] += amount_paid
                col_totals[gw.id]['total_fines'] += late_fine
            else:
                amount_paid = Decimal('0.00')
                late_fine = Decimal('0.00')
                balance_due = standard_due if is_due else Decimal('0.00')
                if is_due:
                    status = 'UNPAID'
                    row_unpaid_count += 1
                    col_totals[gw.id]['unpaid_count'] += 1
                else:
                    status = 'UPCOMING'

            row_total_prizes += prize_won
            col_totals[gw.id]['total_prizes'] += prize_won

            cell = {
                'gw_number': gw.number,
                'gw_id': gw.id,
                'status': status,  # 'PAID', 'PARTIAL', 'LATE', 'UNPAID', 'UPCOMING'
                'payment': payment,
                'gw_result': gw_res,
                'amount_paid': amount_paid,
                'balance_due': balance_due,
                'late_fine': late_fine,
                'prize_won': prize_won,
                'net_points': net_points,
                'is_late': payment.is_late if payment else False,
                'mpesa_code': payment.mpesa_code if payment else None,
                'timestamp': payment.timestamp_received if payment else None,
                'is_due': is_due,
            }
            row_cells.append(cell)


        net_pl = row_total_prizes - row_total_paid

        rows.append({
            'member': member,
            'cells': row_cells,
            'total_paid': row_total_paid,
            'total_fines': row_total_fines,
            'total_prizes': row_total_prizes,
            'net_pl': net_pl,
            'unpaid_count': row_unpaid_count,
            'late_count': row_late_count,
        })

    # Prepare ordered columns summary list
    column_summaries = [col_totals[gw.id] for gw in gameweeks]

    # Grand totals
    grand_total_collected = sum(c['total_collected'] for c in column_summaries)
    grand_total_fines = sum(c['total_fines'] for c in column_summaries)
    grand_total_prizes = sum(c['total_prizes'] for c in column_summaries)

    return {
        'members': members,
        'gameweeks': gameweeks,
        'rows': rows,
        'column_summaries': column_summaries,
        'grand_total_collected': grand_total_collected,
        'grand_total_fines': grand_total_fines,
        'grand_total_prizes': grand_total_prizes,
    }


def get_active_gw_flagged_summary(target_gw_num=None):
    """
    Computes a season-aware financial status radar:
    1. Flagged Defaulters: Members who owe contributions/fines for ANY past/finished gameweeks
       whose deadlines have passed (with zero fines on waived GWs: 1, 2, 19, 38).
    2. Pending Contributions: Members with unpaid dues for the current active/upcoming gameweek (e.g. GW 3),
       with ticking-bomb (<24h) countdown warnings.
    3. Cleared & Paid: Members who have cleared their contributions for the current gameweek.
    """
    all_gws = list(Gameweek.objects.all().order_by('number'))
    if not all_gws:
        return None

    now = timezone.now()
    standard_fee = Decimal('150.00')

    # Determine current target gameweek (Active or Next Upcoming)
    target_gw = None
    if target_gw_num:
        try:
            target_gw = Gameweek.objects.get(number=int(target_gw_num))
        except (Gameweek.DoesNotExist, ValueError):
            target_gw = None

    if not target_gw:
        target_gw = Gameweek.objects.filter(status='active').first()
    if not target_gw:
        target_gw = Gameweek.objects.filter(status='upcoming').order_by('number').first()
    if not target_gw:
        target_gw = Gameweek.objects.filter(status='finished').order_by('-number').first()
    if not target_gw:
        target_gw = all_gws[0]

    # Deadline status for target GW
    deadline = target_gw.deadline_time
    is_past_deadline = target_gw.is_past_deadline or target_gw.status in ['active', 'finished']
    time_left_seconds = 0
    is_within_24h = False
    time_left_human = ""

    if deadline and not is_past_deadline:
        diff = (deadline - now).total_seconds()
        if diff > 0:
            time_left_seconds = int(diff)
            is_within_24h = (time_left_seconds <= 86400)
            hours = time_left_seconds // 3600
            minutes = (time_left_seconds % 3600) // 60
            days = time_left_seconds // 86400

            if days > 0:
                time_left_human = f"{days}d {hours % 24}h remaining"
            elif hours > 0:
                time_left_human = f"{hours}h {minutes}m remaining"
            else:
                time_left_human = f"{minutes}m remaining"
        else:
            is_past_deadline = True
            time_left_human = "Deadline Passed"
    else:
        time_left_human = "Deadline Passed" if is_past_deadline else "TBD"

    # Fine Waiver for current target GW
    is_waived = target_gw.number in WAIVED_FINE_GAMEWEEKS
    waiver_reason = {
        1: "GW 1 Season Kickoff Waiver (No Fines)",
        2: "GW 2 Early Season Setup Waiver (No Fines)",
        19: "GW 19 Mid-Season Holiday Waiver (No Fines)",
        38: "GW 38 Season Finale Waiver (No Fines)",
    }.get(target_gw.number, "")

    if target_gw.status == 'active':
        gw_state = 'active'
    elif is_past_deadline:
        gw_state = 'active' if target_gw.status != 'finished' else 'finished'
    elif is_within_24h:
        gw_state = 'ticking_bomb'
    else:
        gw_state = 'upcoming'

    members = list(Member.objects.filter(is_active=True).order_by('manager_name'))

    # =========================================================================
    # 1. FLAGGED DEFAULTERS (Across all past/finished/active GWs past deadline)
    # =========================================================================
    past_gws = list(Gameweek.objects.filter(
        deadline_time__lt=now
    ).exclude(number=target_gw.number).order_by('number'))

    # If target_gw is itself past deadline, include it in past evaluation
    if is_past_deadline and target_gw not in past_gws:
        past_gws.append(target_gw)
        past_gws.sort(key=lambda g: g.number)

    flagged_defaulters = []
    total_defaulters_amount = Decimal('0.00')

    for member in members:
        joined_gw = getattr(member, 'joined_gameweek', 1)
        member_defaults = []
        member_balance_sum = Decimal('0.00')
        member_fines_sum = Decimal('0.00')

        for gw in past_gws:
            if gw.number < joined_gw:
                continue  # Pardoned

            payment = Payment.objects.filter(member=member, gameweek=gw, verified=True).first()
            paid = payment.amount_paid if payment else Decimal('0.00')
            gw_waived = gw.number in WAIVED_FINE_GAMEWEEKS

            if paid < standard_fee:
                bal = standard_fee - paid
                fine = Decimal('0.00') if gw_waived else Decimal('50.00')
                member_balance_sum += bal
                member_fines_sum += fine
                member_defaults.append({
                    'gw_number': gw.number,
                    'amount_paid': paid,
                    'balance_due': bal,
                    'late_fine': fine,
                    'is_waived': gw_waived,
                    'total_due': bal + fine
                })

        if member_defaults:
            gw_summary_parts = []
            for d in member_defaults:
                fine_note = " (Waived Fine)" if d['is_waived'] else (" (+50 Fine)" if d['late_fine'] > 0 else "")
                if d['amount_paid'] > Decimal('0.00'):
                    gw_summary_parts.append(f"GW {d['gw_number']} (Bal Ksh. {d['balance_due']:,.0f}{fine_note})")
                else:
                    gw_summary_parts.append(f"GW {d['gw_number']} (Ksh. {d['balance_due']:,.0f}{fine_note})")

            total_member_due = member_balance_sum + member_fines_sum
            total_defaulters_amount += total_member_due

            flagged_defaulters.append({
                'member': member,
                'defaulted_gws': member_defaults,
                'defaulted_count': len(member_defaults),
                'gws_summary_text': " • ".join(gw_summary_parts),
                'total_balance_due': member_balance_sum,
                'total_fines': member_fines_sum,
                'total_due': total_member_due,
                'has_fines': member_fines_sum > Decimal('0.00'),
                'phone_number': member.phone_number,
            })

    # =========================================================================
    # 2. CURRENT ACTIVE / UPCOMING GAMEWEEK: PENDING & CLEARED
    # =========================================================================
    current_gw_pending = []
    current_gw_cleared = []
    current_gw_pardoned = []
    total_collected_gw = Decimal('0.00')

    for member in members:
        joined_gw = getattr(member, 'joined_gameweek', 1)
        if target_gw.number < joined_gw:
            current_gw_pardoned.append({
                'member': member,
                'status': 'PARDON',
                'reason': f"Joined in GW {member.joined_gameweek}",
            })
            continue

        payment = Payment.objects.filter(member=member, gameweek=target_gw, verified=True).first()
        paid = payment.amount_paid if payment else Decimal('0.00')
        total_collected_gw += paid

        if paid >= standard_fee:
            is_advance = 'Carryover' in (payment.mpesa_code or '') or 'PRIZE' in (payment.mpesa_code or '')
            current_gw_cleared.append({
                'member': member,
                'amount_paid': paid,
                'payment': payment,
                'is_advance': is_advance,
                'is_late': payment.is_late if payment else False,
                'mpesa_code': payment.mpesa_code if payment else None,
                'timestamp': payment.timestamp_received if payment else None,
                'status_label': 'Paid (Advance)' if is_advance else 'Paid (On Time)',
            })
        elif paid > Decimal('0.00'):
            # Partial payment - strictly in pending with remaining balance due
            bal = standard_fee - paid
            current_gw_pending.append({
                'member': member,
                'amount_paid': paid,
                'balance_due': bal,
                'potential_fine': Decimal('0.00') if is_waived else Decimal('50.00'),
                'total_due': bal,
                'is_partial': True,
                'phone_number': member.phone_number,
                'payment': payment,
            })
        else:
            current_gw_pending.append({
                'member': member,
                'amount_paid': Decimal('0.00'),
                'balance_due': standard_fee,
                'potential_fine': Decimal('0.00') if is_waived else Decimal('50.00'),
                'total_due': standard_fee,
                'is_partial': False,
                'phone_number': member.phone_number,
                'payment': None,
            })

    total_expected = len(members) - len(current_gw_pardoned)
    cleared_count = len(current_gw_cleared)
    compliance_percent = int((cleared_count / total_expected * 100)) if total_expected > 0 else 100

    return {
        'gw': target_gw,
        'all_gws': all_gws,
        'gw_state': gw_state,
        'is_past_deadline': is_past_deadline,
        'is_within_24h': is_within_24h,
        'time_left_seconds': time_left_seconds,
        'time_left_human': time_left_human,
        'is_waived': is_waived,
        'waiver_reason': waiver_reason,
        'flagged_defaulters': flagged_defaulters,
        'defaulters_count': len(flagged_defaulters),
        'total_defaulters_amount': total_defaulters_amount,
        'current_gw_pending': current_gw_pending,
        'pending_count': len(current_gw_pending),
        'current_gw_cleared': current_gw_cleared,
        'cleared_count': cleared_count,
        'current_gw_pardoned': current_gw_pardoned,
        'total_expected': total_expected,
        'compliance_percent': compliance_percent,
        'total_collected_gw': total_collected_gw,
    }

