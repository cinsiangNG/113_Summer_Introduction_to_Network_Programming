import socket
import threading
import json

class LobbyServer:
    def __init__(self, host='127.0.0.1', port=12345):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((host, port))
        self.server_socket.listen(5)
        self.players = {}  # Stores usernames and passwords
        self.player_status = {}  # Stores player statuses
        self.client_sockets = {}  # Stores connected clients
        self.rooms = {}  # Stores room information
        self.game_servers = {}  # 存储游戏服务器信息

    def send_message(self, client_socket, message):
        try:
            message_str = json.dumps(message)
            client_socket.send(message_str.encode('utf-8'))
        except Exception as e:
            print(f"發送消息時出錯: {e}")

    def handle_client(self, client_socket):
        username = None
        while True:
            try:
                request = client_socket.recv(1024).decode('utf-8')
                if not request:
                    break  # Client has disconnected
                response = self.process_request(request, client_socket, username)
                
                # Update username if successfully logged in
                if response and response['status'] == 'success' and 'username' in response:
                    username = response['username']
                
                if response:
                    self.send_message(client_socket, response)
            except Exception as e:
                print(f"處理客戶端請求時出錯: {e}")
                break
        
        # Clean up after client disconnects
        if username:
            self.logout(username)
        client_socket.close()

    def process_request(self, request, client_socket, username):
        data = json.loads(request)
        action = data.get('action')
        request_id = data.get('request_id')  

        print(f"Received request: {data}")
        if action == 'register':
            response = self.register(data['username'], data['password'], client_socket)
        elif action == 'login':
            response = self.login(data['username'], data['password'], client_socket)
        elif action == 'logout':
            response = self.logout(username)
        elif action == 'create_room':
            response = self.create_room(data['room_type'], username, data['room_name'])
        elif action == 'join_room':
            response = self.join_room(data['room_name'], username)
        elif action == 'list_rooms':
            response = self.list_rooms()
        elif action == 'invite_player':
            response = self.invite_player(data['room_name'], username, data['invited_player'])
        elif action == 'respond_to_invite':
            response = self.handle_invite_response(data['room_name'], username, data['response'])
        elif action == 'set_game_server':
            response = self.set_game_server(data['room_name'], data['ip'], data['port'])
        elif action == 'get_game_server':
            response = self.get_game_server(data['room_name'])
        else:
            response = {'status': 'error', 'message': 'Invalid action.'}
        
        # 在響應中加入請求ID
        if request_id:
            response['request_id'] = request_id
        
        return response

    def register(self, username, password, client_socket):
        if username in self.players:
            return {'status': 'error', 'message': 'User already exists.'}
        self.players[username] = password
        return {'status': 'success', 'message': 'Registration successful.'}

    def login(self, username, password, client_socket):
        if username not in self.players:
            return {'status': 'error', 'message': 'User does not exist.'}
        elif self.players[username] != password:
            return {'status': 'error', 'message': 'Incorrect password.'}
        else:
            self.player_status[username] = 'idle' 
            self.client_sockets[username] = client_socket
            return {
                'status': 'success', 
                'message': 'Login successful.', 
                'players': self.get_all_players(),
                'username': username 
            }

    def logout(self, username):
        if username in self.client_sockets:
            del self.client_sockets[username]
        if username in self.player_status:
            del self.player_status[username]
        #if username in self.players:
        #del self.players[username]  
        return {'status': 'success', 'message': 'Logout successful.'}

    def get_all_players(self):
        return {username: status for username, status in self.player_status.items()}

    def create_room(self, room_type, creator, room_name):
        if not creator:
            return {'status': 'error', 'message': 'User must be logged in to create a room.'}
        self.rooms[room_name] = {
            'type': room_type,
            'status': 'waiting',
            'players': [creator],
            'creator': creator,
            'invited_players':[]
        }
        self.player_status[creator] = 'in room'
        return {'status': 'success', 'message': f'{room_name} created as {room_type} room.'}

    def join_room(self, room_name, username):
        if not username:
            return {'status': 'error', 'message': 'User must be logged in to join a room.'}
        
        if room_name not in self.rooms:
            return {'status': 'error', 'message': 'Room does not exist.'}
        
        room = self.rooms[room_name]
        if room['status'] == 'waiting':
            room['players'].append(username)
            if len(room['players']) > 1:
                room['status'] = 'playing'
                for player in room['players']:
                    self.player_status[player] = 'playing'
                
                # 通知房主有玩家加入,可以開始遊戲
                creator = room['creator']
                if creator in self.client_sockets:
                    accept_message = {
                        'status': 'invite_accepted',
                        'room_name': room_name,
                        'player': username
                    }
                    self.client_sockets[creator].send(json.dumps(accept_message).encode('utf-8'))
                
            return {'status': 'success', 'message': f'Joined {room_name}.'}
        else:
            return {'status': 'error', 'message': 'Room is already in game.'}

    def list_rooms(self):
        available_rooms = {
            room_name: {'type': room['type'], 'creator': room['creator'], 'status': room['status']}
            for room_name, room in self.rooms.items() if room['type'] == 'public'

        }
        return {'status': 'success', 'rooms': available_rooms}
    
    def invite_player(self, room_name, inviter, invited_player):
        if room_name not in self.rooms:
            return {'status': 'error', 'message': '房间不存在'}
        
        room = self.rooms[room_name]
        if room['type'] != 'private':
            return {'status': 'error', 'message': '这不是私人房间'}
        
        if self.player_status.get(invited_player) != 'idle':
            return {'status': 'error', 'message': '该玩家不处于空闲状态'}
        
        # 发送邀请给目标玩家
        if invited_player in self.client_sockets:
            invite_message = {
                'status': 'invite',
                'room_name': room_name,
                'inviter': inviter
            }
            self.client_sockets[invited_player].send(json.dumps(invite_message).encode('utf-8'))
            room['invited_players'].append(invited_player)
            return {'status': 'success', 'message': f'已向 {invited_player} 发送邀请'}
        return {'status': 'error', 'message': '玩家不在线'}

    def handle_invite_response(self, room_name, username, response):
        if response:  # 接受邀请
            room = self.rooms[room_name]
            room['players'].append(username)
            # 通知房主邀请已被接受
            creator = room['creator']
            if creator in self.client_sockets:
                accept_message = {
                    'status': 'invite_accepted',
                    'room_name': room_name,
                    'player': username
                }
                self.client_sockets[creator].send(json.dumps(accept_message).encode('utf-8'))
            return {'status': 'success', 'message': '已接受邀请'}
        return {'status': 'error', 'message': '已拒绝邀请'}

    def set_game_server(self, room_name, ip, port):
        self.game_servers[room_name] = {'ip': ip, 'port': port}
        # 通知所有房間玩家遊戲服務器信息
        room = self.rooms[room_name]
        for player in room['players']:
            if player in self.client_sockets and player != room['creator']:
                server_info = {
                    'status': 'game_start',
                    'ip': ip,
                    'port': port
                }
                self.client_sockets[player].send(json.dumps(server_info).encode('utf-8'))
        return {'status': 'success', 'message': '遊戲服務器信息已設置'}

    def get_game_server(self, room_name):
        if room_name in self.game_servers:
            return {'status': 'success', 'server_info': self.game_servers[room_name]}
        return {'status': 'error', 'message': '游戏服务器信息不存在'}

    def run(self):
        print("Lobby server is running...")
        while True:
            client_socket, addr = self.server_socket.accept()
            print(f"Connection from {addr}")
            client_handler = threading.Thread(target=self.handle_client, args=(client_socket,))
            client_handler.start()

if __name__ == "__main__":
    server = LobbyServer()
    server.run()

#所有公開遊戲的房間(包含創建者、遊戲類型、房間狀態)。
#status 換成idle