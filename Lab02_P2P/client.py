import socket
import json
import threading
import time
from game_server import GameServer
class Client:
    def __init__(self, host='127.0.0.1', port=12345):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.connect((host, port))
        self.current_room = None
        self.response_queue = {}
        self.message_lock = threading.Lock()
        self.is_playing = False
        self.is_handling_invite = False
        
        self.listen_thread = threading.Thread(target=self.listen_for_messages)
        self.listen_thread.daemon = True
        self.listen_thread.start()

    def send_request(self, action, **kwargs):
        request = {'action': action}
        request.update(kwargs)
        
        request_id = f"{action}_{threading.get_ident()}"
        request['request_id'] = request_id
        
        with self.message_lock:
            self.response_queue[request_id] = None
            self.server_socket.send(json.dumps(request).encode('utf-8'))
        
        for _ in range(50):
            with self.message_lock:
                response = self.response_queue.get(request_id)
                if response:
                    del self.response_queue[request_id]
                    return response
            time.sleep(0.1)
        
        return {'status': 'error', 'message': '請求超時'}

    def register(self, username, password):
        return self.send_request('register', username=username, password=password)

    def login(self, username, password):
        return self.send_request('login', username=username, password=password)

    def logout(self, username):
        return self.send_request('logout', username=username)

    def show_status(self):
        response = self.send_request('status')
        if response['status'] == 'success':
            if len(player) > 2:
                print("當前線上的玩家:")
                for player, status in response['players'].items():
                    print(f"{player}: {status}")
            else:
                print("目前無玩家在線")

    def list_rooms(self):
        response = self.send_request('list_rooms')
        if response['status'] == 'success' and response['rooms']:
            print("-------------------------------------------------")
            print("Game rooms available:")
            for room_id, room_info in response['rooms'].items():
                print(f"Room Name: {room_id}, Type: {room_info['type']}, Room Creator: {room_info['creator']}, Status: {room_info['status']}")
            print("-------------------------------------------------")
        else:
            print("-------------------------------------------------")
            print("Game rooms:\nNo game room available")
            print("-------------------------------------------------")

    def close(self):
        self.server_socket.close()

    def create_room(self, room_type, room_name):
        return self.send_request('create_room', room_type=room_type, room_name= room_name,)

    def join_room(self, room_name):
        response = self.send_request('join_room', room_name=room_name)
        if response['status'] == 'success':
            self.is_playing = True
            print("\n=== 等待房主開始遊戲 ===")
        return response

    def invite_player(self, room_name, invited_player):
        self.is_handling_invite = True
        return self.send_request('invite_player', room_name=room_name, invited_player=invited_player)

    def listen_for_messages(self):
        buffer = ""
        while True:
            try:
                data = self.server_socket.recv(1024).decode('utf-8')
                if not data:
                    break
                
                buffer += data
                
                while buffer:
                    try:
                        message = json.loads(buffer)
                        buffer = ""  # 清空緩衝區
                        
                        # 檢查是否是請求的響應
                        if 'request_id' in message:
                            with self.message_lock:
                                self.response_queue[message['request_id']] = message
                        else:
                            # 處理服務器推送的消息
                            self.handle_server_message(message)
                        break
                    except json.JSONDecodeError as e:
                        # 檢查是否有多個JSON消息
                        try:
                            pos = buffer.index("}{")
                            first_json = buffer[:pos+1]
                            buffer = buffer[pos+1:]
                            message = json.loads(first_json)
                            
                            # 檢查是否是請求的響應
                            if 'request_id' in message:
                                with self.message_lock:
                                    self.response_queue[message['request_id']] = message
                            else:
                                # 處理服務器推送的消息
                                self.handle_server_message(message)
                        except ValueError:
                            # 如果沒有找到多個JSON的分隔點，說明消息不完整
                            break
                        except json.JSONDecodeError:
                            # 如果解析失敗，丟棄損壞的數據
                            print("接收到損壞的數據，已丟棄")
                            buffer = ""
                            break
                        
            except Exception as e:
                print(f"監聽錯誤: {e}")
                break

    def handle_server_message(self, message):
        try:
            if message['status'] == 'invite':
                self.handle_invite(message)
            elif message['status'] == 'invite_accepted':
                self.handle_invite_accepted(message)
            elif message['status'] == 'game_start':
                self.handle_game_start(message)
        except Exception as e:
            print(f"處理消息時出錯: {e}")

    def handle_invite(self, message):
        try:
            # 設置標誌表示正在處理邀請
            self.is_handling_invite = True
            print(f"\n收到来自 {message['inviter']} 的邀請加入房間 {message['room_name']}")
            response = input(f"是否接受邀請？(y/n): ").lower() == 'y'
            self.send_request('respond_to_invite', room_name=message['room_name'], response=response)
        except Exception as e:
            print(f"處理邀請時出錯: {e}")
        finally:
            if response == 'n':
                self.is_handling_invite = False

    def handle_invite_accepted(self, message):
        try:
            self.is_playing = True
            if self.is_handling_invite:
                print(f"\n玩家 {message['player']} 接受了邀請")
            else:
                print(f"\n玩家 {message['player']} 加入了游戲")
            
            game_type = input("請選擇遊戲類型 (1: 猜拳遊戲, 2: 井字棋): ")
            game_type = "rock_paper_scissors" if game_type == "1" else "tic_tac_toe"
            
            while True:
                try:
                    port = int(input("請輸入遊戲服務器端口號碼 (1024-65535): "))
                    if 1024 <= port <= 65535:
                        break
                    print("端口號碼必須在 1024-65535 之間")
                except ValueError:
                    print("請輸入有效的數字")
            
            game_server = GameServer(game_type, port)
            game_port = game_server.port
            
            if game_port != port:
                print(f"指定的端口 {port} 已被占用，使用新端口 {game_port}")
            
            self.send_request('set_game_server', room_name=message['room_name'], 
                             ip='127.0.0.1', port=game_port)
            
            print("\n=== 遊戲開始 ===")
            game_server.start()  
            
            # 遊戲結束後
            self.is_playing = False
            self.is_handling_invite = False
            print("\n返回大廳...")
            
        except Exception as e:
            print(f"遊戲啟動錯誤: {e}")
            self.is_playing = False
            self.is_handling_invite = False
            print("\n返回大廳...")
            print("請選擇操作 (1: create_room, 2: join_room, 3: logout, 4: list_rooms): ")

    def play_game(self, game_socket):
        try:
            while True:
                data = game_socket.recv(1024).decode()
                game_data = json.loads(data)
                if 'game_over' in game_data:  # 處理遊戲結束
                    print("\n===== 遊戲結束 =====")
                    print(f"結果: {game_data['final_result']}")
                    print(f"最終比分 - 房主: {game_data['final_scores']['host']}, 您: {game_data['final_scores']['client']}")
                    print("==================")
                    break
            
                if 'message' in game_data:  # 猜拳遊戲
                    print("\n輪到您出拳")
                    while True:
                        choice = input("請選擇 (1:石頭 2:剪刀 3:布): ")
                        if choice in ['石頭', '剪刀', '布', '1', '2', '3']:
                            break
                        print("無效選擇，請重新輸入")
                    
                    game_socket.send(json.dumps({"choice": choice}).encode())
                    
                    result_data = json.loads(game_socket.recv(1024).decode())
                    print("\n===== 本回合結果 =====")
                    print(f"結果: {result_data['result']}")
                    print(f"房主選擇: {result_data['host_choice']}")
                    print(f"您的選擇: {result_data['client_choice']}")
                    print(f"比分 - 房主: {result_data['scores']['host']}, 您: {result_data['scores']['client']}")
                    print("=====================")

                if 'board' in game_data:  # 井字棋
                    if 'winner' in game_data:  # 遊戲結束
                        # 顯示最終棋盤
                        print("\n最終棋盤:")
                        board = game_data['board']
                        for i in range(0, 9, 3):
                            print(f"{board[i]} | {board[i+1]} | {board[i+2]}")
                            if i < 6:
                                print("---------")
                        
                        # 顯示結果
                        print("\n===== 遊戲結束 =====")
                        if game_data['winner'] == "O":
                            print("恭喜您獲勝！")
                        elif game_data['winner'] == "X":
                            print("對方獲勝！")
                        else:
                            print("遊戲平局！")
                        print("==================")
                        break
                    
                    print("\n棋盤位置對應數字: ")
                    print(" 0 | 1 | 2 ")
                    print("-----------")
                    print(" 3 | 4 | 5 ")
                    print("-----------")
                    print(" 6 | 7 | 8 \n")
                    print("當前棋盤: (您是O)")
                    board = game_data['board']
                    for i in range(0, 9, 3):
                        print(f"{board[i]} | {board[i+1]} | {board[i+2]}")
                        if i < 6:
                            print("---------")
                    
                    
                    move = int(input("請輸入位置 (0-8): "))
                    game_socket.send(json.dumps({"move": move}).encode())
            
                
        except Exception as e:
            print("\n===== 遊戲結束 =====")
            print("對方獲勝！")
            print("==================")
        finally:
            self.is_handling_invite = False
            self.is_playing = False
            print("\n返回大廳...")


    def respond_to_invite(self, room_name, response):
        return self.send_request('respond_to_invite', room_name=room_name, response=response)

    def handle_game_start(self, message):
        print(f"\n房主已開始遊戲")
        game_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        game_socket.connect((message['ip'], message['port']))
        
        print("\n=== 遊戲開始 ===")
        game_thread = threading.Thread(target=self.play_game, args=(game_socket,))
        game_thread.daemon = True
        game_thread.start()

