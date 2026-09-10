import os
import sys
import django
from django.utils import timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fpl_boys.settings')
django.setup()

from league.models import Gameweek, Member, GameweekResult
from news.models import RoastEdition, ManagerRoastItem
from news.services.roast_engine import ensure_news_tables_exist


def publish_gw3():
    ensure_news_tables_exist()
    gw = Gameweek.objects.get(number=3)

    headline = "GW 3 MASSACRE: DENNIS REIGNS SUPREME, MARVE'S CHERKI TRIPLE CAPTAIN COMEDY, AND BRIGHT BENCHES 23 POINTS!"
    subheadline = "Issue #3 Broadsheet: Wildcard gambles galore, the ultimate Triple Captain catastrophe, Bruno captaincy tears, and the Wooden Spoon finds a new home."
    
    chief_editor = "The League Scribe & Chief Banter Officer"
    weather_report = "Hailstorm of transfer hits, freezing temperatures on the bench, and scorching fires under unpaid defaulters."

    editorial_lead = (
        "Gameweek 3 delivered pure, unadulterated FPL theatre across our 10-man battleground. "
        "At the summit, Dennis Njuguna ('DenniSkills') showcased supreme tactical discipline, amassing 59 net points to conquer 1st place on the pitch. "
        "Meanwhile, Aron Mangati activated an aggressive early Wildcard to seize 2nd with 57 points, capitalizing on league payout eligibility to walk away with the cold hard Ksh. 250.00 cash prize! "
        "However, this week's history books belong to the comedic chaos: Marve Mathingu pulled the trigger on a Triple Captain chip on Rayan Cherki alongside an 8-point transfer hit—returning a tragic 9 points total from his chip. "
        "Not to be outdone, Bright Ottore continued his legendary benching tradition by leaving a mammoth 23 points stranded on his pine. "
        "At the bottom of the table, Renny Muragu's 'The Young Ones' collapsed to 37 net points with an unnecessary transfer hit, proudly taking possession of the GW 3 Wooden Spoon Clown Crown!"
    )

    # King of the week: Dennis (pitch winner) or Aron (cash king)
    dennis = Member.objects.filter(manager_name__icontains="Dennis").first()
    aron = Member.objects.filter(manager_name__icontains="Aron").first()
    renny = Member.objects.filter(manager_name__icontains="Renny").first()
    marve = Member.objects.filter(manager_name__icontains="Marve").first()

    king = dennis or aron
    king_reason = (
        "Dennis 'DenniSkills' Njuguna conquered the round with 59 net points through textbook squad balance (Haaland captaincy + Marc Guéhi & Giles hauls). "
        "Special executive salute to Aron Mangati whose calculated Wildcard overhaul earned 57 points and secured the entire Ksh. 250.00 weekly prize pot!"
    )

    clown = renny
    clown_reason = (
        "Renny 'The Young Ones' Muragu crashed straight to the basement with a league-worst 37 net points after taking a -4 transfer hit. "
        "With 10 points left on the bench and zero tactical rescue from his squad, Renny takes home the GW 3 Wooden Spoon in style."
    )

    quote_of_the_week = "\"Cherki had the underlying metrics in training. The algorithms just didn't translate to Premier League minutes.\" — Marve Mathingu"
    quote_author = "Marve Mathingu (Triple Captain Post-Mortem)"

    defaulter_roast = (
        "🚨 TREASURY CRACKDOWN (GW 3): Grace period is officially OVER! Fines are now strictly enforced. "
        "Aron Mangati stands tall as the sole paid-up saint banking Ksh. 250.00 while the remaining 9 managers funded the communal treasury. "
        "Clear your balances immediately before the Treasurer sends bailiffs to your WhatsApp DM!"
    )

    transfer_hit_roast = (
        "💥 THE TRANSFER CASUALTY WARD: Gameweek 3 saw heavy hits! "
        "Marve took a brutal -8 point hit (paired with a Cherki 3x Captain disaster), while Renny burned -4 points only to finish dead last. "
        "Wildcard activations by Aron, Marvin, and Samuel spared them point penalties, but couldn't spare their pride."
    )

    classifieds = [
        {
            'title': 'WANTED: Working Triple Captain Button',
            'desc': 'Looking for an apology letter from Pep Guardiola and Rayan Cherki. Will trade for 8 transfer hit points.',
            'contact': 'Call 0700-CHERKI-HELP'
        },
        {
            'title': 'FOR RENT: Bright’s Luxury Bench',
            'desc': 'Accommodates 23 points in extreme comfort every weekend. Free refreshments provided for benched double-digit haulers.',
            'contact': 'Drop off at Phill Me In Subs Dept'
        },
        {
            'title': 'URGENT: Bruno Fernandes Search Party',
            'desc': 'Last seen running aimlessly for 2 points. If found by King Chris or Erick, please return the captain’s armband immediately.',
            'contact': 'M16 Lost & Found Desk'
        },
        {
            'title': 'TREASURY NOTICE: M-Pesa Lines Open',
            'desc': 'Avoid the Wall of Shame. Send your Ksh. 150 + fines before the committee freezes your Gameweek 4 assets.',
            'contact': 'M-Pesa Paybill / Treasurer'
        }
    ]

    edition, created = RoastEdition.objects.update_or_create(
        gameweek=gw,
        defaults={
            'edition_number': 3,
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
        # Rank 1: Dennis
        {
            'name_match': 'Dennis',
            'rank': 1,
            'net_pts': 59,
            'badge': '👑 1ST PLACE (GW CHAMPION)',
            'title': "Dennis Njuguna - 'DenniSkills' Masterclass Conquers GW 3",
            'body': "Pure tactical brilliance without burning chips or transfer hits. Dennis trusted Erling Haaland with the armband for 18 points, while defensive gems Marc Guéhi (8 pts) and Ryan Giles (8 pts) fired him to the top of the table with 59 net points. Now if he only paid his treasury dues on time, his bank account would look as glorious as his rank!",
            'verdict': "Verdict: Supreme Tactician on the Pitch, Defaulter in the Ledger",
        },
        # Rank 2: Aron
        {
            'name_match': 'Aron',
            'rank': 2,
            'net_pts': 57,
            'badge': '💰 2ND PLACE & CASH KING',
            'title': "Aron Mangati - The Wildcard Heist & Sole Cash Winner",
            'body': "Aron pulled the Wildcard trigger in Gameweek 3 and completely revamped his squad for 57 points, riding Haaland's captaincy (18 pts) and clean returns from Donnarumma (7 pts) and Pedro Porro (7 pts). Best of all: as the only financially compliant manager in the money, Aron scoops the entire Ksh. 250.00 first-place prize pool all for himself!",
            'verdict': "Verdict: Financial Mastermind & Wildcard King",
        },
        # Rank 3: Marvin
        {
            'name_match': 'Marvin',
            'rank': 3,
            'net_pts': 56,
            'badge': '🥉 3RD PLACE (DON BOSCO REVIVAL)',
            'title': "Marvin Owino - 'Don Bosco' Wildcard Miracle",
            'body': "The prayers at Don Bosco have been answered! Marvin activated his Wildcard chip and engineered a stunning podium finish with 56 net points. Alisson Becker (8 pts) and Joško Gvardiol (8 pts) stood tall alongside captain Haaland. A massive bounce-back from the trenches that puts the rest of the league on high alert.",
            'verdict': "Verdict: Divine Wildcard Resurrection",
        },
        # Rank 4: Samuel
        {
            'name_match': 'Samuel',
            'rank': 4,
            'net_pts': 47,
            'badge': '🃏 4TH PLACE (WILDCARD RESET)',
            'title': "Samuel Wambua - 'maggry shiners' Steady The Ship",
            'body': "Samuel was the third manager to smash the Wildcard button this week, locking in 47 points. Gvardiol (8 pts) and Tzolakis (6 pts) chipped in alongside the Norwegian cyborg. While he missed out on podium glory by 9 points, his squad restructuring gives him solid momentum heading into GW 4.",
            'verdict': "Verdict: Restructured & Reloaded",
        },
        # Rank 5: King Chris
        {
            'name_match': 'King Chris',
            'rank': 5,
            'net_pts': 46,
            'badge': '🎨 5TH PLACE (CAPTAIN FAIL)',
            'title': "King Chris - The Painter Trapped by Bruno's 4-Point Armband",
            'body': "A tragic case of armband remorse. King Chris had Bryan Mbeumo (8 pts), Kai Havertz (8 pts), and Pedro Porro (7 pts) firing on all cylinders, but gambled on Bruno Fernandes as captain for a pathetic 4-point return (while Haaland bagged 18). A proper captain choice would have easily put him in 1st place. The canvas was colorful, but the frame fell off.",
            'verdict': "Verdict: Masterpiece Ruined by Bruno Armband",
        },
        # Rank 6 (Tied): Bright
        {
            'name_match': 'Bright',
            'rank': 6,
            'net_pts': 42,
            'badge': '🪑 6TH PLACE (BENCH HOARDER)',
            'title': "Bright Ottore - 'Phill Me In' Benches an Astonishing 23 Points!",
            'body': "Bright is officially running the most luxurious bench in East Africa. For the second week running, his substitutes outscored half the league's starters, leaving an eye-watering 23 points stranded on the pine while settling for 42 net points on the field. If bench points counted for trophies, Bright would already be Premier League champion.",
            'verdict': "Verdict: Grandmaster of Bench Regret",
        },
        # Rank 6 (Tied): Marve
        {
            'name_match': 'Marve',
            'rank': 6,
            'net_pts': 42,
            'badge': '🤡 6TH PLACE (TRIPLE CAPTAIN DISASTER)',
            'title': "Marve Mathingu - The Rayan Cherki Triple Captain Catastrophe (-8 Hit)",
            'body': "We have witnessed the most audacious banter play in FPL Boys history! Marve swallowed a -8 point transfer hit and slapped his TRIPLE CAPTAIN chip on... Rayan Cherki. The result? A grand total of 9 points from the chip (3 pts x 3), completely cancelling out his transfer penalty. Tyrick Mitchell (15 pts) and Cody Gakpo (11 pts) wept as their hauls were wasted in mid-table obscurity.",
            'verdict': "Verdict: Banter Hall of Fame Inductee",
        },
        # Rank 8: Erick
        {
            'name_match': 'Erick',
            'rank': 8,
            'net_pts': 41,
            'badge': '🐍 8TH PLACE (BRUNO & BENCH BLUES)',
            'title': "Erick Muchira - 'mambaaa' Bitten by Bruno & 16 Benched Points",
            'body': "Erick suffered a double whammy in GW 3: handing Bruno Fernandes the captaincy for a measly 4 points, while simultaneously stranding 16 valuable points on his bench. Martin Ødegaard (10 pts) and Bryan Mbeumo (8 pts) tried their best, but 'mambaaa' slithered down into rank #8 with 41 net points.",
            'verdict': "Verdict: Defanged Snake in the Relegation Zone",
        },
        # Rank 9: Benn
        {
            'name_match': 'Benn',
            'rank': 9,
            'net_pts': 40,
            'badge': '💀 9TH PLACE (TACTICAL FROSTBITE)',
            'title': "Benn Mwangi - 'Odysseus Reign' Sinks to the Trench",
            'body': "After an explosive Gameweek 2 triumph, Benn came crashing down to earth with a freezing 40 net points in GW 3. Beyond captain Haaland's 18 points, the rest of Odysseus Reign combined for a sorrowful 22 points, while 10 points chilled on the bench. The reign has entered a dark tactical winter.",
            'verdict': "Verdict: From Hero in GW 2 to Zero in GW 3",
        },
        # Rank 10: Renny
        {
            'name_match': 'Renny',
            'rank': 10,
            'net_pts': 37,
            'badge': '🤡 10TH PLACE (WOODEN SPOON CLOWN)',
            'title': "Renny Muragu - 'The Young Ones' Inherit the Wooden Spoon (-4 Hit)",
            'body': "The ultimate disasterclass of Gameweek 3! Renny burned 4 transfer points only to stumble to a league-lowest 37 net points. Despite captaining Haaland (18 pts), the remaining 10 starting players generated a scandalous 23 gross points while 10 points were abandoned on the bench. A well-deserved winner of the GW 3 Wooden Spoon Clown Hat!",
            'verdict': "Verdict: Undisputed Gameweek 3 Clown of the League",
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

    print(f"[SUCCESS] Gazette Issue #{edition.edition_number} for GW {gw.number} published successfully with {len(roasts_data)} personalized manager roasts!")


if __name__ == '__main__':
    publish_gw3()
