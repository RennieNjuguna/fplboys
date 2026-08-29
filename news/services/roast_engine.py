import random
from decimal import Decimal
from django.utils import timezone
from django.db import connection, transaction
from league.models import Gameweek, GameweekResult, Member
from treasury.models import Payment
from news.models import RoastEdition, ManagerRoastItem


def ensure_news_tables_exist():
    """
    Guarantees SQLite tables for news models exist even if migrations haven't run on server.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS "news_roastedition" (
                "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                "edition_number" integer NOT NULL UNIQUE,
                "headline" varchar(255) NOT NULL,
                "subheadline" varchar(300) NOT NULL,
                "publish_date" datetime NOT NULL,
                "chief_editor" varchar(120) NOT NULL,
                "weather_report" varchar(200) NOT NULL,
                "editorial_lead" text NOT NULL,
                "clown_reason" text NOT NULL,
                "king_reason" text NOT NULL,
                "quote_of_the_week" text NOT NULL,
                "quote_author" varchar(120) NOT NULL,
                "defaulter_roast" text NOT NULL,
                "transfer_hit_roast" text NOT NULL,
                "classified_ads_raw" text NOT NULL,
                "is_published" bool NOT NULL,
                "created_at" datetime NOT NULL,
                "updated_at" datetime NOT NULL,
                "clown_of_the_week_id" bigint NULL REFERENCES "league_member" ("id") DEFERRABLE INITIALLY DEFERRED,
                "gameweek_id" bigint NOT NULL UNIQUE REFERENCES "league_gameweek" ("id") DEFERRABLE INITIALLY DEFERRED,
                "king_of_the_week_id" bigint NULL REFERENCES "league_member" ("id") DEFERRABLE INITIALLY DEFERRED
            );
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS "news_managerroastitem" (
                "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                "rank_in_gw" integer NOT NULL,
                "net_points" integer NOT NULL,
                "badge" varchar(50) NOT NULL,
                "roast_title" varchar(255) NOT NULL,
                "roast_body" text NOT NULL,
                "verdict" varchar(200) NOT NULL,
                "order" integer NOT NULL,
                "edition_id" bigint NOT NULL REFERENCES "news_roastedition" ("id") DEFERRABLE INITIALLY DEFERRED,
                "member_id" bigint NOT NULL REFERENCES "league_member" ("id") DEFERRABLE INITIALLY DEFERRED
            );
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS "news_roastedition_clown_of_the_week_id_07bddf93" ON "news_roastedition" ("clown_of_the_week_id");')
            cursor.execute('CREATE INDEX IF NOT EXISTS "news_roastedition_king_of_the_week_id_0d129dbc" ON "news_roastedition" ("king_of_the_week_id");')
            cursor.execute('CREATE INDEX IF NOT EXISTS "news_managerroastitem_edition_id_73aea9f1" ON "news_managerroastitem" ("edition_id");')
            cursor.execute('CREATE INDEX IF NOT EXISTS "news_managerroastitem_member_id_91886d09" ON "news_managerroastitem" ("member_id");')
    except Exception:
        pass


SAMPLE_CLASSIFIEDS = [
    {
        'title': 'FOR SALE: Triple Captain Chip',
        'desc': 'Slightly used in GW 1. Yielded 3 points total. Comes with complimentary box of tissues and regret.',
        'contact': 'Call 0700-REGRET-FPL'
    },
    {
        'title': 'LOST & FOUND: Defending Pride',
        'desc': 'Lost somewhere between the 60th and 90th minute. If found, please return to bottom 3 managers.',
        'contact': 'Drop off at Relegation Zone desk'
    },
    {
        'title': 'WANTED: Ksh. 150 Contribution',
        'desc': 'Treasurer is actively scanning M-Pesa. Defaulters will be forced to buy the BBQ charcoal.',
        'contact': 'M-Pesa Paybill #542222'
    },
    {
        'title': 'SERVICES: Professional Excuse Generator',
        'desc': "Expert explanations for why 'Pep Roulette' ruined your weekend. Guaranteed to sound almost believable on WhatsApp.",
        'contact': 'Visit www.itsnotmyfaultfpl.com'
    },
]

WEATHER_REPORTS = [
    'Clear skies at the top of the table. Relegation zone experiencing severe thunder and tactical depression.',
    'Scorching heat on the podium. Mid-table floating in thick tactical fog.',
    'Heavy rain of green arrows for the champion; flash flood of tears in 10th place.',
    'Crisp footballing conditions across the league with high pressure on the bottom managers.',
]


def generate_roast_edition(gameweek: Gameweek, force_update=True) -> RoastEdition:
    """
    Analyzes Gameweek results and payments to generate a savage, hilarious newspaper edition.
    Includes GW1/GW2 fine waiver notices, celebrates winners with swagger, and savages the clowns.
    """
    ensure_news_tables_exist()
    results = list(
        GameweekResult.objects.filter(gameweek=gameweek)
        .select_related('member')
        .order_by('league_rank', '-net_points')
    )
    if not results:
        raise ValueError(f"Cannot generate roasts for GW {gameweek.number}: No results found.")

    payments = {p.member_id: p for p in Payment.objects.filter(gameweek=gameweek, verified=True)}

    winner_res = results[0]
    last_res = results[-1]
    clown_res = last_res
    king_res = winner_res

    # Check for largest hit taker
    hit_takers = [r for r in results if r.transfer_cost > 0]
    hit_takers.sort(key=lambda r: r.transfer_cost, reverse=True)
    biggest_hit_taker = hit_takers[0] if hit_takers else None

    gw_num = gameweek.number
    winner_name = winner_res.member.manager_name.upper()
    last_name = last_res.member.manager_name.upper()

    headline = f"GW {gw_num} CROWN: {winner_name} CLAIMS SUPREME GLORY AS {last_name} ANCHORS THE CLOWN CAR!"
    subheadline = f"Official Issue #{gw_num}: Masterclass at the summit, carnage at the bottom, and an unfiltered autopsy of the weekend."

    # Editorial lead
    editorial_lead = (
        f"Welcome to Issue #{gw_num} of The FPL Boys Gazette! "
        f"Gameweek {gw_num} kicked off with high drama and tactical showdowns across all 10 managers. "
        f"Leading from the front, {winner_res.member.manager_name} ({winner_res.member.team_name}) put on a championship display, amassing a league-high {winner_res.net_points} points to secure top honors and pocket Ksh. {winner_res.gw_prize_won:,.2f} in prize money. "
        f"However, for every champion standing proudly on the podium, there is a casualty in the trenches. "
        f"At the very bottom of the table, {last_res.member.manager_name} ({last_res.member.team_name}) suffered a complete tactical meltdown with only {last_res.net_points} points, officially earning the unwanted wooden spoon. "
        f"Read through the full breakdown below for the complete manager-by-manager autopsy!"
    )

    king_reason = (
        f"{winner_res.member.manager_name} dominated the round with {winner_res.net_points} net points, bagging Ksh. {winner_res.gw_prize_won:,.2f}. "
        f"An imperious showing that sets the early benchmark for the rest of the league to chase!"
    )

    clown_reason = (
        f"{last_res.member.manager_name} collapsed to rank #{last_res.league_rank} with just {last_res.net_points} points. "
        f"A textbook disasterclass that will be studied in tactical defense academies as what NOT to do."
    )

    # Defaulter roast / waiver rules
    if gw_num in [1, 2]:
        defaulter_roast = (
            f"🚨 LEAGUE GRACE PERIOD (GW {gw_num}): The League Committee has officially declared a full grace period for GW 1 & GW 2! "
            f"Zero late penalty fines apply for all managers. Defaulters get a clean slate for the opening fortnight—strict Ksh. 50 fines will be enforced by the Treasurer starting GW 3!"
        )
    else:
        # Check actual late payments
        late_members = [r.member for r in results if payments.get(r.member_id) and payments.get(r.member_id).is_late]
        unpaid_members = [r.member for r in results if not payments.get(r.member_id)]
        if late_members or unpaid_members:
            names = ', '.join([f"{m.manager_name} ({'LATE' if m in late_members else 'UNPAID'})" for m in (late_members + unpaid_members)])
            defaulter_roast = (
                f"Special gratitude to our voluntary BBQ Pot sponsors: {names}. "
                f"Your contributions to the fine fund are deeply appreciated by the meat committee!"
            )
        else:
            defaulter_roast = "All 10 managers paid on time! The Treasurer extends sincere congratulations to the entire league."

    # Hit roast
    if gw_num == 1:
        transfer_hit_roast = (
            "Season Kickoff Window: All 10 managers launched with unlimited free squad selections prior to the GW 1 deadline. "
            "Point-deducting transfer hits unlock from GW 2 onward, where panic transfers and tactical chaos will officially commence!"
        )
    elif biggest_hit_taker:
        transfer_hit_roast = (
            f"Transfer Market Alert: {biggest_hit_taker.member.manager_name} took a -{biggest_hit_taker.transfer_cost} point hit in transfers, "
            f"finishing with {biggest_hit_taker.net_points} net points. A costly gamble that did not quite deliver the expected dividends."
        )
    else:
        transfer_hit_roast = "Zero transfer hits taken this week. Clean discipline across the entire mini-league!"

    quote_of_the_week = f"\"My rank is only temporary. By Gameweek 38, they will see the vision.\" — {last_res.member.manager_name}"
    quote_author = f"{last_res.member.manager_name} (Post-Match Presser)"

    weather = random.choice(WEATHER_REPORTS)

    with transaction.atomic():
        edition, created = RoastEdition.objects.update_or_create(
            gameweek=gameweek,
            defaults={
                'edition_number': gw_num,
                'headline': headline,
                'subheadline': subheadline,
                'publish_date': timezone.now(),
                'chief_editor': 'The League Scribe & Chief Correspondent',
                'weather_report': weather,
                'editorial_lead': editorial_lead,
                'clown_of_the_week': clown_res.member,
                'clown_reason': clown_reason,
                'king_of_the_week': king_res.member,
                'king_reason': king_reason,
                'quote_of_the_week': quote_of_the_week,
                'quote_author': quote_author,
                'defaulter_roast': defaulter_roast,
                'transfer_hit_roast': transfer_hit_roast,
                'classified_ads': [],
                'is_published': True,
            }
        )

        # Remove old manager roasts if updating
        edition.manager_roasts.all().delete()

        # Create individual manager roasts
        for r in results:
            rank = r.league_rank
            pts = r.net_points
            hits = r.transfer_cost
            manager = r.member
            is_last = (r == last_res)

            if rank == 1:
                badge = '👑 1ST PLACE (CHAMPION)'
                title = f"{manager.manager_name} - Tactical Masterclass & GW Winner"
                body = (
                    f"{manager.manager_name}'s {manager.team_name} delivered a statement performance with a magnificent {pts} points, "
                    f"clinching 1st place and Ksh. {r.gw_prize_won:,.2f} in prize money. Sharp captaincy and clinical returns gave them total command of the gameweek."
                )
                verdict = 'Verdict: Certified Baller & League Leader'
            elif is_last and len(results) > 1:
                badge = '🤡 CLOWN OF THE GAMEWEEK'
                title = f"{manager.manager_name} - The League Punchline"
                body = (
                    f"An unforgettable disasterclass of {pts} points to claim the undisputed wooden spoon at rank #{rank}. "
                    f"Your team didn't just underperform—it committed a footballing felony. Group chat banter is going to be merciless."
                )
                verdict = 'Verdict: Delete App & Try Checkers'
            elif rank == 2:
                badge = '🥈 2ND PLACE (SILVER PODIUM)'
                title = f"{manager.manager_name} - High-Flying Silver Finish"
                body = (
                    f"A fantastic round scoring {pts} points to take 2nd place and Ksh. {r.gw_prize_won:,.2f}. "
                    f"Pushed the champion right down to the final whistle. High-class fantasy management."
                )
                verdict = 'Verdict: Title Contender'
            elif rank == 3:
                badge = '🥉 3RD PLACE (BRONZE PODIUM)'
                title = f"{manager.manager_name} - Money In The Bank"
                body = (
                    f"Scored {pts} points to secure the final podium cash prize of Ksh. {r.gw_prize_won:,.2f}. "
                    f"Solid and effective execution when it mattered most."
                )
                verdict = 'Verdict: Podium Secured'
            elif 4 <= rank <= 7:
                badge = '😴 MID-TABLE PURGATORY'
                title = f"{manager.manager_name} - Floating in the Middle"
                hit_note = f" (after -{hits} transfer deduction)" if hits > 0 else ""
                body = (
                    f"Recorded {pts} net points{hit_note} to settle into rank #{rank}. "
                    f"Just a few points away from the podium money. Decent foundation, but needs a sharper captaincy pick to challenge for the top."
                )
                verdict = 'Verdict: Sleeping Giant'
            elif 8 <= rank <= 9:
                badge = '💀 RELEGATION SINKHOLE'
                title = f"{manager.manager_name} - Dangerously Close to the Bottom"
                body = (
                    f"A difficult round ending with {pts} points at rank #{rank}. "
                    f"Defenders conceded, forwards blanked, and the bench points are looking painful. Urgent tactical surgery required before next deadline."
                )
                verdict = 'Verdict: Code Red Alert'
            else:
                badge = '🤡 CLOWN OF THE GAMEWEEK'
                title = f"{manager.manager_name} - The League Punchline"
                body = (
                    f"An unforgettable disasterclass of {pts} points at rank #{rank}. "
                    f"Please submit an apology letter to the group chat immediately."
                )
                verdict = 'Verdict: Needs Divine Intervention'

            ManagerRoastItem.objects.create(
                edition=edition,
                member=manager,
                rank_in_gw=rank,
                net_points=pts,
                badge=badge,
                roast_title=title,
                roast_body=body,
                verdict=verdict,
                order=rank
            )

    return edition

