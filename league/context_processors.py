from league.models import Gameweek, Member
from treasury.services.pot_calculator import get_treasury_summary


def league_context(request):
    """
    Global context processor to provide mini-league stats across all templates.
    """
    current_gw = Gameweek.objects.filter(is_current=True).first()
    if not current_gw:
        current_gw = Gameweek.objects.filter(status='active').first()
    if not current_gw:
        current_gw = Gameweek.objects.filter(status='finished').order_by('-number').first()

    next_gw = Gameweek.objects.filter(is_next=True).first()
    if not next_gw and current_gw:
        next_gw = Gameweek.objects.filter(number=current_gw.number + 1).first()

    active_members_count = Member.objects.filter(is_active=True).count()

    try:
        treasury_summary = get_treasury_summary()
    except Exception:
        treasury_summary = {}

    is_treasury_unlocked = bool(
        request.user.is_authenticated or request.session.get('treasury_admin_authenticated')
    )

    return {
        'current_gw': current_gw,
        'next_gw': next_gw,
        'active_members_count': active_members_count,
        'global_treasury': treasury_summary,
        'is_treasury_unlocked': is_treasury_unlocked,
    }
