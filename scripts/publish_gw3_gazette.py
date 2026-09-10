import os
import sys
import django
from django.utils import timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fpl_boys.settings')
django.setup()

from league.models import Gameweek, Member
from news.models import RoastEdition, ManagerRoastItem
from news.services.roast_engine import ensure_news_tables_exist
from news.services.gazette_storage import export_edition_to_disk


def publish_gw3():
    ensure_news_tables_exist()
    gw = Gameweek.objects.get(number=3)

    headline = "GW 3 MASSACRE: DENNI-SKILLS REIGNS AT THE SUMMIT, ARON & MARVIN BAG PODIUM CASH, MARVE'S 3X CHERKI DISASTER, AND KING CHRIS GETS FINED!"
    subheadline = "Issue #3 Broadsheet: Dennis takes the crown, Wildcards pay cash dividends, Cherki Triple Captain comedy, and King Chris anchors the Treasury Wall of Shame."
    
    chief_editor = "The League Scribe & Chief Banter Officer"
    weather_report = "Sunny skies and incoming cash for the podium; heavy financial frost and captaincy storms over King Chris."

    editorial_lead = (
        "Gameweek 3 delivered sensational footballing drama and hilarious tactical calamities across the 10-man battleground. "
        "Leading from the front with supreme poise, Dennis Njuguna ('DenniSkills') conquered the gameweek with 59 net points—relying on captain Erling Haaland and defensive gems Marc Guéhi and Ryan Giles to claim 1st place and bank Ksh. 250.00 in prize money! "
        "Close behind on the podium, aggressive early Wildcards paid off handsomely: Aron Mangati captured 2nd place (57 pts) for Ksh. 166.67, while Marvin Owino orchestrated a stunning Don Bosco revival to take 3rd place (56 pts) and pocket Ksh. 83.33. "
        "On the comedic front, Marve Mathingu delivered the ultimate banter masterclass by burning an 8-point transfer hit only to Triple Captain Rayan Cherki for a tragic 9 points total. "
        "Meanwhile, King Chris endured an unforgettable horror show: captaining Bruno Fernandes for 4 points while standing as the SOLE unpaid defaulter in the entire league! "
        "At the very bottom, Renny Muragu's 'The Young Ones' crashed to 37 net points with a transfer hit to proudly capture the GW 3 Wooden Spoon Clown Crown!"
    )

    dennis = Member.objects.filter(manager_name__icontains="Dennis").first()
    renny = Member.objects.filter(manager_name__icontains="Renny").first()

    king = dennis
    king_reason = (
        "Dennis 'DenniSkills' Njuguna delivered pure tactical perfection with 59 net points (zero hits, zero chips) to claim the GW 3 crown and Ksh. 250.00 cash prize!"
    )

    clown = renny
    clown_reason = (
        "Renny 'The Young Ones' Muragu burned a -4 transfer hit only to collapse to a league-lowest 37 net points with 10 points left on the bench. The Wooden Spoon finds a worthy home!"
    )

    quote_of_the_week = "\"Cherki had the underlying metrics in training. The algorithms just didn't translate to Premier League minutes.\" — Marve Mathingu"
    quote_author = "Marve Mathingu (Triple Captain Post-Mortem)"

    defaulter_roast = (
        "🚨 TREASURY WALL OF SHAME (GW 3): 9 out of 10 managers paid on time and kept the league running smoothly. "
        "Then there's King Chris, our solitary BBQ Pot sponsor! Not only did he captain Bruno Fernandes for 2 points, "
        "but he also forgot to settle his dues, earning an official committee late fine. Sincere thanks to Chris for voluntarily funding the meat fund!"
    )

    transfer_hit_roast = (
        "💥 THE TRANSFER CASUALTY WARD: Marve Mathingu took a self-inflicted -8 point penalty (paired with the now-legendary Cherki 3x Captain catastrophe), "
        "while Renny burned -4 points straight into 10th place. Wildcards from Aron, Marvin, and Samuel spared them point hits and launched two of them straight onto the cash podium!"
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
            'title': 'TREASURY APPRECIATION: King Chris BBQ Pot Fund',
            'desc': 'Special shoutout to King Chris for single-handedly funding the league barbecue through his GW 3 fine.',
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
            'title': "Dennis Njuguna - 'DenniSkills' Tactical Masterclass & Cash King",
            'body': "Pure class without burning a single chip or transfer hit. Dennis trusted Erling Haaland with the armband (18 pts), while Marc Guéhi (8 pts) and Ryan Giles (8 pts) formed an impenetrable defensive foundation to deliver 59 net points and bank Ksh. 250.00. A deserved champion at the 10-man summit!",
            'verdict': "Verdict: Undisputed GW 3 Champion & Cash King (Ksh. 250.00)",
        },
        # Rank 2: Aron
        {
            'name_match': 'Aron',
            'rank': 2,
            'net_pts': 57,
            'badge': '🥈 2ND PLACE (WILDCARD SILVER)',
            'title': "Aron Mangati - 'Arons' Wildcard Masterstroke Bags Silver Cash",
            'body': "Aron pulled the Wildcard trigger with ruthless precision. Overhauling his squad yielded 57 points, powered by captain Haaland (18 pts), Donnarumma (7 pts), and Pedro Porro (7 pts). Sits proudly in 2nd place and banks Ksh. 166.67 in hard-earned podium cash!",
            'verdict': "Verdict: Wildcard Mastermind & Silver Winner (Ksh. 166.67)",
        },
        # Rank 3: Marvin
        {
            'name_match': 'Marvin',
            'rank': 3,
            'net_pts': 56,
            'badge': '🥉 3RD PLACE (DON BOSCO RESURRECTION)',
            'title': "Marvin Owino - 'Don Bosco' Wildcard Miracle Bags Bronze Prize",
            'body': "The prayers at Don Bosco church worked wonders! Marvin activated his Wildcard and engineered an incredible resurgence, finishing with 56 net points to secure 3rd place and Ksh. 83.33. Alisson Becker (8 pts) and Joško Gvardiol (8 pts) provided the divine inspiration behind captain Haaland.",
            'verdict': "Verdict: Divine Podium Revival & Bronze Winner (Ksh. 83.33)",
        },
        # Rank 4: Samuel
        {
            'name_match': 'Samuel',
            'rank': 4,
            'net_pts': 47,
            'badge': '🃏 4TH PLACE (WILDCARD RESET)',
            'title': "Samuel Wambua - 'maggry shiners' Restructured for the Long Haul",
            'body': "Samuel was the third tactician to hit the Wildcard button in GW 3, racking up 47 points. Gvardiol (8 pts) and Tzolakis (6 pts) performed well alongside Haaland, putting solid foundations in place for the upcoming fixtures.",
            'verdict': "Verdict: Solid Squad Overhaul",
        },
        # Rank 5: King Chris
        {
            'name_match': 'King Chris',
            'rank': 5,
            'net_pts': 46,
            'badge': '💸 5TH PLACE (SOLE DEFAULTER & BRUNO FAIL)',
            'title': "King Chris - The Painter's Double Disaster: Bruno Armband & Late Fine!",
            'body': "A weekend King Chris will want to scrub from his memory. He stubbornly captained Bruno Fernandes for a miserable 4 points (leaving Haaland's 18 points unboosted), and topped it off by being the ONLY manager in the entire league to default on his dues! He officially earns the Sole Defaulter Badge and funds the BBQ pot.",
            'verdict': "Verdict: Sponsored the BBQ Pot & Lost the Armband Gamble",
        },
        # Rank 6 (Tied): Bright
        {
            'name_match': 'Bright',
            'rank': 6,
            'net_pts': 42,
            'badge': '🪑 6TH PLACE (23 BENCHED POINTS)',
            'title': "Bright Ottore - 'Phill Me In' Benches an Eye-Watering 23 Points!",
            'body': "Bright is running a 5-star luxury hotel on his substitutes' bench. For the second consecutive gameweek, his bench outscored most starting midfields, stranding 23 massive points on the pine while scoring 42 on the pitch. Bench management training is urgently required.",
            'verdict': "Verdict: Grandmaster of Bench Regret",
        },
        # Rank 6 (Tied): Marve
        {
            'name_match': 'Marve',
            'rank': 6,
            'net_pts': 42,
            'badge': '🤡 6TH PLACE (CHERKI TRIPLE CAPTAIN COMEDY)',
            'title': "Marve Mathingu - The Rayan Cherki Triple Captain Banter Classic (-8 Hit)",
            'body': "An entry into the FPL Boys Hall of Comedy! Marve absorbed an 8-point transfer penalty to unleash his prestigious TRIPLE CAPTAIN chip on... Rayan Cherki. The haul? A staggering 9 points total (3 pts x 3), neatly negating his transfer deduction. Mitchell (15 pts) and Gakpo (11 pts) deserved a medal for carrying this tactical comedy.",
            'verdict': "Verdict: Hall of Fame Banter Play",
        },
        # Rank 8: Erick
        {
            'name_match': 'Erick',
            'rank': 8,
            'net_pts': 41,
            'badge': '🐍 8TH PLACE (BRUNO WOES & 16 BENCH PTS)',
            'title': "Erick Muchira - 'mambaaa' Trapped by Bruno & Benched Hauls",
            'body': "Erick suffered tactical paralysis in GW 3: handing Bruno Fernandes the captain's armband for a flat 4 points, while abandoning 16 valuable points on his substitutes' bench. Martin Ødegaard (10 pts) and Bryan Mbeumo (8 pts) were left fighting a lonely battle.",
            'verdict': "Verdict: Defanged in the Relegation Trench",
        },
        # Rank 9: Benn
        {
            'name_match': 'Benn',
            'rank': 9,
            'net_pts': 40,
            'badge': '💀 9TH PLACE (GW 2 CHAMPION\'S HANGOVER)',
            'title': "Benn Mwangi - 'Odysseus Reign' Plunges from Hero to Zero",
            'body': "After a majestic Gameweek 2 triumph (118 pts), Benn experienced an icy tactical hangover with just 40 net points. Apart from captain Haaland (18 pts), the remaining 10 starters mustered only 22 points while 10 points chilled on the bench.",
            'verdict': "Verdict: Post-Championship Hangover",
        },
        # Rank 10: Renny
        {
            'name_match': 'Renny',
            'rank': 10,
            'net_pts': 37,
            'badge': '🤡 10TH PLACE (WOODEN SPOON CLOWN)',
            'title': "Renny Muragu - 'The Young Ones' Take the Wooden Spoon (-4 Hit)",
            'body': "The undisputed calamity of Gameweek 3. Renny took an aggressive -4 transfer hit only to sink to the very bottom with a league-lowest 37 net points. Despite captaining Haaland, his supporting cast failed to turn up while 10 points watched from the sidelines. The GW 3 Clown Hat fits perfectly!",
            'verdict': "Verdict: Undisputed GW 3 Wooden Spoon Clown",
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
    print(f"[SUCCESS] Gazette Issue #{edition.edition_number} for GW {gw.number} published and exported to news/editions/gw3.json successfully!")


if __name__ == '__main__':
    publish_gw3()
