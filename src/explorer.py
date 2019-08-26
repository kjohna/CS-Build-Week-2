import json
import requests
import os
# consider moving to a settings.py
from dotenv import load_dotenv
load_dotenv()

# load most recent map from map.txt
# note should at minimum be text file containing: "{}"
map_graph_existing = {}
try:
    with open('map.txt', 'r+') as f:
        map_graph_existing = json.loads(f.readline())
except OSError:
    print("Cannot open map.txt..does it exist?")

map_graph = {**map_graph_existing}
# print(map_graph)

server_url = 'https://lambda-treasure-hunt.herokuapp.com/api/adv'

# initialize if this is the first time running
if len(map_graph.keys()) == 0:
    api_key = os.environ.get('API_KEY')
    # print(api_key)
    headers = {
        'Authorization': f"Token {api_key}"
    }
    r = requests.get(server_url + '/init/', headers=headers)
    r_data = r.json()
    # print(r_data)
    exits = {}
    for exit_dir in r_data['exits']:
        exits[exit_dir] = '?'
    map_graph[str(r_data['room_id'])] = exits
    with open('map.txt', 'w+') as f:
        json.dump(map_graph, f)

print(map_graph)
