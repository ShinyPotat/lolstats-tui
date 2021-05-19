#!/usr/bin/env python3
import os
import requests
import xlsxwriter
from datetime import datetime
from riotwatcher import LolWatcher, ApiError
from tabulate import tabulate

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


api_key = os.environ['RIOT_API_KEY']
lol_watcher = LolWatcher(api_key)
my_region = 'euw1'

name = input('Summoner name: ')

try:
    latest = lol_watcher.data_dragon.versions_for_region(my_region)['n']['champion']
    static_champ_list = lol_watcher.data_dragon.champions(latest, False, 'en_US')
    champ_dict = {}
    for key in static_champ_list['data']:
        row = static_champ_list['data'][key]
        champ_dict[row['key']] = row['id']

    url = "http://static.developer.riotgames.com/docs/lol/queues.json"
    queues = requests.get(url).json()

    summ = lol_watcher.summoner.by_name(my_region, name)
    ranked_stats = lol_watcher.league.by_summoner(my_region, summ['id'])
    print(bcolors.BOLD + "---- {} ----".format(name) + bcolors.ENDC)
    for ranked in ranked_stats:
        if ranked['queueType'] == "RANKED_FLEX_SR":
            print("Solo/Duo: {} {}".format(ranked['tier'], ranked['rank']))
        elif ranked['queueType'] == "RANKED_SOLO_5x5":
            print("Flex: {} {}".format(ranked['tier'], ranked['rank']))
    print()
    matches = lol_watcher.match.matchlist_by_account(my_region, summ['accountId'], end_index=10)
    wins = 0
    table = [['Result', 'Game Mode' , 'Role', 'Champion', 'Duration', 'KDA', 'CS', 'Gold Earned', 'Total Damage', 'Date']]
    for match in matches['matches']:
        match_detail = lol_watcher.match.by_id(my_region, match['gameId'])
        participant_id = 0

        for identity in match_detail['participantIdentities']:
            if identity['player']['accountId'] == summ['accountId']:
                participant_id = identity['participantId']
                break

        game_mode = ""
        for queue in queues:
            if queue['queueId'] == match_detail['queueId']:
                game_mode = queue['description']
                break

        participant = match_detail['participants'][participant_id-1]
        participant_stats = participant['stats']

        total_kills = 0
        for player in match_detail['participants']:
            if player['teamId'] == participant['teamId']:
                total_kills += player['stats']['kills']

        if participant_stats['win']:
            end = bcolors.OKGREEN + "win" + bcolors.ENDC
            wins += 1
        else:
            end = bcolors.FAIL + "defeat" + bcolors.ENDC
        role = ""

        if 'CARRY' in match['role']:
            role = 'ADC'
        elif 'SUPPORT' in match['role']:
            role = 'SUPPORT'
        else:
            role = match['lane']

        if 'Flex' in game_mode:
            game_mode = "Flex"
        elif 'Solo' in game_mode:
            game_mode = 'Solo/Duo'
        elif 'ARAM' in game_mode:
            game_mode = 'ARAM'
            role = ""
        elif 'URF' in game_mode:
            game_mode = "URF"
            role = ""
        elif "Draft" in game_mode:
            game_mode = "Draft"

        champion = champ_dict[str(participant['championId'])]
        time = match_detail['gameDuration']
        minutes, seconds = divmod(time, 60)
        kills = participant_stats['kills']
        deaths = participant_stats['deaths']
        assists = participant_stats['assists']
        minions = participant_stats['totalMinionsKilled'] + participant_stats['neutralMinionsKilled']
        gold = participant_stats['goldEarned']
        damage = participant_stats['totalDamageDealtToChampions']
        date = datetime.fromtimestamp(match['timestamp']/1000).strftime("%d/%m/%Y")

        l = [end, game_mode, role, champion, "{:02}:{:02}".format(int(minutes), int(seconds)), "{}/{}/{} ({}%)".format(kills, deaths, assists, int((kills+assists)/total_kills*100)), "{} ({:.1f})".format(minions, minions/minutes), gold, damage,date]
        table.append(l)

    print(tabulate(table, headers='firstrow', tablefmt='fancy_grid'))
    print("\nWR: {}% {}W {}L".format(int(wins/10*100), wins, 10-wins))

    with xlsxwriter.Workbook('test.xlsx') as workbook:
        worksheet = workbook.add_worksheet()

        for row_num, data in enumerate(table):
            if 'defeat' in data[0]:
                data[0] = 'defeat'
            elif 'win' in data[0]:
                data[0] = 'win'
            worksheet.write_row(row_num, 0, data)

except ApiError as err:
    if err.response.status_code == 429:
        print('We should retry in {} seconds.'.format(err.response))
        print('this retry-after is handled by default by the RiotWatcher library')
        print('future requests wait until the retry-after time passes')
    elif err.response.status_code == 404:
        print('Summoner with that ridiculous name not found.')
    else:
        raise
