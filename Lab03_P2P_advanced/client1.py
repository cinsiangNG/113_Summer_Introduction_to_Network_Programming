import socket
import json
import threading
import time
from game_server import GameServer
import os

class Client:
    def __init__(self, host='140.113.235.151', port=12222):
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
            elif message['status'] == 'invite_rejected':
                print(f"\n玩家 {message['player']} 已拒絕您的邀請加入房間 {message['room_name']}")
                self.is_handling_invite = False
                self.is_playing = False
                print("\n返回大廳...")
                return
            elif message['status'] == 'game_start':
                self.handle_game_start(message)
            elif message['status'] == 'notification':
                print(f"\n通知: {message['message']},請繼續上面的選擇......")
        except Exception as e:
            print(f"處理消息時出錯: {e}")

    def handle_invite(self, message):
        try:
            # 設置標誌表示正在處理邀請
            self.is_handling_invite = True
            print(f"\n收到来自 {message['inviter']} 的邀請加入房間 {message['room_name']}")
            response = input(f"是否接受邀請？(y/n): ").lower() == 'y'
            
            # 新增拒絕邀請的處理
            if not response:
                self.send_request('respond_to_invite', room_name=message['room_name'], response=False)
                print(f"玩家 {message['inviter']} 已被通知您拒絕了邀請")
                self.is_handling_invite = False
                return
            
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
                print(f"\n玩家 {message['player']} 加入了游戲,請輸入任意鍵以繼續.....")
                input()
            
            # 直接讀取 Lobby/games 目錄下的遊戲文件
            games_dir = 'Lobby/games'
            if not os.path.exists(games_dir):
                print("\n目前沒有任何可用的遊戲")
                return
            
            # 獲取遊戲列表並移除.py後綴
            games = [f.replace('.py', '') for f in os.listdir(games_dir) if f.endswith('.py')]
            if not games:
                print("\n目前沒有任何可用的遊戲")
                return

            # 顯示遊戲列表
            print("\n=== 可選擇的遊戲 ===")
            for i, game in enumerate(games, 1):
                print(f"{i}. {game}")

            # 選擇要使用的遊戲
            while True:
                try:
                    choice = int(input("\n請選擇要使用的遊戲編號: "))
                    if 1 <= choice <= len(games):
                        break
                    print("無效的選擇，請重新輸入")
                except ValueError:
                    print("請輸入有效的數字")

            selected_game = games[choice - 1]
            game_type = selected_game  # 設置game_type為選擇的遊戲名稱
            
            # 複製選定的遊戲到下載目錄（需要加回.py後綴）
            download_dir = 'Client/download_games/'
            os.makedirs(download_dir, exist_ok=True)
            
            # 複製遊戲文件
            source_path = os.path.join(games_dir, f"{selected_game}.py")
            target_path = os.path.join(download_dir, f"{selected_game}.py")
            
            with open(source_path, 'r', encoding='utf-8') as source:
                game_content = source.read()
            with open(target_path, 'w', encoding='utf-8') as target:
                target.write(game_content)
            
            print(f"\n遊戲 '{selected_game}' 已準備就緒")

            # 設置端口
            while True:
                try:
                    port = int(input("\n請輸入遊戲服務器端口號碼 (1024-65535): "))
                    if 1024 <= port <= 65535:
                        break
                    print("端口號碼必須在 1024-65535 之間")
                except ValueError:
                    print("請輸入有效的數字")
            
            # 使用下載的遊戲啟動遊戲服務器，傳入game_type
            game_server = GameServer(game_type, port)
            game_port = game_server.port
            
            if game_port != port:
                print(f"指定的端口 {port} 已被占用，使用新端口 {game_port}")
            
            self.send_request('set_game_server', room_name=message['room_name'], 
                            ip='140.113.235.151', port=game_port, game_type=game_type)
            
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
        
        # 從消息中獲取遊戲類型
        game_type = message['game_type']
        
        # 下載遊戲文件
        games_dir = 'Lobby/games'
        download_dir = 'Client/download_games/'
        os.makedirs(download_dir, exist_ok=True)
        
        # 複製遊戲文件（需要加上.py後綴）
        source_path = os.path.join(games_dir, f"{game_type}.py")
        target_path = os.path.join(download_dir, f"{game_type}.py")
        
        with open(source_path, 'r', encoding='utf-8') as source:
            game_content = source.read()
        with open(target_path, 'w', encoding='utf-8') as target:
            target.write(game_content)
        
        print(f"\n遊戲 '{game_type}' 已準備就緒")
        
        print("\n=== 遊戲開始 ===")
        game_thread = threading.Thread(target=self.play_game, args=(game_socket,))
        game_thread.daemon = True
        game_thread.start()

    def upload_game(self, game_path, description):
        try:
            with open(game_path, 'r', encoding='utf-8') as file:
                game_content = file.read()
                game_content = repr(game_content)[1:-1] 
            
            chunk_size = 512 
            chunks = [game_content[i:i+chunk_size] for i in range(0, len(game_content), chunk_size)]
            total_chunks = len(chunks)
            
            game_name = os.path.basename(game_path)
            
            print(f"\n開始上傳 {game_name}")
            print("上傳進度: [", end="")
            
            # 發送第一個請求，包含文件信息
            response = self.send_request(
                'upload_game',
                game_name=game_name,
                total_chunks=total_chunks,
                chunk_index=0,
                game_content=chunks[0],
                description=description
            )
            print("=", end="", flush=True)
            
            # 發送剩餘的塊
            for i in range(1, total_chunks):
                if response['status'] != 'success':
                    break
                    
                response = self.send_request(
                    'upload_game_chunk',
                    game_name=game_name,
                    chunk_index=i,
                    game_content=chunks[i]
                )
                
                # 顯示進度
                if i % (total_chunks // 50 + 1) == 0: 
                    print("=", end="", flush=True)
            
            print("] 100%")
            
            return response
        except Exception as e:
            print(f"\n上傳過程中出錯: {e}")
            return {'status': 'error', 'message': str(e)}
        
    def handle_game_management(self):
        while True:
            try:
                print("\n=== 遊戲管理 ===")
                print("1. 查看大廳遊戲")
                print("2. 上傳遊戲")
                print("3. 下載遊戲")
                print("4. 返回")
                
                game_action = input("請選擇操作: ")
                
                if game_action == '1':
                    self.list_all_games()
                elif game_action == '2':
                    print("\n請將遊戲文件放在 games 文件夾中")
                    print("可用的遊戲文件:")
                    
                    # 確保 games 目錄存在
                    games_dir = 'Client/my_games'
                    if not os.path.exists(games_dir):
                        os.makedirs(games_dir)
                        
                    games = [f for f in os.listdir(games_dir) if f.endswith('.py')]
                    
                    if not games:
                        print("未找到可上傳的遊戲文件")
                        return
                        
                    for i, game in enumerate(games, 1):
                        print(f"{i}. {game}")
                    
                    try:
                        choice = int(input("\n請選擇要上傳的遊戲編號 (0 取消): "))
                        if choice == 0:
                            return
                        if choice < 1 or choice > len(games):
                            print("無效的選擇")
                            return
                            
                        game_file = games[choice - 1]
                        description = input("請輸入遊戲描述: ")
                        
                        game_path = os.path.join(games_dir, game_file)
                        response = self.upload_game(game_path, description)
                        
                        if response['status'] == 'success':
                            print("\n遊戲上傳成功！")
                        else:
                            print(f"\n上傳失敗: {response.get('message', '未知錯誤')}")
                    
                    except ValueError:
                        print("請輸入有效的數字")
                    except Exception as e:
                        print(f"操作出錯: {e}")
                    
                elif game_action == '3':
                    self.download_game()
                elif game_action == '4':
                    break
                else:
                    print("無效的選擇")
                    
            except Exception as e:
                print(f"遊戲管理出錯: {e}")

    def list_all_games(self):
        """列出所有可用的游戏"""
        try:
            response = self.send_request('list_games')
            if response['status'] == 'success':
                games = response.get('games', [])
                if games:
                    print("\n=== 大廳遊戲列表 ===")
                    print("{:<15} {:<15} {:<30}".format("遊戲名稱", "發布者", "描述"))
                    print("-" * 60)
                    
                    for game in games:
                        print("{:<15} {:<15} {:<30}".format(
                            game['name'],
                            game['publisher'],
                            game['description']
                        ))
                    print("-" * 60)
                    print(f"總共有 {len(games)} 個遊戲\n")
                else:
                    print("\n目前大廳沒有任何遊戲")
                    print("您可以通過'上傳遊戲'功能來添加遊戲\n")
            else:
                print(f"\n獲取遊戲列表失敗: {response.get('message', '未知錯誤')}")
            
        except Exception as e:
            print(f"列出遊戲時出錯: {e}")

    def download_game(self):
        """下載選定的遊戲"""
        try:
            # 獲取可用遊戲列表
            response = self.send_request('list_games')
            if response['status'] != 'success':
                print(f"\n獲取遊戲列表失敗: {response.get('message', '未知錯誤')}")
                return

            games = response.get('games', [])
            if not games:
                print("\n目前大廳沒有任何遊戲可供下載")
                return

            # 顯示遊戲列表
            print("\n=== 可下載的遊戲 ===")
            for i, game in enumerate(games, 1):
                print(f"{i}. {game['name']} (發布者: {game['publisher']})")

            # 選擇要下載的遊戲
            try:
                choice = int(input("\n請選擇要下載的遊戲編號 (0 取消): "))
                if choice == 0:
                    return
                if choice < 1 or choice > len(games):
                    print("無效的選擇")
                    return

                selected_game = games[choice - 1]
                game_name = selected_game['name']

                # 發送下載請求
                response = self.send_request('download_game', game_name=game_name)
                
                if response['status'] == 'success':
                    # 確保目標目錄存在
                    download_dir = 'Client/download_games/'
                    os.makedirs(download_dir, exist_ok=True)
                    
                    # 保存遊戲文件
                    game_path = os.path.join(download_dir, f"{game_name}.py")
                    with open(game_path, 'w', encoding='utf-8') as f:
                        f.write(response['game_content'])
                    
                    print(f"\n遊戲 '{game_name}' 已成功下載到 {game_path}")
                else:
                    print(f"\n下載失敗: {response.get('message', '未知錯誤')}")

            except ValueError:
                print("請輸入有效的數字")
            except Exception as e:
                print(f"下載過程中出錯: {e}")

        except Exception as e:
            print(f"下載遊戲時出錯: {e}")

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
                            action = input("請選擇操作 (1: create_room, 2: join_room, 3: logout, 4: list_rooms, 5: game management): ")
                        
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
                            elif action == '5':
                                client.handle_game_management()
                            else:
                                print("無效的操作，請重新選擇。")

                elif response['status'] == 'error':
                    print(response['message'])
        except KeyboardInterrupt:
            print("\n程序已終。")
            break
        except Exception as e:
            print(f"發生錯誤: {e}")

    client.close()
