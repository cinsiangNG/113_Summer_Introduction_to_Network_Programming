import socket
import json
import threading
import random

class GameServer:
    def __init__(self, game_type, port):
        self.game_type = game_type
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.server_socket.bind(('127.0.0.1', port))
            self.port = port
        except socket.error:
            print(f"端口 {port} 已被占用，將使用隨機端口")
            self.server_socket.bind(('127.0.0.1', 0))
            self.port = self.server_socket.getsockname()[1]
        self.server_socket.listen(1)
        self.client_socket = None
        self.game_state = {}
        
    def start(self):
        print(f"遊戲服務器啟動在端口 {self.port}")
        if self.game_type == "rock_paper_scissors":
            self.game_state = {
                "host_choice": None,
                "client_choice": None,
                "rounds": 0,
                "host_score": 0,
                "client_score": 0
            }
        elif self.game_type == "tic_tac_toe":
            self.game_state = {
                "board": [" " for _ in range(9)],
                "current_player": "X",  # X為房主，O為加入者
                "winner": None
            }
            
        self.client_socket, addr = self.server_socket.accept()
        print(f"玩家已連接：{addr}")
        
        if self.game_type == "rock_paper_scissors":
            self.play_rock_paper_scissors()
        elif self.game_type == "tic_tac_toe":
            self.play_tic_tac_toe()

    def play_rock_paper_scissors(self):
        print("\n=== 猜拳遊戲開始 ===")
        while self.game_state["rounds"] < 3:  # 三兩勝
            print(f"\n第 {self.game_state['rounds'] + 1} 回合")
            # 等待雙方選擇
            self.client_socket.send(json.dumps({"message": "請選擇"}).encode())
            print("等待對方選擇...")
            
            client_data = self.client_socket.recv(1024).decode()
            self.game_state["client_choice"] = json.loads(client_data)["choice"]
            
            self.game_state["host_choice"] = input("請選擇 (1:石頭 2:剪刀 3:布): ")
            
            # 判斷勝負
            result = self.judge_rps()
            self.game_state["rounds"] += 1
            
            # 顯示結果
            print("\n===== 本回合結果 =====")
            print(f"結果: {result}")
            print(f"您的選擇: {self.game_state['host_choice']}")
            print(f"對方選擇: {self.game_state['client_choice']}")
            print(f"比分 - 您: {self.game_state['host_score']}, 對方: {self.game_state['client_score']}")
            print("=====================")
            
            # 發送結果給客戶端
            self.client_socket.send(json.dumps({
                "result": result,
                "host_choice": self.game_state["host_choice"],
                "client_choice": self.game_state["client_choice"],
                "scores": {
                    "host": self.game_state["host_score"],
                    "client": self.game_state["client_score"]
                }
            }).encode())
        
        print("\n===== 遊戲結束 =====")
        if self.game_state["host_score"] > self.game_state["client_score"]:
            final_result = "您贏了！"
            client_result = "對方贏了！"
        elif self.game_state["host_score"] < self.game_state["client_score"]:
            final_result = "對方贏了！"
            client_result = "您贏了！"
        else:
            final_result = "平局！"
            client_result = "平局！"
            
        print(final_result)
        print("==================")
        
        # 發送最終結果給客戶端
        self.client_socket.send(json.dumps({
            "game_over": True,
            "final_result": client_result,
            "final_scores": {
                "host": self.game_state["host_score"],
                "client": self.game_state["client_score"]
            }
        }).encode())

    def judge_rps(self):
        choices = {
            "石頭": 0, "1": 0,
            "剪刀": 1, "2": 1,
            "布": 2, "3": 2
        }
        
        # 檢查輸入是否有效
        if self.game_state["host_choice"] not in choices or self.game_state["client_choice"] not in choices:
            return "無效的選擇"
        
        host = choices[self.game_state["host_choice"]]
        client = choices[self.game_state["client_choice"]]
        
        if host == client:
            return "平局"
        elif (host - client) % 3 == 1:
            self.game_state["client_score"] += 1
            return "客戶端贏"
        else:
            self.game_state["host_score"] += 1
            return "房主贏"

    def play_tic_tac_toe(self):
        while not self.game_state["winner"]:
            print("\n當前棋盤: (您是X)")
            board = self.game_state['board']
            for i in range(0, 9, 3):
                print(f"{board[i]} | {board[i+1]} | {board[i+2]}")
                if i < 6:
                    print("---------")
            print("\n棋盤位置對應數字: ")
            print(" 0 | 1 | 2 ")
            print("-----------")
            print(" 3 | 4 | 5 ")
            print("-----------")
            print(" 6 | 7 | 8 ")
            if self.game_state["current_player"] == "X":
                # 房主回合
                move = int(input("請輸入位置 (0-8): "))
                if self.make_move(move):
                    self.client_socket.send(json.dumps({
                        "board": self.game_state["board"],
                        "move": move
                    }).encode())
            else:
                print("等待對方下棋...")
                data = self.client_socket.recv(1024).decode()
                move_data = json.loads(data)
                self.make_move(move_data["move"])
            
            # 檢查勝負
            winner = self.check_winner()
            if winner:
                self.game_state["winner"] = winner
                # 顯示最終棋盤
                print("\n最終棋盤:")
                board = self.game_state['board']
                for i in range(0, 9, 3):
                    print(f"{board[i]} | {board[i+1]} | {board[i+2]}")
                    if i < 6:
                        print("---------")
                
                # 顯示結果
                print("\n===== 遊戲結束 =====")
                if winner == "X":
                    print("恭喜您獲勝！")
                elif winner == "O":
                    print("對方獲勝！")
                else:
                    print("遊戲平局！")
                print("==================")
                
                # 發送結果給客戶端
                self.client_socket.send(json.dumps({
                    "winner": winner,
                    "board": self.game_state["board"]
                }).encode())
                break

    def make_move(self, position):
        if self.game_state["board"][position] == " ":
            self.game_state["board"][position] = self.game_state["current_player"]
            self.game_state["current_player"] = "O" if self.game_state["current_player"] == "X" else "X"
            return True
        return False

    def check_winner(self):
        # 檢查行
        for i in range(0, 9, 3):
            if self.game_state["board"][i] == self.game_state["board"][i+1] == self.game_state["board"][i+2] != " ":
                return self.game_state["board"][i]
        
        # 檢查列
        for i in range(3):
            if self.game_state["board"][i] == self.game_state["board"][i+3] == self.game_state["board"][i+6] != " ":
                return self.game_state["board"][i]
        
        # 檢查對角線
        if self.game_state["board"][0] == self.game_state["board"][4] == self.game_state["board"][8] != " ":
            return self.game_state["board"][0]
        if self.game_state["board"][2] == self.game_state["board"][4] == self.game_state["board"][6] != " ":
            return self.game_state["board"][2]
        
        # 檢查平局
        if " " not in self.game_state["board"]:
            return "平局"
        
        return None

    def close(self):
        if self.client_socket:
            self.client_socket.close()
        self.server_socket.close()