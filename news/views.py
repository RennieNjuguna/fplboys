from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from league.models import Gameweek
from news.models import RoastEdition, ManagerRoastItem
from news.services.roast_engine import generate_roast_edition


def gazette_view(request):
    """
    Renders The FPL Boys Gazette newspaper layout with issue selector,
    breaking news ticker, brutal roast cards, classifieds, and PDF export.
    """
    all_editions = []
    selected_edition = None
    manager_roasts = []

    try:
        all_editions = list(RoastEdition.objects.filter(is_published=True).select_related('gameweek').order_by('-edition_number'))

        # If no editions exist yet, auto-generate for finished gameweeks
        if not all_editions:
            finished_gws = Gameweek.objects.filter(status__in=['finished', 'active']).order_by('-number')
            for gw in finished_gws:
                try:
                    generate_roast_edition(gw)
                except Exception:
                    pass
            all_editions = list(RoastEdition.objects.filter(is_published=True).select_related('gameweek').order_by('-edition_number'))

        selected_gw_num = request.GET.get('gw')

        if selected_gw_num:
            try:
                selected_edition = RoastEdition.objects.filter(edition_number=int(selected_gw_num), is_published=True).first()
            except (ValueError, TypeError):
                selected_edition = None

        if not selected_edition and all_editions:
            selected_edition = all_editions[0]

        if selected_edition:
            manager_roasts = selected_edition.manager_roasts.select_related('member').order_by('rank_in_gw', 'order')

    except Exception as e:
        # Handles unmigrated database state gracefully
        pass

    context = {
        'all_editions': all_editions,
        'selected_edition': selected_edition,
        'manager_roasts': manager_roasts,
    }
    return render(request, 'news/gazette.html', context)


def api_gazette_data(request, edition_num):
    """
    JSON API providing full structured Gazette edition data.
    """
    edition = get_object_or_404(RoastEdition, edition_number=edition_num, is_published=True)
    roasts = edition.manager_roasts.select_related('member').order_by('rank_in_gw')

    data = {
        'edition_number': edition.edition_number,
        'gameweek': edition.gameweek.number,
        'headline': edition.headline,
        'subheadline': edition.subheadline,
        'chief_editor': edition.chief_editor,
        'weather_report': edition.weather_report,
        'editorial_lead': edition.editorial_lead,
        'clown_of_the_week': {
            'name': edition.clown_of_the_week.manager_name if edition.clown_of_the_week else 'N/A',
            'reason': edition.clown_reason,
        },
        'king_of_the_week': {
            'name': edition.king_of_the_week.manager_name if edition.king_of_the_week else 'N/A',
            'reason': edition.king_reason,
        },
        'quote_of_the_week': edition.quote_of_the_week,
        'quote_author': edition.quote_author,
        'defaulter_roast': edition.defaulter_roast,
        'transfer_hit_roast': edition.transfer_hit_roast,
        'classified_ads': edition.classified_ads,
        'manager_roasts': [
            {
                'manager_name': r.member.manager_name,
                'team_name': r.member.team_name,
                'rank': r.rank_in_gw,
                'net_points': r.net_points,
                'badge': r.badge,
                'title': r.roast_title,
                'body': r.roast_body,
                'verdict': r.verdict,
            }
            for r in roasts
        ]
    }
    return JsonResponse(data)