if __name__ == "__main__":
    client = Client()
    
    while True:
        try:
            action = input("請選擇操作 (1: register, 2: login, 3: exit): ")
            if action not in ['1', '2', '3']:
                print("無效的操作，請重新選擇。")
                continue
            
            if action == '3':
                print("退出程序。")
                break  
            
            username = input("請輸入用戶名: ")
            password = input("請輸入密碼: ")

            if action == '1':
                response = client.register(username, password)
                print(response)
                if response['status'] == 'success':
                    print("Registration successful")
                    print("-------------------------------------------------")
            elif action == '2':
                response = client.login(username, password)
                print(response)
                if response['status'] == 'success':
                    print("Login successful")
                    print("-------------------------------------------------")
                    
                  
                    online_players = response.get('players', {})
                    print("Online players:")
                    if online_players:
                        if len(online_players) > 1:
                            for user, status in online_players.items():
                                print(f"Username: {user}  Status: {status}")
                        else:
                            print('No other online player available')

                    client.list_rooms()

                    # 修改登錄後的操作循環
                    while True:
                        if (hasattr(client, 'is_playing') and client.is_playing) or \
                           (hasattr(client, 'is_handling_invite') and client.is_handling_invite):
                            time.sleep(0.1)  
                            continue
                        
                        else:
                            action = input("請選擇操作 (1: create_room, 2: join_room, 3: logout, 4: list_rooms): ")
                        
                            if action == '1':
                                room_type = input("請選擇房間類型 (1: public, 2: private): ")
                                room_type = 'public' if room_type == '1' else 'private'
                                room_name = input("請輸入您想要創建的房間名稱: ")
                                response = client.create_room(room_type, room_name)
                                print(response)

                                if room_type == 'private':
                                    print("-------------------------------------------------")
                                    for user, status in online_players.items():
                                        if status == 'idle':
                                            print(f"Username: {user}  Status: {status}")
                                    print("-------------------------------------------------")
                                    invitee = input("請輸入您想要邀請的玩家名稱: ")
                                    invite_response = client.invite_player(room_name, invitee)
                                    print(invite_response)

                            elif action == '2':
                                room_name = input("請輸入房間名稱: ")
                                response = client.join_room(room_name)
                                print(response)
                            elif action == '3':
                                client.logout(username)
                                print("Logout successful")
                                break
                            elif action == '4':
                                client.list_rooms()
                            else:
                                print("無效的操作，請重新選擇。")
                elif response['status'] == 'error':
                    print(response['message'])
        except KeyboardInterrupt:
            print("\n程序已終止。")
            break
        except Exception as e:
            print(f"發生錯誤: {e}")

    client.close()
