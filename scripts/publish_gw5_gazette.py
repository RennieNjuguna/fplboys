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


def publish_gw5():
    ensure_news_tables_exist()
    gw = Gameweek.objects.get(number=5)

    # 1. Update GameweekResult prize allocations:
    # Tied Rank 1: Marvin (61 pts) = 208.34, Samuel (61 pts) = 208.33
    # Rank 3: Renny (55 pts) = 83.33
    # Chris & Dennis = Flagged/Unpaid -> Disqualified
    payout_map = {
        'Marvin': Decimal('208.34'),
        'Samuel': Decimal('208.33'),
        'Renny': Decimal('83.33'),
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

    # 2. Build Broadsheet Content (Harder Roasts + International Break Theme)
    headline = "GW 5 CARNAGE: MARVIN & SAMUEL SHARE THE THRONE, BENN BENCHES 14-PT GROSS, & KING CHRIS CRASHES TO A HISTORIC 20-PT DISASTER!"
    subheadline = "Issue #5 International Break Special: Two full weeks of misery for King Chris's 20-point horror show, Benn's repeat bench crime, Dennis's fine ledger debut, and Don Bosco cash dividends."
    
    chief_editor = "The League Scribe & Chief Banter Executioner"
    weather_report = "100% chance of emotional depression, freezing financial frost in the Defaulter Ward, and a dark 14-day international break drought."

    editorial_lead = (
        "Welcome to the pre-International Break autopsy of Gameweek 5, where our managers must now marinate in their shame for two agonizing weeks without Premier League football to save them! "
        "At the summit, Marvin Owino ('Don Bosco') and Samuel Wambua ('maggry shiners fc') tied with 61 net points to split 1st and 2nd place cash (Ksh. 208.34 each), powered by Pascal Groß's 14-point demolition of Arsenal in Brighton's 3-0 masterclass. "
        "Taking 3rd place cash (Ksh. 83.33), Renny Muragu pulled off the luckiest Wildcard in human history—captaining Morgan Gibbs-White for 4 points, benching 15 points, and still finishing on the podium! "
        "However, this week's banter hall belongs to two men: Benn Mwangi, who committed his second consecutive felony by benching a 14-point Pascal Groß (costing himself the outright title), and King Chris, who delivered a legendary 20-POINT COLLAPSE! "
        "Not a single starting outfield player in Chris's team scored more than 2 points, and to put the cherry on top, he was FLAGGED for unpaid dues for the third week running alongside Torque Dennis. "
        "Sit tight, gentlemen—you have 336 hours over the international break to think about what you've done!"
    )

    marvin = Member.objects.filter(manager_name__icontains="Marvin").first()
    chris = Member.objects.filter(manager_name__icontains="Chris").first()

    king = marvin
    king_reason = (
        "Marvin 'Don Bosco' Owino delivered tactical purity: zero transfer hits, zero bench waste, and a clutch 61 net points to share the GW 5 championship and bank Ksh. 208.34!"
    )

    clown = chris
    clown_reason = (
        "King Chris painted the ultimate disasterpiece: a historic, jaw-dropping 20 NET POINTS! "
        "Captaining Gibbs-White for 4 points while every single starter blanked with 2 points or fewer—plus being flagged for unpaid dues for the 3rd week running—earns him the undisputed Crown Clown of the Fortnight!"
    )

    quote_of_the_week = "\"Twenty points. I scored twenty points. And now I have to look at this red arrow for two entire weeks with no Premier League games to heal me.\" — King Chris"
    quote_author = "King Chris (International Break Survivor & 20-Point Record Holder)"

    defaulter_roast = (
        "🚨 TREASURY WALL OF SHAME (GW 5): The BBQ Meat Pot is overflowing! "
        "King Chris has achieved the fabled three-peat, defaulting on his dues for the 3rd consecutive gameweek to cement his status as League Patron of Nyama Choma. "
        "Joining him in the defaulters' penalty box this week is Torque Dennis, who crashed to rank #8 with 45 points and an unpaid fine. "
        "Both gentlemen have two full weeks during the international break to visit M-Pesa and reflect on their sins!"
    )

    transfer_hit_roast = (
        "💥 THE TRANSFER MARKET REPORT: Transfer hits returned with venom! "
        "Three managers burned -4 hits: Samuel Wambua (-4, finished T-1st on 61 pts), Aron Mangati (-4, finished 49 pts), and Marve Mathingu (-4, finished 42 pts). "
        "Meanwhile, two managers triggered their WILDCARD chips: Renny Muragu (55 pts, podium cash) and Erick Muchira (49 pts). "
        "The smartest tactician was Marvin Owino, who made 2 free transfers with ZERO point deductions to win the gameweek!"
    )

    classifieds = [
        {
            'title': 'HOTLINE: 20-Point Trauma Helpline',
            'desc': 'Free psychological counseling available 24/7 during the international break for King Chris. Grief counselors standing by.',
            'contact': 'Call 0800-TWENTY-POINTS'
        },
        {
            'title': 'WANTED: Benn Mwangi’s Bench Radar',
            'desc': 'GW4: Benched Leif Davis (14 pts). GW5: Benched Pascal Groß (14 pts). Willing to trade for a manager who knows how to pick a starting XI.',
            'contact': 'Drop off at Odysseus Subs Bench'
        },
        {
            'title': 'FOR SALE: Morgan Gibbs-White Armband',
            'desc': 'Slightly used captaincy armband worn by Renny (4 pts) and King Chris (4 pts) in a 1-0 loss to Coventry City. Comes with instant regret.',
            'contact': 'Visit www.whycaptainhim.com'
        },
        {
            'title': 'TREASURY NOTICE: 14-Day Payment Window',
            'desc': 'No matches this weekend means no excuses! Chris and Dennis must settle their Ksh. 150 + fines before GW 6 kicks off.',
            'contact': 'M-Pesa Paybill / Treasurer'
        }
    ]

    edition, created = RoastEdition.objects.update_or_create(
        gameweek=gw,
        defaults={
            'edition_number': 5,
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
        # Rank 1 (Tied): Marvin Owino
        {
            'name_match': 'Marvin',
            'rank': 1,
            'net_pts': 61,
            'badge': '👑 1ST PLACE (CLEAN SHEET MASTERMIND)',
            'title': "Marvin Owino - 'Don Bosco' Purity: Zero Hits, Zero Bench Waste, & Ksh. 208 Cash!",
            'body': "Tactical perfection from the pulpit of Don Bosco! Marvin made two seamless free transfers, took zero hits, left ZERO points on his bench, and let Pascal Groß (14 pts in Brighton's 3-0 dismantling of Arsenal) and captain Haaland (12 pts) fire him to 61 net points. Shares 1st place and banks Ksh. 208.34! Don Bosco is officially the form team of the league.",
            'verdict': "Verdict: Flawless Execution & Joint Champion (Ksh. 208.34)",
        },
        # Rank 1 (Tied): Samuel Wambua
        {
            'name_match': 'Samuel',
            'rank': 1,
            'net_pts': 61,
            'badge': '👑 1ST PLACE (GROSS DIFFERENTIAL KING)',
            'title': "Samuel Wambua - 'maggry shiners' Overcomes -4 Hit to Retain the Crown",
            'body': "Samuel continues to bully the competition! Even after taking an aggressive -4 transfer hit (65 gross points), his loyalty to Pascal Groß (14 pts), Kevin Schade (9 pts), Rayan Cherki (8 pts), and captain Haaland (12 pts) pushed him to 61 net points. Back-to-back gameweeks on top of the podium, pocketing another Ksh. 208.33 to take into the break!",
            'verdict': "Verdict: Relentless Heavyweight & Joint Champion (Ksh. 208.33)",
        },
        # Rank 3: Renny Muragu
        {
            'name_match': 'Renny',
            'rank': 3,
            'net_pts': 55,
            'badge': '🥉 3RD PLACE (WILDCARD CASH JAM)',
            'title': "Renny Muragu - 'The Young Ones' Flukes Podium Cash Despite 15 Benched Points!",
            'body': "A masterclass in failing upward! Renny activated his WILDCARD, galaxy-brained the captaincy onto Morgan Gibbs-White for 4 points (in a 0-1 home loss to Coventry!), and left 15 points rotting on his bench (Mitchell 7p, Tzolakis 6p). Yet, thanks to James Tarkowski's 14-point monster haul and absolute carnage beneath him, Renny stumbled straight onto the podium for Ksh. 83.33!",
            'verdict': "Verdict: Luckiest Wildcard on Earth & Bronze Winner (Ksh. 83.33)",
        },
        # Rank 4: Bright Ottore
        {
            'name_match': 'Bright',
            'rank': 4,
            'net_pts': 53,
            'badge': '🪑 4TH PLACE (BENCH HOARDING CONTINUES)',
            'title': "Bright Ottore - 'Phill Me In' Benches 11 Points to Narrowly Miss the Money",
            'body': "Death, taxes, and Bright Ottore stranding double-digit hauls on his substitutes' bench! Bright started Pascal Groß (14 pts) and captain Haaland (12 pts), but left Omari Thomas (9 pts) chilling on the pine alongside 11 total bench points. Those 9 benched points would have easily propelled him to 1st place and Ksh. 250.00 cash. Instead, he spends the break in 4th place with empty pockets!",
            'verdict': "Verdict: Luxury Bench Addiction Costs Him Cold Hard Cash",
        },
        # Rank 5 (Tied): Aron Mangati
        {
            'name_match': 'Aron',
            'rank': 5,
            'net_pts': 49,
            'badge': '💥 5TH PLACE (TRANSFER HIT SINKHOLE)',
            'title': "Aron Mangati - 'Arons' Burned by -4 Hit to Fall Out of the Money",
            'body': "A costly tactical gamble. Aron had James Tarkowski (14 pts), captain Haaland (12 pts), and Cherki (8 pts) firing, but an ill-timed -4 transfer penalty dragged his 53 gross points down to 49 net. After two straight weeks of collecting cash prizes, Aron leaves GW 5 empty-handed to contemplate his transfer budget over the international break.",
            'verdict': "Verdict: Transfer Hit Threw Away the Podium",
        },
        # Rank 5 (Tied): Erick Muchira
        {
            'name_match': 'Erick',
            'rank': 5,
            'net_pts': 49,
            'badge': '🃏 5TH PLACE (WILDCARD TO NOWHERE)',
            'title': "Erick Muchira - 'mambaaa' Burns Wildcard Only to Crawl to 49 Points",
            'body': "After his GW 4 Wooden Spoon catastrophe, Erick hit the emergency WILDCARD panic button. The result? A lukewarm 49 net points. Beyond Haaland (12 pts) and Schade (9 pts), his shiny new squad failed to ignite, with 6 points left on the bench. He escaped the basement, but spending your most prized chip just to finish 5th is a bitter pill to swallow for two whole weeks.",
            'verdict': "Verdict: Wildcard Fired, Threat Minimal",
        },
        # Rank 7: Benn Mwangi
        {
            'name_match': 'Benn',
            'rank': 7,
            'net_pts': 48,
            'badge': '🤦 7TH PLACE (BENCHED 14-PT GROSS!)',
            'title': "Benn Mwangi - 'Odysseus Reign' Commits Repeat Bench Felony: 14-PT GROSS BENCHED!",
            'body': "Someone call the footballing authorities! In GW 4, Benn benched Leif Davis (14 pts). In GW 5, Benn outdid himself by BENCHING PASCAL GROß (14 PTS)! He left a staggering 16 points on his bench while watching Lewis Hall (13 pts) and Haaland (12 pts) fight alone on the pitch. Had Benn simply started Groß, he would have scored 62 points and won the entire gameweek outright! Two weeks of nightmares await.",
            'verdict': "Verdict: Serial Bench Criminal & Self-Sabotage World Champion",
        },
        # Rank 8: Torque Dennis
        {
            'name_match': 'Dennis',
            'rank': 8,
            'net_pts': 45,
            'badge': '💸 8TH PLACE (FLAGGED DEFAULTER & SLUMP)',
            'title': "Torque Dennis - 'DenniSkills' Plunges to 45 pts & Lands on the Fine Ledger!",
            'body': "From the penthouse straight to the doghouse! Dennis followed up his GW 3 triumph with an abysmal 45-point collapse. Lewis Hall's 13 points couldn't mask the total failure of his midfield, while 11 points (including 9-pt Thomas) chilled on his bench. To make matters worse, Dennis was FLAGGED as an unpaid defaulter! Two long weeks to find his tactical skills and his M-Pesa pin.",
            'verdict': "Verdict: Flagged, Fined, and Frostbitten in 8th Place",
        },
        # Rank 9: Marve Mathingu
        {
            'name_match': 'Marve',
            'rank': 9,
            'net_pts': 42,
            'badge': '💀 9TH PLACE (-4 HIT & NEAR-CLOWN STATUS)',
            'title': "Marve Mathingu - 'Marve of the Match' Sinks to 42 pts After -4 Penalty",
            'body': "Marve is living dangerously close to the abyss. After his GW 3 Cherki comedy, Marve swallowed another -4 point deduction only to muster a pathetic 42 net points. Beyond captain Haaland (12 pts) and Schade (9 pts), his outfield completely deserted him, while Verbruggen's 6 points mocked him from the bench. He only escaped the clown hat because King Chris broke the universe.",
            'verdict': "Verdict: Saved from the Wooden Spoon by a Historic Miracle",
        },
        # Rank 10: King Chris
        {
            'name_match': 'Chris',
            'rank': 10,
            'net_pts': 20,
            'badge': '🤡 10TH PLACE (HISTORIC 20-PT DISASTER & 3-PEAT DEFAULTER)',
            'title': "King Chris - The 20-Point Horror Show: The Worst Disaster in FPL Boys History!",
            'body': "BEHOLD THE DISASTERPIECE OF THE DECADE! King Chris didn't just lose; he redefined the depths of human failure with TWENTY NET POINTS. He captained Morgan Gibbs-White for 4 points, watched Arsenal's defense get demolished 3-0 by Brighton (Saliba 0p, Gabriel 0p, Calafiori 0p), and had NOT A SINGLE OUTFIELD STARTER SCORE MORE THAN 2 POINTS! To crown this immortal disasterclass, Chris was FLAGGED for unpaid dues for the 3rd CONSECUTIVE WEEK! A fortnight of pure, unadulterated shame awaits.",
            'verdict': "Verdict: Undisputed 20-Point Wooden Spoon Legend & Permanent BBQ Pot Sponsor",
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
    print(f"[SUCCESS] Gazette Issue #{edition.edition_number} for GW {gw.number} published and exported to news/editions/gw5.json successfully!")


if __name__ == '__main__':
    publish_gw5()
