import socket
import json
import sys

class TicTacToe:
    def __init__(self):
        self.board = [" " for _ in range(9)]
        self.current_player = "X"
        
    def make_move(self, position):
        if self.board[position] == " ":
            self.board[position] = self.current_player
            self.current_player = "O" if self.current_player == "X" else "X"
            return True
        return False
        
    def check_winner(self):
        # Check rows
        for i in range(0, 9, 3):
            if self.board[i] == self.board[i+1] == self.board[i+2] != " ":
                return self.board[i]
        # Check columns
        for i in range(3):
            if self.board[i] == self.board[i+3] == self.board[i+6] != " ":
                return self.board[i]
        # Check diagonals
        if self.board[0] == self.board[4] == self.board[8] != " ":
            return self.board[0]
        if self.board[2] == self.board[4] == self.board[6] != " ":
            return self.board[2]
        # Check tie
        if " " not in self.board:
            return "Tie"
        return None

def run_game(host_mode=True):
    try:
        if host_mode:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.bind(('127.0.0.1', 12346))
            server.listen(1)
            print("Waiting for opponent to connect...")
            client_socket, addr = server.accept()
        else:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect(('127.0.0.1', 12346))

        game = TicTacToe()
        my_symbol = "X" if host_mode else "O"

        while True:
            # Display board
            print("\nCurrent board:")
            for i in range(0, 9, 3):
                print(f"{game.board[i]} | {game.board[i+1]} | {game.board[i+2]}")
                if i < 6:
                    print("---------")

            # My turn
            if game.current_player == my_symbol:
                while True:
                    try:
                        move = int(input("Enter position (0-8): "))
                        if 0 <= move <= 8 and game.make_move(move):
                            break
                        print("Invalid move, please try again")
                    except ValueError:
                        print("Please enter a valid number")
                client_socket.send(str(move).encode())
            # Opponent's turn
            else:
                print("Waiting for opponent's move...")
                move = int(client_socket.recv(1024).decode())
                game.make_move(move)

            # Check game result
            winner = game.check_winner()
            if winner:
                print("\nFinal board:")
                for i in range(0, 9, 3):
                    print(f"{game.board[i]} | {game.board[i+1]} | {game.board[i+2]}")
                if winner == "Tie":
                    print("\nGame is a tie!")
                elif winner == my_symbol:
                    print("\nYou won!")
                else:
                    print("\nOpponent won!")
                break

    except Exception as e:
        print(f"Game error: {e}")
    finally:
        if host_mode:
            server.close()
        client_socket.close()

if __name__ == "__main__":
    mode = input("Choose mode (1: Host, 2: Client): ")
    run_game(mode == "1") 