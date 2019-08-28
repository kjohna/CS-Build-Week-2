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
        self.encumbered = False
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
        BFS for nearest 'target' and add to travel_queue
        '''
        q = collections.deque([])
        for ex_dir in self.exits:
            q.append([ex_dir])
        while len(q) > 0:
            print(f"get_route_to ->{target}<-")
            # print(f"queue: {q}")
            path = q.popleft()
            next_room = self.current_room
            for direction in path:
                next_room = self.map_graph[next_room]['exits'][direction]
            check_dir = path[-1]
            # next_room = self.map_graph[check_room]['exits'][check_dir]
            # print(f"check_dir: {check_dir}, next_room: {next_room}")
            # time.sleep(0.5)
            if next_room == target:
                # found target
                travel_queue = collections.deque(path)
                break
            else:
                if next_room != '?':
                    for ex in self.map_graph[next_room]['exits']:
                        exit_room = self.map_graph[next_room]['exits'][ex]
                        if exit_room != self.current_room:
                            new_path = path[:]
                            new_path.append(ex)
                            q.append(new_path)
        print(f"new route: {travel_queue}")
        return travel_queue

    def travel(self, travel_queue):
        # expects a travel_queue which is a "deque"
        while len(travel_queue) > 0:
            direction = travel_queue.popleft()
            next_room = self.map_graph[self.current_room]['exits'][direction]
            data = {'direction': direction}
            # # as long as we're going in a straight line we can dash
            # if len(travel_queue) > 0 and direction == travel_queue[0]:
            #     print("can dash!")
            #     next_room_ids = [next_room]
            #     while len(travel_queue) > 0 and direction == travel_queue[0]:
            #         direction = travel_queue.popleft()
            #         next_room = self.map_graph[next_room]['exits'][direction]
            #         next_room_ids.append(next_room)
            #     # handle case we're traveling to a '?'
            #     if next_room_ids[len(next_room_ids) - 1] == '?':
            #         next_room_ids.pop()
            #     room_count = len(next_room_ids)
            #     #'{"direction":"n", "num_rooms":"5", "next_room_ids":"10,19,20,63,72"}'
            #     data['num_rooms'] = room_count
            #     data['next_room_ids'] = ",".join(next_room_ids)
            #     data_json = json.dumps(data)
            #     print(f"dash: {data_json}")
            #     r = requests.post(self.server_url + '/dash/',
            #                       headers=self.auth_header, data=data_json)
            # else:
            # not a straight line
            # if we know the id of the next room, add to the data for the request to get "Wise Explorer" reduction of cooldown
            if next_room != '?':
                data['next_room_id'] = next_room
            data_json = json.dumps(data)
            r = requests.post(self.server_url + '/move/',
                              headers=self.auth_header, data=data_json)
            r_data = r.json()
            # TODO maybe extra sleep:
            time.sleep(r_data['cooldown'])
            self.orient(r_data, direction)
            print("-" * 20)
            print(f"travel request: {r_data}")
            # clear travel_queue and set self.encumbered if we are over encumbered an not aware
            if not self.encumbered and "Heavily Encumbered: +100% CD" in r_data['messages']:
                self.encumbered = True
                travel_queue = []
            time.sleep(self.cool_down)
            while len(r_data['items']) > 0 and not self.encumbered:
                data = json.dumps({'name': 'treasure'})
                r = requests.post(self.server_url + '/take/',
                                  headers=self.auth_header, data=data)
                r_data = r.json()
                print("$" * 20)
                print(f"treasure found: {r_data}")
                time.sleep(r_data['cooldown'])

    def explore(self):
        while True:
            if not self.encumbered:
                # keep exploring until over encumbered by treasure
                travel_queue = self.get_route_to('?')
                self.travel(travel_queue)
            else:
                # travel to shop and sell treasure
                print("Too much treasure, travel to shop")
                # dump one treasure first
                data = json.dumps({"name": "treasure"})
                r = requests.post(self.server_url + '/drop/',
                                  headers=self.auth_header, data=data)
                r_data = r.json()
                time.sleep(r_data['cooldown'])
                travel_queue = self.get_route_to('1')
                self.travel(travel_queue)
                print("Arrived at shop, sell treasures!")
                # figure out how many treasures we have
                r = requests.post(self.server_url + '/status/',
                                  headers=self.auth_header)
                r_data = r.json()
                treasure_count = len(r_data['inventory'])
                time.sleep(r_data['cooldown'])
                for count in range(treasure_count):
                    data = json.dumps({"name": "treasure", "confirm": "yes"})
                    r = requests.post(self.server_url + '/sell/',
                                      headers=self.auth_header, data=data)
                    r_data = r.json()
                    print(f"sale response: {r_data}")
                    time.sleep(r_data['cooldown'])
                self.encumbered = False


explorer = Explorer()
explorer.explore()
