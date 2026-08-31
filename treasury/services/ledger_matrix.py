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
