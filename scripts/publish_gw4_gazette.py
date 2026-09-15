import os
import sys
import django
from decimal import Decimal
from django.utils import timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fpl_boys.settings')
django.setup()

from league.models import Gameweek, Member, GameweekResult
from news.models import RoastEdition, ManagerRoastItem
from news.services.roast_engine import ensure_news_tables_exist
from news.services.gazette_storage import export_edition_to_disk


def publish_gw4():
    ensure_news_tables_exist()
    gw = Gameweek.objects.get(number=4)

    # 1. Update GameweekResult prize allocations:
    # Samuel: 250.00, Bright: 166.67, Aron: 41.67, Marvin: 41.67, Benn: 0.00 (Disqualified / Flagged)
    payout_map = {
        'Samuel': Decimal('250.00'),
        'Bright': Decimal('166.67'),
        'Aron': Decimal('41.67'),
        'Marvin': Decimal('41.67'),
    }

    for res in GameweekResult.objects.filter(gameweek=gw).select_related('member'):
        m_name = res.member.manager_name
        prize = Decimal('0.00')
        is_top3 = False
        for k, p in payout_map.items():
            if k in m_name:
                prize = p
                is_top3 = True
                break
        res.gw_prize_won = prize
        res.is_top3 = is_top3
        res.save(update_fields=['gw_prize_won', 'is_top3'])

    # 2. Build 100% Factual & Savage Broadsheet Content
    headline = "GW 4 MAYHEM: SAMUEL'S 90-PT SPREE, BRIGHT'S BENCH HEIST, BENN'S FORFEITED PODIUM CASH, & ERICK'S CLOWN COLLAPSE!"
    subheadline = "Issue #4 Broadsheet: Pascal Groß runs riot in Brighton's 5-0 win, Benn forfeits Ksh. 83 while benching 14-pt Davis, Bruno Derby captaincy tears, and all 10 managers take zero hits."
    
    chief_editor = "The League Scribe & Chief Banter Autopsist"
    weather_report = "Bright sunshine and incoming cash for Samuel & Bright; freezing cold bankruptcy in the Defaulter Ward for Benn and King Chris."

    editorial_lead = (
        "Gameweek 4 delivered astronomical scores, flawless transfer discipline, and ruthless financial drama across our 10-man battleground. "
        "Reigning supreme at the summit, Samuel Wambua ('maggry shiners fc') unleashed a 90-point hurricane powered by a sensational 17-point haul from Pascal Groß (1 goal, 2 assists in Brighton's 5-0 rout of Coventry) and Erling Haaland's captaincy (18 pts) to claim 1st place and pocket Ksh. 250.00! "
        "Hot on his heels, Bright Ottore ('Phill Me In FC') scored an imperious 88 points to bag Ksh. 166.67—all while continuing his sacred ritual of stranding 12 points on his luxury bench! "
        "However, the round's greatest financial tragedy belongs to Benn Mwangi: after scoring a brilliant 78 points on the pitch, his unpaid treasury dues meant his Ksh. 83.33 cash prize was forfeited and rolled down to Aron Mangati and Marvin Owino (Ksh. 41.67 each)! To compound his misery, Benn also left a 14-point Leif Davis haul (goal & 2 assists for Ipswich) frozen on his bench. "
        "Meanwhile, in the Manchester Derby (Man Utd 0-1 Man City), King Chris and Erick Muchira formed a delusional 'Bruno Fernandes Captaincy Cult' (4 pts) while watching Haaland score the derby winner. "
        "Erick's 'mambaaa' suffered a total blackout with a league-lowest 52 points, earning the undisputed GW 4 Wooden Spoon Clown Crown!"
    )

    samuel = Member.objects.filter(manager_name__icontains="Samuel").first()
    erick = Member.objects.filter(manager_name__icontains="Erick").first()

    king = samuel
    king_reason = (
        "Samuel 'maggry shiners fc' Wambua orchestrated a 90-point masterclass. "
        "His Pascal Groß (17 pts) differential combined with captain Haaland (18 pts) and João Pedro (12 pts) conquered the league and banked the Ksh. 250.00 top prize!"
    )

    clown = erick
    clown_reason = (
        "Erick 'mambaaa' Muchira crashed straight into the basement with an embarrassing 52 net points (a massive 11 points behind 9th place). "
        "Captaining Bruno Fernandes in a 0-1 derby loss while leaving Murillo (6 pts) on the bench earned Erick the undisputed GW 4 Wooden Spoon Clown Hat!"
    )

    quote_of_the_week = "\"I was convinced Bruno would orchestrate the Manchester Derby. Instead, Haaland scored the winner, Bruno blanked, and the Treasurer fined me.\" — King Chris"
    quote_author = "King Chris (Treasury Defaulter & Derby Survivor)"

    defaulter_roast = (
        "🚨 TREASURY WALL OF SHAME (GW 4): Benn Mwangi and King Chris have officially taken over the league sponsorship department! "
        "Benn's failure to clear his Ksh. 150 contribution cost him a Ksh. 83.33 podium prize that was redistributed to Aron and Marvin. "
        "Meanwhile, King Chris remains a permanent VIP resident of the fine ledger for the second consecutive week. Sincere gratitude from the BBQ Pot Committee!"
    )

    transfer_hit_roast = (
        "💥 THE TRANSFER MARKET REPORT: Flawless transfer discipline across the entire mini-league! "
        "All 10 managers took ZERO transfer hits (-0 pts) in Gameweek 4. "
        "Four tacticians (Samuel, Benn, Aron, Marvin) rolled over their free transfers, while the other six made precise free swaps. "
        "The real financial bleeding this week wasn't from transfer hits—it was the forfeited prize money from our flagged defaulters!"
    )

    classifieds = [
        {
            'title': 'FOR SALE: Benn’s Unclaimed Ksh. 83 Prize',
            'desc': 'Slightly used 3rd place finish. Forfeited due to outstanding M-Pesa balance. Enjoyed thoroughly by Aron and Marvin.',
            'contact': 'Call 0700-FREE-MONEY'
        },
        {
            'title': 'LOST & FOUND: Leif Davis (14 Points)',
            'desc': 'Found sitting frozen on Benn Mwangi’s bench alongside 15 total bench points after Ipswich’s 3-2 win. Please return to starting XI.',
            'contact': 'Drop off at Odysseus Subs Bench'
        },
        {
            'title': 'WANTED: Bruno Derby Captaincy Rehab',
            'desc': 'Support group meeting every Tuesday for King Chris and Erick. Coffee, tissues, and Haaland apology forms provided.',
            'contact': 'Visit www.stopcaptainingbruno.com'
        },
        {
            'title': 'PUBLIC NOTICE: Treasury Meat Fund Secured',
            'desc': 'Thanks to repeat contributions from Benn and King Chris, the end-of-season nyama choma budget is looking magnificent.',
            'contact': 'M-Pesa Paybill / Treasury Desk'
        }
    ]

    edition, created = RoastEdition.objects.update_or_create(
        gameweek=gw,
        defaults={
            'edition_number': 4,
            'headline': headline,
            'subheadline': subheadline,
            'publish_date': timezone.now(),
            'chief_editor': chief_editor,
            'weather_report': weather_report,
            'editorial_lead': editorial_lead,
            'clown_of_the_week': clown,
            'clown_reason': clown_reason,
            'king_of_the_week': king,
            'king_reason': king_reason,
            'quote_of_the_week': quote_of_the_week,
            'quote_author': quote_author,
            'defaulter_roast': defaulter_roast,
            'transfer_hit_roast': transfer_hit_roast,
            'classified_ads': classifieds,
            'is_published': True,
        }
    )

    edition.manager_roasts.all().delete()

    roasts_data = [
        # Rank 1: Samuel Wambua
        {
            'name_match': 'Samuel',
            'rank': 1,
            'net_pts': 90,
            'badge': '👑 1ST PLACE (90-PT CHAMPION)',
            'title': "Samuel Wambua - 'maggry shiners' 90-Point Masterclass & Top Prize",
            'body': "A footballing symphony of the highest order! Samuel rolled his transfer and tore the competition to shreds with a breathtaking 90 net points. His inspired Pascal Groß differential returned a monster 17 points (1 goal, 2 assists in Brighton's 5-0 thrashing of Coventry), perfectly complemented by captain Haaland (18 pts), João Pedro (12 pts), and Joško Gvardiol (11 pts). Sits indisputably atop the podium with Ksh. 250.00 in cash!",
            'verdict': "Verdict: Supreme 90-Point Baller & Cash King (Ksh. 250.00)",
        },
        # Rank 2: Bright Ottore
        {
            'name_match': 'Bright',
            'rank': 2,
            'net_pts': 88,
            'badge': '🥈 2ND PLACE (BENCH HEIST SILVER)',
            'title': "Bright Ottore - 'Phill Me In' Bags Silver Despite 12 Benched Points!",
            'body': "Bright is operating in another tactical dimension. Even with Cole Palmer returning a modest 10 points as captain and 12 valuable points idling on his luxury bench, Groß (17 pts), João Pedro (12 pts), and Maxim De Cuyper (11 pts) detonated for 88 points! Bright bags Ksh. 166.67 and cements his status as the league's most dangerous bench manager.",
            'verdict': "Verdict: Silver Podium Master & Luxury Bench King (Ksh. 166.67)",
        },
        # Rank 3: Benn Mwangi
        {
            'name_match': 'Benn',
            'rank': 3,
            'net_pts': 78,
            'badge': '💸 3RD ON PITCH (DISQUALIFIED & FINED)',
            'title': "Benn Mwangi - 'Odysseus Reign' Scores 78 pts But Forfeits Ksh. 83 & Benches 14-pt Davis!",
            'body': "The ultimate tragedy in FPL Boys history! Benn played brilliantly on the pitch for 78 points (Groß 17 pts, João Pedro 12 pts, Haaland 18 pts) to claim 3rd place... only to discover he was FLAGGED for unpaid dues! His Ksh. 83.33 prize was promptly stripped and handed to Aron and Marvin. To add comedic misery, Benn left a 14-point haul from Leif Davis on his 15-point bench!",
            'verdict': "Verdict: Scored 78 pts, Benched 14 pts, Donated Ksh. 83 (Ksh. 0.00 + Fine)",
        },
        # Rank 4 (Tied): Aron Mangati
        {
            'name_match': 'Aron',
            'rank': 4,
            'net_pts': 77,
            'badge': '💰 4TH PLACE (BENN ROLLDOWN BENEFICIARY)',
            'title': "Aron Mangati - 'Arons' Snaps Up 77 Points & Free Rolldown Cash!",
            'body': "Aron's consistent form continues to pay dividends. Rolling over his transfer and riding João Pedro (12 pts), De Cuyper (11 pts), Tarkowski (8 pts), and captain Haaland (18 pts) to 77 points, Aron tied for 4th. And because Benn forgot to pay his treasury fee, Aron happily walked into the bank to collect Ksh. 41.67 in rolled-down prize money. Pure financial opportunism!",
            'verdict': "Verdict: Consistent Heavyweight & Rolldown Winner (Ksh. 41.67)",
        },
        # Rank 4 (Tied): Marvin Owino
        {
            'name_match': 'Marvin',
            'rank': 4,
            'net_pts': 77,
            'badge': '🥉 4TH PLACE (DON BOSCO ROLLDOWN CASH)',
            'title': "Marvin Owino - 'Don Bosco' Strikes 77 Points & Banks Rolldown Prize",
            'body': "Don Bosco's miraculous revival continues in GW 4! Matching Aron stride for stride with 77 points (João Pedro 12 pts, De Cuyper 11 pts, Tarkowski 8 pts, Haaland 18 pts), Marvin also profited from Benn's financial blunder to bank Ksh. 41.67 in cash. Two consecutive gameweeks in the money for Don Bosco!",
            'verdict': "Verdict: Divine Intervention & Rolldown Cash (Ksh. 41.67)",
        },
        # Rank 6: Renny Muragu
        {
            'name_match': 'Renny',
            'rank': 6,
            'net_pts': 75,
            'badge': '📈 6TH PLACE (CLOWN ESCAPE)',
            'title': "Renny Muragu - 'The Young Ones' Rebound from Wooden Spoon Trauma",
            'body': "A much-needed recovery for Renny! After his GW 3 Wooden Spoon nightmare, 'The Young Ones' posted a strong 75 net points with zero transfer hits. João Pedro (12 pts), Gvardiol (11 pts), and Haaland (18 pts) restored his dignity, though 8 points abandoned on the bench prevented a podium push.",
            'verdict': "Verdict: Dignity Restored, Wooden Spoon Returned (75 pts, 0 Hits)",
        },
        # Rank 7: Marve Mathingu
        {
            'name_match': 'Marve',
            'rank': 7,
            'net_pts': 67,
            'badge': '🧤 7TH PLACE (SCHADE & RAYA SHOW)',
            'title': "Marve Mathingu - 'Marve of the Match' Carried by Schade & Raya",
            'body': "After the infamous Cherki Triple Captain saga in GW 3, Marve pivoted to sanity. Differential maestro Kevin Schade delivered a sensational 15 points (2 goals in Brentford's 2-2 at Bournemouth), while David Raya pulled off a 14-point goalkeeping masterclass at Sunderland. Unfortunately, with Saka captaincy returning 16 pts and the rest of his outfield sleeping, Marve settled for rank #7 with 67 points.",
            'verdict': "Verdict: Goalkeeping Heroics in Mid-Table (67 pts)",
        },
        # Rank 8: Torque Dennis
        {
            'name_match': 'Dennis',
            'rank': 8,
            'net_pts': 64,
            'badge': '📉 8TH PLACE (POST-CHAMPIONSHIP SLUMP)',
            'title': "Torque Dennis - 'DenniSkills' Sinks from Summit to 8th",
            'body': "The champion's hangover hit Dennis hard! Following his glorious Gameweek 3 victory, 'DenniSkills' dropped to 64 points in GW 4. Beyond João Pedro (12 pts), Haaland (18 pts), and Gabriel (9 pts), his midfield completely evaporated. Dennis survives the bottom only because the Bruno Cult collapsed beneath him.",
            'verdict': "Verdict: Dethroned from the Summit (64 pts)",
        },
        # Rank 9: King Chris
        {
            'name_match': 'Chris',
            'rank': 9,
            'net_pts': 63,
            'badge': '🤡 9TH PLACE (REPEAT DEFAULTER & BRUNO CULT)',
            'title': "King Chris - The Painter's Derby Disaster: Bruno Armband, Rank 9 & BBQ Fine!",
            'body': "A comedy of errors worthy of an Oscar! For the THIRD week in a row, King Chris blindly trusted Bruno Fernandes with the captain's armband for a microscopic 4 points in a 0-1 Manchester Derby defeat (wasting Haaland's 18 pts). Even Raya (14 pts), João Pedro (12 pts), and DCL (10 pts) couldn't save him from rank #9. To cap it all off, Chris was FLAGGED as an unpaid defaulter again!",
            'verdict': "Verdict: Honorary President of the Fine & Armband Disaster Club",
        },
        # Rank 10: Erick Muchira
        {
            'name_match': 'Erick',
            'rank': 10,
            'net_pts': 52,
            'badge': '🤡 10TH PLACE (WOODEN SPOON CLOWN)',
            'title': "Erick Muchira - 'mambaaa' Crashes by 11 Points for the Wooden Spoon!",
            'body': "The undisputed catastrophe of Gameweek 4! Erick joined King Chris in the delusional Bruno Fernandes Captaincy Cult (4 pts in the Manchester Derby), while Murillo (6 pts) mocked him from the bench. With 5 starting outfield players scoring 2 points or fewer, 'mambaaa' suffered a total blackout with 52 net points—finishing a whopping 11 points adrift of 9th place!",
            'verdict': "Verdict: Undisputed GW 4 Wooden Spoon Clown Crown Holder",
        },
    ]

    for idx, rdata in enumerate(roasts_data):
        member = Member.objects.filter(manager_name__icontains=rdata['name_match']).first()
        if not member:
            continue

        ManagerRoastItem.objects.create(
            edition=edition,
            member=member,
            rank_in_gw=rdata['rank'],
            net_points=rdata['net_pts'],
            badge=rdata['badge'],
            roast_title=rdata['title'],
            roast_body=rdata['body'],
            verdict=rdata['verdict'],
            order=idx + 1
        )

    export_edition_to_disk(edition)
    print(f"[SUCCESS] Gazette Issue #{edition.edition_number} for GW {gw.number} published and exported to news/editions/gw4.json successfully!")


if __name__ == '__main__':
    publish_gw4()
