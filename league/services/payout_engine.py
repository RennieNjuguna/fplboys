from decimal import Decimal, ROUND_HALF_UP
from itertools import groupby
from django.db import transaction
from league.models import Gameweek, GameweekResult
from treasury.models import Payment, WAIVED_FINE_GAMEWEEKS


# Base Top 3 prize allocations (sum = 500.00)
BASE_PRIZES = [
    Decimal('250.00'),  # 1st Place (3/6)
    Decimal('166.67'),  # 2nd Place (2/6)
    Decimal('83.33'),   # 3rd Place (1/6)
]


def is_member_eligible_for_prize(member, gameweek: Gameweek) -> bool:
    """
    Prize Eligibility Rules:
    1. Members who had not yet joined the league for this gameweek are ineligible (e.g. Aron joined in GW2, so ineligible for GW1).
    2. GW 1, GW 2, GW 19, and GW 38 have automatic fine and penalty waivers, so all joined members are eligible to win prizes even if their contribution was not yet logged.
    3. For standard gameweeks, payment must exist, be verified, and NOT be late (is_late=False).
    """
    if gameweek.number < getattr(member, 'joined_gameweek', 1):
        return False
    if gameweek.number in WAIVED_FINE_GAMEWEEKS:
        return True
    payment = Payment.objects.filter(member=member, gameweek=gameweek, verified=True).first()
    if not payment:
        return False
    return not payment.is_late


def calculate_gameweek_payouts(gameweek: Gameweek) -> list:
    """
    Calculates the weekly prize payouts for a gameweek based on net points (gw_points - transfer_cost).
    Applies strict eligibility: Managers who paid late or failed to pay are disqualified from cash prizes.
    Prizes roll down and are distributed to top eligible managers with tie-breaker pooling.
    """
    results = list(gameweek.results.select_related('member').order_by('-net_points', '-gw_points', 'overall_rank'))
    if not results:
        return []

    # Find previous gameweek to compute last_rank movement
    prev_gw = Gameweek.objects.filter(number=gameweek.number - 1).first()
    prev_ranks = {}
    if prev_gw:
        for prev_res in prev_gw.results.all():
            prev_ranks[prev_res.member_id] = prev_res.league_rank

    # Map position to base prize derived from gameweek.prize_pool_amount (3:2:1 ratio)
    prize_pool = gameweek.prize_pool_amount or Decimal('500.00')
    p1 = (prize_pool * Decimal('3') / Decimal('6')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    p2 = (prize_pool * Decimal('2') / Decimal('6')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    p3 = prize_pool - p1 - p2
    base_prizes = [p1, p2, p3]

    def get_pos_prize(idx):
        if idx < len(base_prizes):
            return base_prizes[idx]
        return Decimal('0.00')

    # Assign overall rank to all results (based strictly on points)
    # Group by net_points descending
    grouped = []
    for net_pts, group in groupby(results, key=lambda r: r.net_points):
        grouped.append((net_pts, list(group)))

    current_rank = 1
    for net_pts, tied_group in grouped:
        for item in tied_group:
            item.league_rank = current_rank
            if item.member_id in prev_ranks:
                item.last_rank = prev_ranks[item.member_id]
        current_rank += len(tied_group)

    # Separate eligible and ineligible managers for prize distribution
    eligible_grouped = []
    ineligible_members = []

    for net_pts, tied_group in grouped:
        eligible_in_tier = []
        for item in tied_group:
            if is_member_eligible_for_prize(item.member, gameweek):
                eligible_in_tier.append(item)
            else:
                item.gw_prize_won = Decimal('0.00')
                item.is_top3 = False
                ineligible_members.append(item)
        if eligible_in_tier:
            eligible_grouped.append((net_pts, eligible_in_tier))

    # Allocate prizes to eligible managers
    current_pos = 0
    updated_eligible = []

    for net_pts, tied_eligible in eligible_grouped:
        group_size = len(tied_eligible)
        group_prize_pool = Decimal('0.00')
        for i in range(current_pos, current_pos + group_size):
            group_prize_pool += get_pos_prize(i)

        if group_prize_pool > Decimal('0.00') and group_size > 0:
            share = (group_prize_pool / Decimal(str(group_size))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            share = Decimal('0.00')

        for item in tied_eligible:
            item.gw_prize_won = share
            item.is_top3 = (share > Decimal('0.00'))
            updated_eligible.append(item)

        current_pos += group_size

    all_updated = updated_eligible + ineligible_members

    with transaction.atomic():
        for res in all_updated:
            res.save(update_fields=['league_rank', 'last_rank', 'gw_prize_won', 'is_top3', 'net_points'])
        gameweek.payout_calculated = True
        gameweek.save(update_fields=['payout_calculated'])

    # Automatically generate The FPL Boys Gazette newspaper issue for this gameweek
    try:
        from news.services.roast_engine import generate_roast_edition
        generate_roast_edition(gameweek)
    except Exception:
        pass

    return all_updated
