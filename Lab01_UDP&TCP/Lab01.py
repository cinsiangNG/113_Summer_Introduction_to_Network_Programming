import socket
import json
import threading
import random
import time

UDP_PORT_START = 10000
UDP_PORT_END = 10020
TCP_PORT_START = 10021
TCP_PORT_END = 10040
#SERVERS = ['140.113.235.151', '140.113.235.152', '140.113.235.153', '140.113.235.154']
SERVERS = ['140.113.235.151']
BUFFER_SIZE = 4096 
# SERVERS = ['127.0.0.1']

player_name = input("請輸入你的名字: ")

SERVER_IP = '140.113.235.151' 
def udp_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for port in range(UDP_PORT_START, UDP_PORT_END + 1):
        try:
            server_socket.bind(('', port))
            print(f"UDP服务器正在监听端口 {port}")
            break
        except:
            continue
    
    while True:
        try:
            data, addr = server_socket.recvfrom(BUFFER_SIZE)
            if data:
                print(f"接收到的原始數據: {data}")
                message = json.loads(data.decode())
            else:
                print("接收到空數據")
            
            if message['type'] == 'check':
                response = json.dumps({
                    'type': 'available',
                    'name': player_name
                })
                server_socket.sendto(response.encode(), addr)
            
            elif message['type'] == 'invite':
                print(f"收到來自 {message['name']} 的邀請。接受? (y/n)")
                if input().lower() == 'y':
                    response = json.dumps({
                        'type': 'accept',
                        'name': player_name
                    })
                    server_socket.sendto(response.encode(), addr)
                    
                    data, _ = server_socket.recvfrom(BUFFER_SIZE)
                    tcp_info = json.loads(data.decode())
                    return tcp_info['ip'], tcp_info['port']
                else:
                    response = json.dumps({
                        'type': 'reject',
                        'name': player_name
                    })
                    server_socket.sendto(response.encode(), addr)
                    print("邀請被拒絕，等待其他玩家的邀請...") 

        except ConnectionResetError:
            print("连接被远程主机重置。等待新的连接...")
            continue
        except json.JSONDecodeError as e:
            print(f"JSON 解析錯誤: {e}")
            print(f"接收到的數據: {data.decode()}")
            continue
        except Exception as e:
            print(f"发生未知错误：{e}")
            continue

def udp_client():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    available_players = []

    print("開始搜索可用玩家...")
    for server in SERVERS:
        print(f"正在檢查服務器 {server}")
        for port in range(UDP_PORT_START, UDP_PORT_END + 1):
            try:
                message = json.dumps({
                    'type': 'check',
                    'name': player_name
                })
                print(f"  嘗試連接 {server}:{port}")
                client_socket.sendto(message.encode(), (server, port))
                client_socket.settimeout(1.0) 
                response, addr = client_socket.recvfrom(BUFFER_SIZE)
                print(f"  收到來自 {addr} 的回應")
                data = json.loads(response.decode())
                if data['type'] == 'available':
                    available_players.append((server, port, data['name']))
                    print(f"  找到可用玩家: {data['name']}")
            except socket.timeout:
                print(f"  {server}:{port} 超時")
            except Exception as e:
                print(f"  錯誤: {e}")

    if not available_players:
        print("沒有找到可用的家。")
        return None, None

    print("可用的玩家:")
    for i, (server, port, name) in enumerate(available_players):
        print(f"{i+1}. {name} ({server}:{port})")

    choice = int(input("選擇一個玩家 (輸入數字): ")) - 1
    server, port, name = available_players[choice]

    message = json.dumps({
        'type': 'invite',
        'name': player_name
    })
    client_socket.sendto(message.encode(), (server, port))

    max_retries = 3
    for attempt in range(max_retries):
        client_socket.settimeout(10)  # 10秒超时
        try:
            response, _ = client_socket.recvfrom(BUFFER_SIZE)
            data = json.loads(response.decode())
            if data['type'] == 'accept':
                print(f"{name} 接受了你的邀请!")
                tcp_port = random.randint(TCP_PORT_START, TCP_PORT_END)
                tcp_info = json.dumps({
                    'type': 'tcp_info',
                    'ip': SERVER_IP,  # 使用 SERVER_IP
                    'port': tcp_port
                })
                client_socket.sendto(tcp_info.encode(), (server, port))
                return SERVER_IP, tcp_port  # 返回 SERVER_IP
            else:
                print(f"{name} 拒绝了你的邀请。")
                return None, None
        except socket.timeout:
            if attempt < max_retries - 1:
                print(f"等待 {name} 响应超时。正在重试... (尝试 {attempt + 1}/{max_retries})")
            else:
                print(f"等待 {name} 响应超时。请稍后再试。")
        except Exception as e:
            print(f"发生错误：{e}")
            break

    return None, None

def get_public_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip

def tcp_server(port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_socket.bind((SERVER_IP, port))
        server_socket.listen(1)
        print(f"TCP服務器正在監聽 {SERVER_IP}:{port}")
        
        server_socket.settimeout(60)  # 設置 60 秒超時
        conn, addr = server_socket.accept()
        print(f"與 {addr} 建立連接")

        play_game(conn, True)
    except socket.timeout:
        print("等待連接超時")
    except Exception as e:
        print(f"TCP 服務器錯誤: {e}")
    finally:
        server_socket.close()

def tcp_client(ip, port):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        ip = ip[0] if isinstance(ip, list) else ip  
        print(f"嘗試連接到 {ip}:{port}")
        client_socket.connect((ip, port))
        print(f"已連接到 {ip}:{port}")

        play_game(client_socket, False)
    except Exception as e:
        print(f"TCP 客戶端錯誤: {e}")
    finally:
        client_socket.close()

def play_game(socket, is_server):
    choices = ['石頭', '剪刀', '布']
    while True:
        if is_server:
            my_choice = input("請選擇 (1: 石頭, 2: 剪刀, 3: 布): ")
            my_choice = choices[int(my_choice) - 1]  
            socket.send(my_choice.encode())
            opponent_choice = socket.recv(BUFFER_SIZE).decode()
        else:
            opponent_choice = socket.recv(BUFFER_SIZE).decode()
            my_choice = input("請選擇 (1: 石頭, 2: 剪刀, 3: 布): ")
            my_choice = choices[int(my_choice) - 1]  
            socket.send(my_choice.encode())

        print(f"你選擇了 {my_choice}，對手選擇了 {opponent_choice}")

        if my_choice == opponent_choice:
            result = "平局!"
        elif (choices.index(my_choice) - choices.index(opponent_choice)) % 3 == 1:
            result = "你輸了!"
        else:
            result = "你贏了!"

        print(result)

        play_again = input("再玩一次? (y/n): ")
        socket.send(play_again.encode())
        opponent_play_again = socket.recv(BUFFER_SIZE).decode()

        if play_again.lower() != 'y' or opponent_play_again.lower() != 'y':
            break

    socket.close()

def main():
    choice = input("選擇模式 (1: 等待邀請, 2: 發送邀請): ")
    if choice == '1':
        ip, port = udp_server()
        if ip and port:
            tcp_client(ip, port)
    elif choice == '2':
        ip, port = udp_client()
        if ip and port:
            tcp_server(port)

if __name__ == "__main__":
    main()
