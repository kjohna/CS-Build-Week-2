import json
import requests
import os
import time
import collections
# consider moving to a settings.py
from dotenv import load_dotenv
load_dotenv()


class Explorer:
    def __init__(self):
        # load most recent map from map.json
        # note should at minimum be text file containing: "{}"
        map_graph_existing = {}
        try:
            with open('map.json', 'r+') as f:
                map_graph_existing = json.loads(f.read().strip().rstrip())
        except OSError:
            print("Cannot open map.json..does it exist?")
        self.map_graph = {**map_graph_existing}
        self.opp_dir = {'n': 's', 'e': 'w', 's': 'n', 'w': 'e'}
        # set up connection to server
        self.server_url = 'https://lambda-treasure-hunt.herokuapp.com/api/adv'
        self.api_key = os.environ.get('API_KEY')
        self.auth_header = {
            'Authorization': f"Token {self.api_key}"
        }
        # make first request to server to determine current room
        r = requests.get(self.server_url + '/init/', headers=self.auth_header)
        r_data = r.json()
        self.current_room = str(r_data['room_id'])
        self.current_room_title = r_data['title']
        self.exits = r_data['exits']
        self.cool_down = r_data['cooldown']
        # initialize if this is the first time running
        if len(self.map_graph.keys()) == 0:
            found_exits = {}
            for exit_dir in self.exits:
                found_exits[exit_dir] = '?'
            self.map_graph[self.current_room] = {'title': '', 'exits': ''}
            self.map_graph[self.current_room]['title'] = self.current_room_title
            self.map_graph[self.current_room]['exits'] = found_exits
            self.update_stored_map
        # wait for "cool_down" before anything else
        time.sleep(self.cool_down)
        print(r_data)

    def orient(self, r_data, dir_traveled):
        '''
        Receives response data from a movement plus direction traveled.
        Updates map graph with current/previous room directions
        and self with current room info 
        '''
        prev_room = self.current_room
        prev_room_title = self.current_room_title
        rev_dir = self.opp_dir[dir_traveled]
        self.current_room = str(r_data['room_id'])
        self.current_room_title = r_data['title']
        self.exits = r_data['exits']
        self.cool_down = r_data['cooldown']
        if self.current_room not in self.map_graph:
            found_exits = {}
            for exit_dir in self.exits:
                found_exits[exit_dir] = '?'
            self.map_graph[self.current_room] = {
                'title': self.current_room_title, 'exits': found_exits
            }
        self.map_graph[prev_room]['exits'][dir_traveled] = self.current_room
        self.map_graph[self.current_room]['exits'][rev_dir] = prev_room
        self.map_graph[self.current_room]['elevation'] = r_data['elevation']
        self.map_graph[self.current_room]['terrain'] = r_data['terrain']
        self.map_graph[self.current_room]['coordinates'] = r_data['coordinates']
        self.update_stored_map()

    def update_stored_map(self):
        ''' 
        dump map graph data to file 
        '''
        with open('map.json', 'w+') as f:
            json.dump(self.map_graph, f, sort_keys=True, indent=4)
        # print(self.map_graph)

    def get_route_to(self, target):
        '''
        BFS for nearest '?' and add to travel_queue
        '''
        q = collections.deque([])
        for ex_dir in self.exits:
            q.append([ex_dir])
        while len(q) > 0:
            print(f"get_route_to ->{target}<-..current path: {q}")
            path = q.popleft()
            next_room = self.current_room
            for direction in path:
                next_room = self.map_graph[next_room]['exits'][direction]
            check_dir = path[-1]
            # next_room = self.map_graph[check_room]['exits'][check_dir]
            print(f"check_dir: {check_dir}, next_room: {next_room}")
            if next_room == target:
                # found target
                travel_queue = collections.deque(path)
                break
            else:
                for ex in self.map_graph[next_room]['exits']:
                    if not ex == self.opp_dir[ex_dir]:
                        new_path = path[:]
                        new_path.append(ex)
                        q.append(new_path)
        print(f"new route: {travel_queue}")
        return travel_queue

    def travel(self, travel_queue):
        # expects a travel_queue which is a "deque"
        while len(travel_queue) > 0:
            direction = travel_queue.popleft()
            data = {'direction': direction}
            # if we know the id of the next room, add to the data for the request to get "Wise Explorer" reduction of cooldown
            next_room = self.map_graph[self.current_room]['exits'][direction]
            if not next_room == '?':
                data['next_room_id'] = next_room
            data_json = json.dumps(data)
            r = requests.post(self.server_url + '/move/',
                              headers=self.auth_header, data=data_json)
            r_data = r.json()
            self.orient(r_data, direction)
            print("-" * 20)
            print(f"travel request: {r_data}")
            time.sleep(self.cool_down)
            if len(r_data['items']) > 0:
                data = json.dumps({'name': 'treasure'})
                r = requests.post(self.server_url + '/take/',
                                  headers=self.auth_header, data=data)
                r_data = r.json()
                print("$" * 20)
                print(f"treasure found: {r_data}")
                time.sleep(r_data['cooldown'])

    def explore(self):
        while True:
            travel_queue = self.get_route_to('?')
            self.travel(travel_queue)


explorer = Explorer()
explorer.explore()
# while True:
#     time.sleep(cool_down)
# travel to next direction in travel_queue
# if the travel_queue is empty, devise more moves based on current strategy:
# if 'exploring' strategy travel to nearest '?' via shortest path
# if there is a '?' in current_room's exits travel there
# else if we are at a 'dead end' (no unexplored exits) BFS for nearest '?'
# else if the map is already explored do 'playing' strategy

# after moving to new room, if there is treasure take it
