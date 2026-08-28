from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.conf import settings
from league.models import Member, Gameweek, GameweekResult
from treasury.models import Payment


def get_treasury_summary():
    """
    Computes overall pot balances and league financial health metrics.
    """
    # All verified payments
    verified_payments = Payment.objects.filter(verified=True)
    total_verified_count = verified_payments.count()

    # Total collected revenue (base contributions + any additional amounts)
    total_revenue_collected = verified_payments.aggregate(
        Sum('amount_paid')
    )['amount_paid__sum'] or Decimal('0.00')

    # Total late fines collected/assessed
    late_payments = verified_payments.filter(is_late=True)
    total_fines_collected = late_payments.aggregate(
        Sum('late_fine_amount')
    )['late_fine_amount__sum'] or Decimal('0.00')

    # Pot breakdowns:
    # Each standard payment of Ksh. 150 contributes:
    # 50 -> BBQ, 50 -> Jackpot, 50 -> Weekly Prize Pool
    standard_bbq_portion = Decimal(str(total_verified_count * settings.BBQ_PORTION))
    standard_jackpot_portion = Decimal(str(total_verified_count * settings.JACKPOT_PORTION))
    standard_prize_pool_portion = Decimal(str(total_verified_count * settings.PRIZE_POOL_PORTION))

    # All late fines route directly into the BBQ Pot!
    total_bbq_pot = standard_bbq_portion + total_fines_collected
    total_jackpot_pot = standard_jackpot_portion

    # Prizes distributed
    total_prizes_distributed = GameweekResult.objects.aggregate(
        Sum('gw_prize_won')
    )['gw_prize_won__sum'] or Decimal('0.00')

    # Weekly prize pool net balance
    prize_pool_balance = standard_prize_pool_portion - Decimal(str(total_prizes_distributed))

    # Finished and active gameweeks to date
    finished_or_active_gws = Gameweek.objects.filter(status__in=['finished', 'active'])
    gws_count = finished_or_active_gws.count()
    expected_total_to_date = Decimal(str(gws_count * settings.EXPECTED_TOTAL_MEMBERS * settings.WEEKLY_CONTRIBUTION))

    # Outstanding dues (expected vs actual verified payments)
    outstanding_dues = max(Decimal('0.00'), expected_total_to_date - total_revenue_collected)

    return {
        'total_revenue_collected': total_revenue_collected,
        'total_bbq_pot': total_bbq_pot,
        'bbq_standard_portion': standard_bbq_portion,
        'bbq_fines_portion': total_fines_collected,
        'total_jackpot_pot': total_jackpot_pot,
        'total_prize_pool_collected': standard_prize_pool_portion,
        'total_prizes_distributed': Decimal(str(total_prizes_distributed)),
        'prize_pool_balance': prize_pool_balance,
        'gws_count': gws_count,
        'expected_total_to_date': expected_total_to_date,
        'outstanding_dues': outstanding_dues,
        'verified_payments_count': total_verified_count,
        'late_payments_count': late_payments.count(),
    }


def get_member_financial_leaderboard():
    """
    Returns a sorted list of members ranked by Net Profit / Loss:
    Net P/L = Total Prizes Won - (Total Standard Contributions Paid + Total Fines Paid)
    """
    members = Member.objects.filter(is_active=True)
    leaderboard = []

    for m in members:
        # Sum of verified payments
        paid_agg = Payment.objects.filter(member=m, verified=True).aggregate(
            total_paid=Sum('amount_paid'),
            total_fines=Sum('late_fine_amount'),
            late_count=Count('id', filter=Q(is_late=True)),
            paid_count=Count('id')
        )
        total_paid = paid_agg['total_paid'] or Decimal('0.00')
        total_fines = paid_agg['total_fines'] or Decimal('0.00')
        late_count = paid_agg['late_count'] or 0
        paid_count = paid_agg['paid_count'] or 0

        # Sum of prizes won
        won_agg = m.gw_results.aggregate(
            total_won=Sum('gw_prize_won'),
            top3_count=Count('id', filter=Q(is_top3=True))
        )
        total_won = won_agg['total_won'] or Decimal('0.00')
        top3_count = won_agg['top3_count'] or 0

        net_pl = Decimal(str(total_won)) - total_paid

        # Overall points
        total_points = m.total_overall_points

        leaderboard.append({
            'member': m,
            'total_paid': total_paid,
            'total_fines': total_fines,
            'total_won': Decimal(str(total_won)),
            'net_pl': net_pl,
            'late_count': late_count,
            'paid_count': paid_count,
            'top3_count': top3_count,
            'total_points': total_points,
        })

    # Sort primarily by Net P/L descending, then by total points
    leaderboard.sort(key=lambda x: (x['net_pl'], x['total_points']), reverse=True)

    # Assign ranks
    for idx, item in enumerate(leaderboard, start=1):
        item['rank'] = idx

    return leaderboard
