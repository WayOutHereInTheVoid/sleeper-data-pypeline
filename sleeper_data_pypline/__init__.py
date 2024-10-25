import argparse
import json
from sleeper_wrapper import League
from dotenv import load_dotenv
from etl import write_draft_and_picks, fetch_and_write_transactions, fetch_and_push_matchups, write_season, write_players 
from mongo import connect
from transforms import get_10g1c_leagueid_by_year, get_display_name_from_roster_id
from fetchers import get_leg, get_upper_and_lower_leg
from queries import get_scoring_array_and_calculate_week_of_1k_points, get_highest_bids_of_all_time
from utils import write_to_file

load_dotenv()

def lambda_handler(event, context):
    # Extract arguments from the event (assume they're passed as a dictionary)
    command = event.get('command', '')
    season = event.get('season', '')

    # Call the main function with these arguments
    # init()

    # Return a response
    return {
        'statusCode': 200,
        'body': 'Function executed successfully'
    }

def parseArgs():
    parser = argparse.ArgumentParser(description="Sleeper pipeline ETL scripts and data utilities")

    subparsers = parser.add_subparsers(dest="command", help="Sub-command help")

    parser_identify = subparsers.add_parser("identify", help="Identify a league member")
    parser_identify.add_argument("number", type=int, choices=range(1, 11), help="An integer between 1 and 10")
    parser_identify.add_argument("season", type=str, help="The season (ex: 2022)")

    etl_choices = ['draft', 'league', 'transactions', 'matchups', 'players', 'playoffs']

    parser_etl = subparsers.add_parser("etl", help="Grab data for a season, upsert it into mongo")
    parser_etl.add_argument("action", type=str, choices=etl_choices, help="Grab and load draft data")
    parser_etl.add_argument("season", type=str, help="The season (ex: 2022)")
    parser_etl.add_argument("--h", type=int, help="High leg (when action will span multiple legs)")
    parser_etl.add_argument("--l", type=int, help="Low leg (when action will span multiple legs)")

    query_choices = ['time_to_1k', 'highest_faab_bids']
    parser_query = subparsers.add_parser("query", help="make a query, answer a question")
    parser_query.add_argument("action", type=str, choices=query_choices, help="which query do you want to execute?")
    parser_query.add_argument("season", type=str, help="The season (ex: 2022)")

    args = parser.parse_args()
    return args


# TODO - can I create an effective 'scores' csv export that lets me crunch data faster?
# TODO - given a season and a roster id, figure out the display_name
  # Can/should I just add a mapping of roster_id::display_name::owner_id/etc to the 'league' collection?
# TODO - Calculate high scores of the week
# TODO - How many (and which) players were both drafted and started by the championship team in the championship week?
def init(args):
    valid_actions = [
        "identify",
        "etl",
        "query"
    ]

    season = args.season

    print(f"Action: {args.command}")
    if args.command not in valid_actions:
        print('Action is not valid')
        raise
    
    if args.command == "identify":
        league_id = get_10g1c_leagueid_by_year(season)
        LeagueDataFetcher = League(league_id)
        rosters = LeagueDataFetcher.get_rosters()
        users = LeagueDataFetcher.get_users()
        print(get_display_name_from_roster_id(rosters, users, args.number))
    elif args.command == "etl":
        MongoClient = connect()
        league_id = get_10g1c_leagueid_by_year(season)
        LeagueDataFetcher = League(league_id)
        if args.action == "league":
            write_season(LeagueDataFetcher, MongoClient)
        elif args.action == "transactions":
            # This is inefficient to fetch the league here and then do it again later when we
            # pass LeagueDataFetcher
            # Is there a way to pass league_data if it's already been fetched
            # or LeagueDataFetcher if not?
            legs = get_upper_and_lower_leg(LeagueDataFetcher.get_league())
            highLeg = args.h or legs[1]
            lowLeg = args.l or legs[0]
            fetch_and_write_transactions(LeagueDataFetcher, MongoClient, highLeg, lowLeg)
        elif args.action == "draft":
            write_draft_and_picks(LeagueDataFetcher, MongoClient, league_id)
        elif args.action == "matchups":
            fetch_and_push_matchups(LeagueDataFetcher, MongoClient)
        elif args.action == "players":
            write_players(MongoClient)
        elif args.action == "playoffs":
            # losers = LeagueDataFetcher.get_playoff_losers_bracket()
            winners_result = winners = LeagueDataFetcher.get_playoff_winners_bracket()
            for w_result in winners_result:
                metadata = {
                    "season": season,
                    "league_id": league_id,
                }
                w_result |= metadata
                print(json.dumps(w_result, indent=4))
            # The only way for us to know if a roster_id was in playoffs:
            # 1. Get the winners bracket
            # 2. Loop over each row where r = 1
            # 3. Assign to a dict row.t1+t2 or row.w+l
               # This dict contains the roster_id of all teams in
            # 4. When loading rosters (still TODO), assign made_playoffs = true/false based on this dict
            # write_to_file(winners, 'winners_bracker_2023.json')
            # write_playoffs(MongoClient)  
        else:
            print('ETL action: {} is not a valid action'.format(args.action))
            raise
    elif args.command == "query":
        if args.action == "time_to_1k":
           league_id = get_10g1c_leagueid_by_year(season)
           LeagueDataFetcher = League(league_id)
           MongoClient = connect()
           result = get_scoring_array_and_calculate_week_of_1k_points(LeagueDataFetcher, MongoClient, args.season)
           print(json.dumps(result, indent=4))
        elif args.action == 'highest_faab_bids':
            result = get_highest_bids_of_all_time(10)
            print(json.dumps(result, indent=4))
        else:
            print('Query action: {} is not a valid action'.format(args.action))
            raise

if __name__ == "__main__":
    args = parseArgs()
    init(args)
