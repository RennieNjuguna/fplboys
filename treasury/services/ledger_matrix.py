from decimal import Decimal
from django.utils import timezone
from league.models import Member, Gameweek, GameweekResult
from treasury.models import Payment


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
    Computes real-time flagging and payment compliance for the active/upcoming gameweek.
    Categorizes members into:
    - actually_flagged: Defaulters past deadline with late fines applied (unless fine waived).
    - to_be_flagged: Pending members within 24h of deadline (Ticking Bomb 💣) or upcoming.
    - cleared_members: Fully paid members on time or via advance/prize rollover.
    - pardoned_members: Excused late joiners.
    """
    all_gws = list(Gameweek.objects.all().order_by('number'))
    if not all_gws:
        return None

    # Determine target gameweek
    target_gw = None
    if target_gw_num:
        try:
            target_gw = Gameweek.objects.get(number=int(target_gw_num))
        except (Gameweek.DoesNotExist, ValueError):
            target_gw = None

    if not target_gw:
        # Priority 1: Active gameweek
        target_gw = Gameweek.objects.filter(status='active').first()
    if not target_gw:
        # Priority 2: Next upcoming gameweek
        target_gw = Gameweek.objects.filter(status='upcoming').order_by('number').first()
    if not target_gw:
        # Priority 3: Latest finished gameweek
        target_gw = Gameweek.objects.filter(status='finished').order_by('-number').first()
    if not target_gw:
        target_gw = all_gws[0]

    now = timezone.now()
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

    # Fine Waiver Gameweeks: 1 (season start), 2 (teams not set), 19 (mid-season), 38 (season end)
    is_waived = target_gw.number in (1, 2, 19, 38)
    waiver_reason = {
        1: "GW 1 Season Kickoff Waiver",
        2: "GW 2 Early Season Setup Waiver",
        19: "GW 19 Mid-Season Holiday Waiver",
        38: "GW 38 Season Finale Waiver",
    }.get(target_gw.number, "")

    # State
    if target_gw.status == 'active':
        gw_state = 'active'
    elif is_past_deadline:
        gw_state = 'active' if target_gw.status != 'finished' else 'finished'
    elif is_within_24h:
        gw_state = 'ticking_bomb'
    else:
        gw_state = 'upcoming'

    members = list(Member.objects.filter(is_active=True).order_by('manager_name'))
    payments = {
        p.member_id: p for p in Payment.objects.filter(gameweek=target_gw, verified=True)
    }

    standard_fee = Decimal('150.00')
    late_fine_rate = Decimal('0.00') if is_waived else Decimal('50.00')

    actually_flagged = []
    to_be_flagged = []
    cleared_members = []
    pardoned_members = []

    total_collected_gw = Decimal('0.00')
    total_fines_gw = Decimal('0.00')
    total_due_outstanding = Decimal('0.00')

    for member in members:
        payment = payments.get(member.id)
        amount_paid = payment.amount_paid if payment else Decimal('0.00')
        is_late_payment = payment.is_late if payment else False
        late_fine_incurred = payment.late_fine_amount if (payment and payment.is_late) else Decimal('0.00')
        balance_due = max(Decimal('0.00'), standard_fee - amount_paid)

        total_collected_gw += amount_paid
        total_fines_gw += late_fine_incurred

        # Check pardon (joined in a later gameweek)
        if target_gw.number < getattr(member, 'joined_gameweek', 1):
            pardoned_members.append({
                'member': member,
                'status': 'PARDON',
                'reason': f"Joined in GW {member.joined_gameweek}",
            })
            continue

        # Case 1: Fully Paid on time
        if amount_paid >= standard_fee and not is_late_payment:
            is_advance = 'Carryover' in (payment.mpesa_code or '') or 'PRIZE' in (payment.mpesa_code or '')
            cleared_members.append({
                'member': member,
                'amount_paid': amount_paid,
                'payment': payment,
                'is_advance': is_advance,
                'is_late': False,
                'mpesa_code': payment.mpesa_code if payment else None,
                'timestamp': payment.timestamp_received if payment else None,
                'status_label': 'Paid (Advance)' if is_advance else 'Paid (On Time)',
            })

        # Case 2: Fully Paid but late
        elif amount_paid >= standard_fee and is_late_payment:
            cleared_members.append({
                'member': member,
                'amount_paid': amount_paid,
                'payment': payment,
                'is_advance': False,
                'is_late': True,
                'late_fine': late_fine_incurred,
                'mpesa_code': payment.mpesa_code if payment else None,
                'timestamp': payment.timestamp_received if payment else None,
                'status_label': 'Paid Late (+50 fine)',
            })

        # Case 3: GW deadline has passed (or GW is active/finished) -> ACTUALLY FLAGGED
        elif is_past_deadline:
            fine_to_apply = late_fine_rate if not is_late_payment else late_fine_incurred
            total_member_due = balance_due + fine_to_apply
            total_due_outstanding += total_member_due

            status_type = 'PARTIAL_DEFAULTER' if amount_paid > Decimal('0.00') else 'DEFAULTER'
            actually_flagged.append({
                'member': member,
                'amount_paid': amount_paid,
                'balance_due': balance_due,
                'late_fine': fine_to_apply,
                'total_due': total_member_due,
                'status_type': status_type,
                'is_waived': is_waived,
                'phone_number': member.phone_number,
                'payment': payment,
            })

        # Case 4: GW deadline is upcoming -> TO BE FLAGGED
        else:
            total_member_due = balance_due
            total_due_outstanding += total_member_due
            
            status_type = 'TICKING_BOMB' if is_within_24h else 'PENDING'
            if amount_paid > Decimal('0.00'):
                status_type = 'PARTIAL_PENDING'

            to_be_flagged.append({
                'member': member,
                'amount_paid': amount_paid,
                'balance_due': balance_due,
                'potential_fine': late_fine_rate,
                'total_due': total_member_due,
                'status_type': status_type,
                'is_within_24h': is_within_24h,
                'is_waived': is_waived,
                'phone_number': member.phone_number,
                'payment': payment,
            })

    total_expected = len(members) - len(pardoned_members)
    cleared_count = len(cleared_members)
    compliance_percent = int((cleared_count / total_expected * 100)) if total_expected > 0 else 100

    return {
        'gw': target_gw,
        'all_gws': all_gws,
        'gw_state': gw_state,  # 'active', 'ticking_bomb', 'upcoming', 'finished'
        'is_past_deadline': is_past_deadline,
        'is_within_24h': is_within_24h,
        'time_left_seconds': time_left_seconds,
        'time_left_human': time_left_human,
        'is_waived': is_waived,
        'waiver_reason': waiver_reason,
        'actually_flagged': actually_flagged,
        'to_be_flagged': to_be_flagged,
        'cleared_members': cleared_members,
        'pardoned_members': pardoned_members,
        'total_expected': total_expected,
        'cleared_count': cleared_count,
        'flagged_count': len(actually_flagged),
        'pending_count': len(to_be_flagged),
        'compliance_percent': compliance_percent,
        'total_collected_gw': total_collected_gw,
        'total_fines_gw': total_fines_gw,
        'total_due_outstanding': total_due_outstanding,
    }

