from pathlib import Path  # python3 only
import json
import requests
import os
import time
import collections
import random
# # consider moving to a settings.py
from dotenv import load_dotenv
load_dotenv()
# # OR, explicitly providing path to '.env'
# env_path = Path('.') / '.env'
# load_dotenv(dotenv_path=env_path)


class Explorer:
    def __init__(self):
        # load most recent map from map.json
        # NOTE: should at minimum be text file containing: "{}"
        map_graph_existing = {}
        working_dir = os.path.dirname(os.path.abspath(__file__))
        try:
            with open(working_dir + '/map.json', 'r+') as f:
                map_graph_existing = json.loads(f.read().strip().rstrip())
            print("--------------loaded saved map----------------")
        except OSError:
            print("Cannot open map.json..does it exist?")
        self.map_graph = {**map_graph_existing}

        # load treasure_tracker from treasure_tracker.json
        # NOTE: should at minimum be text file containing: "{}"
        treasure_tracker_existing = {}
        working_dir = os.path.dirname(os.path.abspath(__file__))
        try:
            with open(working_dir + '/treasure_tracker.json', 'r+') as f:
                treasure_tracker_existing = json.loads(
                    f.read().strip().rstrip())
            print("--------loaded saved treasure_tracker---------")
        except OSError:
            print("Cannot open treasure_tracker.json..does it exist?")
        self.treasure_tracker = {**treasure_tracker_existing}

        self.opp_dir = {'n': 's', 'e': 'w', 's': 'n', 'w': 'e'}
        self.encumbered = False

        # set up connection to server
        self.server_url = 'https://lambda-treasure-hunt.herokuapp.com/api/adv'
        self.api_key = os.environ.get('API_KEY')
        self.auth_header = {
            'Authorization': f"Token {self.api_key}"
        }

        # make first request to server to determine current room
        r_data = self.make_request('init')
        self.current_room = str(r_data['room_id'])
        self.current_room_title = r_data['title']
        self.exits = r_data['exits']
        # TODO: remove once self.request is complete
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
        print(r_data)

    def make_request(self, req_type, data=None):
        '''
        make a request to the server and wait for cooldown.
        accepts a dict of data
        return dict of returned json
        '''
        if data:
            data_json = json.dumps(data)
        if req_type == 'init':
            r = requests.get(self.server_url + '/init/',
                             headers=self.auth_header)
        elif req_type == 'move':
            r = requests.post(self.server_url + '/move/',
                              headers=self.auth_header, data=data_json)
        elif req_type == 'take':
            r = requests.post(self.server_url + '/take/',
                              headers=self.auth_header, data=data_json)
        elif req_type == 'drop':
            r = requests.post(self.server_url + '/drop/',
                              headers=self.auth_header, data=data_json)
        elif req_type == 'status':
            r = requests.post(self.server_url + '/status/',
                              headers=self.auth_header)
        elif req_type == 'sell':
            r = requests.post(self.server_url + '/sell/',
                              headers=self.auth_header, data=data_json)
        elif req_type == 'dash':
            r = requests.post(self.server_url + '/dash/',
                              headers=self.auth_header, data=data_json)
        elif req_type == 'fly':
            r = requests.post(self.server_url + '/fly/',
                              headers=self.auth_header, data=data_json)
        else:
            print('unknown req_type')
        r_data = r.json()
        # wait for "cool_down" before anything else
        cooldown = r_data['cooldown']
        print(f"cool down = {cooldown}", end="..", flush=True)
        while cooldown > 0:
            if(cooldown > 1):
                time.sleep(1)
                cooldown -= 1
            else:
                time.sleep(cooldown)
                cooldown = 0
            print(cooldown, end="..", flush=True)
        # formatting..
        print(" ")
        return r_data

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
        # TODO: theres something messing up the map_graph, check where orient is called in travel??
        if len(self.map_graph.keys()) < 500:
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

    def update_stored_treasure_tracker(self):
        ''' 
        dump treasure_tracker data to file 
        '''
        with open('treasure_tracker.json', 'w+') as f:
            json.dump(self.treasure_tracker, f, sort_keys=True, indent=4)

    def get_route_to(self, target):
        '''
        BFS for nearest 'target' and add to travel_queue
        '''
        q = collections.deque([])
        visited = set()
        visited.add(self.current_room)
        for ex_dir in self.exits:
            q.append([ex_dir])
        print(f"current room: {self.current_room} exits: {self.exits}")
        print(f"get_route_to ->{target}<-")
        while len(q) > 0:
            # print(f"queue: {q}")
            path = q.popleft()
            # path is only directions, need to re-find next_room
            next_room = self.current_room
            for direction in path:
                next_room = self.map_graph[next_room]['exits'][direction]
            check_dir = path[-1]
            # time.sleep(0.5)
            if next_room == target:
                # found target
                travel_queue = collections.deque(path)
                break
            else:
                if next_room != '?' and next_room not in visited:
                    visited.add(next_room)
                    for ex in self.map_graph[next_room]['exits']:
                        exit_room = self.map_graph[next_room]['exits'][ex]
                        # having visited should make this unnecessary?
                        if exit_room != self.current_room:
                            new_path = path[:]
                            new_path.append(ex)
                            q.append(new_path)

        print(f"check_dir: {check_dir}, next_room: {next_room}")
        print(
            f"len(visited): {len(visited)} len(graph): {len(self.map_graph)} visited: {sorted(visited)}")
        print(f"new route: {travel_queue}")
        return travel_queue

    def travel(self, travel_queue, fast=False):
        '''
        expects a travel_queue of type: "collections.deque"
        travels according to the directions in travel_queue
        subject to some constraints:
        1) if we're over encumbered, clear travel queue and
        set self.encumbered to true. this triggers re-routing to the shop to sell items
        '''
        # expects a travel_queue which is a "deque"
        while len(travel_queue) > 0:
            direction = travel_queue.popleft()
            print(f"nxt route: {travel_queue}")
            next_room = self.map_graph[self.current_room]['exits'][direction]
            data = {'direction': direction}
            # if we know id of next room, add to request data to get "Wise Explorer" reduction of cooldown
            if next_room != '?':
                data['next_room_id'] = next_room
            # if we're fast traveling:
            if fast:
                # as long as we're going in a straight line we can dash
                # NOTE: only after changing name and praying at 461
                if len(travel_queue) > 0 and direction == travel_queue[0]:
                    print("can dash!")
                    next_room_ids = [next_room]
                    while len(travel_queue) > 0 and direction == travel_queue[0]:
                        direction = travel_queue.popleft()
                        next_room = self.map_graph[next_room]['exits'][direction]
                        next_room_ids.append(next_room)
                    # handle case we're traveling to a '?'
                    if next_room_ids[len(next_room_ids) - 1] == '?':
                        next_room_ids.pop()
                    room_count = len(next_room_ids)
                    #'{"direction":"n", "num_rooms":"5", "next_room_ids":"10,19,20,63,72"}'
                    data['num_rooms'] = str(room_count)
                    data['next_room_ids'] = ",".join(next_room_ids)
                    # also remove 'next_room_id'
                    del data['next_room_id']
                    r_data = self.make_request('dash', data)
                    print(f"dash response: {r_data}")
                    # data_json = json.dumps(data)
                    # print(f"dash: {data_json}")
                    # r = requests.post(self.server_url + '/dash/',
                    #                   headers=self.auth_header, data=data_json)
                else:
                    # can't dash
                    r_data = self.make_request('move', data)
                self.orient(r_data, direction)
            # not fast traveling
            else:
                # if the next room has elevated terrain, fly!
                # NOTE: only after changing name and praying at 22
                terrain = self.map_graph[next_room]['terrain']
                if terrain == 'MOUNTAIN':
                    print("FLYING")
                    r_data = self.make_request('fly', data)
                else:
                    r_data = self.make_request('move', data)
                # # code to pick up all treasure in the room
                while len(r_data['items']) > 0 and not self.encumbered:
                    treasure = r_data['items'][0]
                    print("$" * 20)
                    print(f"treasure found: {r_data}")
                    r_data = self.make_request('take', {'name': 'treasure'})
                    # update treasure_tracker
                    if treasure not in self.treasure_tracker:
                        self.treasure_tracker[treasure] = 0
                    self.treasure_tracker[treasure] += 1
                    self.update_stored_treasure_tracker()
            self.orient(r_data, direction)
            print("-" * 20)
            print(f"travel response: {r_data}")
            # clear travel_queue and set self.encumbered if we are over encumbered an not aware
            if not self.encumbered and "Heavily Encumbered: +100% CD" in r_data['messages']:
                self.encumbered = True
                travel_queue = []

    def explore(self):
        '''
        run until interrupted
        1) check self.map_graph, if there are '?', travel there, else travel to a random room
        2) if encumbered, travel to the shop and sell items
        '''
        while True:
            if not self.encumbered:
                # keep exploring until over encumbered by treasure
                # search for a room...
                # travel_queue = self.get_route_to('77')
                # ... or travel a random direction
                # travel_queue = collections.deque([random.choice(self.exits)])
                # ... or travel to a random room
                travel_queue = self.get_route_to(
                    str(random.choice(range(1, 500))))
                self.travel(travel_queue)
            else:
                # travel to shop and sell treasure
                print("Too much treasure, travel to shop")
                # dump one treasure first
                r_data = self.make_request('drop', {"name": "treasure"})
                travel_queue = self.get_route_to('1')
                self.travel(travel_queue, True)
                print("Arrived at shop, sell treasures!")
                # figure out how many treasures we have
                r_data = self.make_request('status')
                treasure_count = len(r_data['inventory'])
                for count in range(treasure_count):
                    r_data = self.make_request(
                        'sell', {"name": "treasure", "confirm": "yes"})
                    print("$" * 20)
                    print(f"sale response: {r_data}")
                self.encumbered = False


explorer = Explorer()
explorer.explore()
