import socket
import threading
import json
import csv
import os

class LobbyServer:
    def __init__(self, host='140.113.235.151', port=12222):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((host, port))
        self.server_socket.listen(5)
        self.players = {}  # Stores usernames and passwords
        self.player_status = {}  # Stores player statuses
        self.client_sockets = {}  # Stores connected clients
        self.rooms = {}  # Stores room information
        self.game_servers = {}  # 存储游戏服务器信息
        self.games = {}  # 存储游戏信息
        self.load_users()

    def load_users(self):
        """從CSV文件加載用戶信息"""
        try:
            with open('users.csv', mode='r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                for row in reader:
                    username, password = row
                    self.players[username] = password  
        except FileNotFoundError:
            print("用戶文件未找到，將創建新文件。")

    def save_user(self, username, password):
        """將新用戶信息寫入CSV文件"""
        with open('users.csv', mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([username, password]) 

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
        # print("Received request data:", request)
        data = json.loads(request)
        action = data.get('action')
        request_id = data.get('request_id')

        # print(f"Received request: {data}")
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
            response = self.set_game_server(data['room_name'], data['ip'], data['port'], data['game_type'])
        elif action == 'get_game_server':
            response = self.get_game_server(data['room_name'])
        elif action == 'upload_game':
            response = self.handle_game_upload(
                game_name=data['game_name'],
                game_content=data['game_content'],
                description=data['description'],
                publisher=username,
                chunk_index=data.get('chunk_index', 0),
                total_chunks=data.get('total_chunks', 1)
            )
        elif action == 'upload_game_chunk':
            response = self.handle_game_upload(
                game_name=data['game_name'],
                game_content=data['game_content'],
                description="",  
                publisher=username,
                chunk_index=data['chunk_index'],
                total_chunks=data.get('total_chunks', 1)
            )
        elif action == 'list_games':
            response = self.list_games()
        elif action == 'download_game':
            response = self.handle_game_download(data['game_name'])
        else:
            response = {'status': 'error', 'message': 'Invalid action.'}
        
        if request_id:
            response['request_id'] = request_id
        
        return response

    def register(self, username, password, client_socket):
        if username in self.players:
            return {'status': 'error', 'message': 'User already exists.'}
        self.players[username] = password
        self.save_user(username, password)  # 註冊時保存用戶信息
        return {'status': 'success', 'message': 'Registration successful.'}

    def login(self, username, password, client_socket):
        if username not in self.players:
            return {'status': 'error', 'message': 'User does not exist.'}
        elif self.players[username] != password:
            return {'status': 'error', 'message': 'Incorrect password.'}
        else:
            self.player_status[username] = 'idle' 
            self.client_sockets[username] = client_socket
            self.broadcast({'status': 'notification', 'message': f'Lobby boardcasting: {username} 已加入大廳'})  # 廣播登錄通知
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
        self.broadcast({'status': 'notification', 'message': f'Lobby boardcasting: {username} 已退出大廳'})  # 廣播登出通知
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
        self.broadcast({'status': 'notification', 'message': f'Lobby boardcasting: {creator} 創建了房間 {room_name} 作為 {room_type} 房間'})  # 廣播創建房間通知
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
        room = self.rooms[room_name]
        creator = room['creator']
        if response:  # 接受邀请
            room['players'].append(username)
            # 通知房主邀请已被接受
            if creator in self.client_sockets:
                accept_message = {
                    'status': 'invite_accepted',
                    'room_name': room_name,
                    'player': username
                }
                self.client_sockets[creator].send(json.dumps(accept_message).encode('utf-8'))
            return {'status': 'success', 'message': '已接受邀请'}
        else:  # 拒绝邀请
            # 通知房主邀请已被拒绝
            if creator in self.client_sockets:
                reject_message = {
                    'status': 'invite_rejected',
                    'room_name': room_name,
                    'player': username
                }
                self.client_sockets[creator].send(json.dumps(reject_message).encode('utf-8'))
            return {'status': 'error', 'message': '已拒绝邀请'}

    def set_game_server(self, room_name, ip, port, game_type):
        """設置遊戲服務器信息並通知其他玩家"""
        self.game_servers[room_name] = {
            'ip': ip, 
            'port': port,
            'game_type': game_type
        }
        
        # 通知所有房間玩家遊戲服務器信息
        room = self.rooms[room_name]
        for player in room['players']:
            if player in self.client_sockets and player != room['creator']:
                server_info = {
                    'status': 'game_start',
                    'ip': ip,
                    'port': port,
                    'game_type': game_type 
                }
                self.client_sockets[player].send(json.dumps(server_info).encode('utf-8'))
        return {'status': 'success', 'message': '遊戲服務器信息已設置'}

    def get_game_server(self, room_name):
        if room_name in self.game_servers:
            return {'status': 'success', 'server_info': self.game_servers[room_name]}
        return {'status': 'error', 'message': '游戏服务器信息不存在'}
    
    def broadcast(self, message):
        """廣播消息給所有連接的客戶端"""
        for client_socket in self.client_sockets.values():
            self.send_message(client_socket, message)

    def run(self):
        print("Lobby server is running...")
        while True:
            client_socket, addr = self.server_socket.accept()
            print(f"Connection from {addr}")
            client_handler = threading.Thread(target=self.handle_client, args=(client_socket,))
            client_handler.start()
    
   

    def handle_game_upload(self, game_name, game_content, description, publisher, chunk_index=0, total_chunks=1):
        """處理遊戲上傳"""
        try:
            game_name_without_ext = game_name.replace('.py', '')
            
            # 確保目錄存在
            if not os.path.exists('Lobby/games'):
                os.makedirs('Lobby/games')
            
            # 解析轉義後的內容
            game_content = bytes(game_content, 'utf-8').decode('unicode_escape')
            
            # 如果是第一個塊，保存游戲信息到CSV
            if chunk_index == 0:
                # 使用不带后缀的名称保存到 CSV
                self.save_game_info(game_name_without_ext, publisher, description)
                print("\n=== 保存游戲信息 ===")
                print(f"遊戲名稱: {game_name_without_ext}")
                print(f"發布者: {publisher}")
                print(f"描述: {description}")
                print("==================\n")

            print(f"正在處理塊 {chunk_index + 1}/{total_chunks}")
            
            # 文件仍然使用原始名称（带 .py）保存
            temp_path = os.path.join('Lobby/games', game_name)
            final_path = os.path.join('Lobby/games', game_name)
            
            # 寫入模式：第一個塊是 'w'，後續塊是 'a'
            mode = 'w' if chunk_index == 0 else 'a'
            with open(temp_path, mode, encoding='utf-8') as f:
                f.write(game_content)
            
            # 如果是最後一個塊，完成上傳
            if chunk_index == total_chunks - 1:
                # 重命名臨時文件
                if os.path.exists(final_path):
                    os.remove(final_path)
                os.rename(temp_path, final_path)
                
                return {
                    'status': 'success',
                    'message': '遊戲上傳成功'
                }
            else:
                return {
                    'status': 'success',
                    'message': f'已接收塊 {chunk_index + 1}/{total_chunks}'
                }
                
        except Exception as e:
            print(f"遊戲上傳錯誤: {e}")
            # 清理臨時文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return {
                'status': 'error',
                'message': f'上傳失敗: {str(e)}'
            }

    def save_game_info(self, game_name, publisher, description):
        """將遊戲信息保存到CSV文件"""
        try:
            # 確保目錄存在
            os.makedirs('Lobby', exist_ok=True)
            
            csv_path = 'Lobby/games.csv'
            file_exists = os.path.exists(csv_path)
            
            with open(csv_path, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                
                # 如果文件不存在，寫入表頭
                if not file_exists:
                    writer.writerow(['game_name', 'publisher', 'description'])
                
                # 寫入遊戲信息
                writer.writerow([game_name, publisher, description])
                
            # 更新内存中的游戏信息
            self.games[game_name] = {
                'publisher': publisher,
                'description': description
            }
            
            print(f"遊戲信息已保存到 {csv_path}")
            
        except Exception as e:
            print(f"保存遊戲信息時出錯: {e}")
            raise

    def list_games(self):
        """返回所有遊戲列表"""
        try:
            games_dict = {}
            csv_path = 'Lobby/games.csv'
            
            if not os.path.exists(csv_path):
                return {
                    'status': 'success',
                    'games': [],
                    'message': '目前沒有任何遊戲'
                }
            
            with open(csv_path, mode='r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    games_dict[row['game_name']] = {
                        'name': row['game_name'],
                        'publisher': row['publisher'],
                        'description': row['description']
                }
                    
            # 将字典值转换为列表
            games_list = list(games_dict.values())
            return {
                'status': 'success',
                'games': games_list,
                'message': '成功獲取遊戲列表'
            }
            
        except Exception as e:
            print(f"讀取遊戲列表時出錯: {e}")
            return {
                'status': 'error',
                'message': f'獲取遊戲列表失敗: {str(e)}'
            }

    def handle_game_download(self, game_name):
        """處理遊戲下載請求"""
        try:
            game_path = os.path.join('Lobby/games', f"{game_name}.py")
            
            if not os.path.exists(game_path):
                return {
                    'status': 'error',
                    'message': '遊戲文件不存在'
                }
            
            with open(game_path, 'r', encoding='utf-8') as f:
                game_content = f.read()
            
            return {
                'status': 'success',
                'game_content': game_content,
                'message': '遊戲下載成功'
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'下載失敗: {str(e)}'
            }

if __name__ == "__main__":
    server = LobbyServer()
    server.run()

#所有公開遊戲的房間(包含創建者、遊戲類型、房間狀態)。
#status 換成idle