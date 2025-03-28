import socket
import json
import random
import sys

class RockPaperScissors:
    def __init__(self):
        self.choices = ['Rock', 'Scissors', 'Paper']
        self.scores = {'host': 0, 'client': 0}
        
    def determine_winner(self, choice1, choice2):
        if choice1 == choice2:
            return "Tie"
        elif ((choice1 == 'Rock' and choice2 == 'Scissors') or
              (choice1 == 'Scissors' and choice2 == 'Paper') or
              (choice1 == 'Paper' and choice2 == 'Rock')):
            return "Player1Wins"
        else:
            return "Player2Wins"

def run_game(host_mode=True):
    try:
        if host_mode:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.bind(('127.0.0.1', 12347))
            server.listen(1)
            print("Waiting for opponent to connect...")
            client_socket, addr = server.accept()
        else:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect(('127.0.0.1', 12347))

        game = RockPaperScissors()
        rounds = 5

        for round in range(rounds):
            print(f"\n=== Round {round + 1} ===")
            
            # Choose a move
            while True:
                choice = input("Choose (1:Rock 2:Scissors 3:Paper): ")
                if choice in ['1', '2', '3']:
                    my_choice = game.choices[int(choice)-1]
                    break
                print("Invalid choice, please try again")

            # Send the choice
            client_socket.send(my_choice.encode())
            
            # Receive the opponent's choice
            opponent_choice = client_socket.recv(1024).decode()
            
            # Display the result
            print(f"\nYour choice: {my_choice}")
            print(f"Opponent's choice: {opponent_choice}")
            
            result = game.determine_winner(
                my_choice if host_mode else opponent_choice,
                opponent_choice if host_mode else my_choice
            )
            
            if result == "Player1Wins":
                if host_mode:
                    game.scores['host'] += 1
                    print("You won this round!")
                else:
                    game.scores['client'] += 1
                    print("Opponent won this round!")
            elif result == "Player2Wins":
                if host_mode:
                    game.scores['client'] += 1
                    print("Opponent won this round!")
                else:
                    game.scores['host'] += 1
                    print("You won this round!")
            else:
                print("This round is a tie!")
                
            print(f"Current score - You: {game.scores['host' if host_mode else 'client']}, "
                  f"Opponent: {game.scores['client' if host_mode else 'host']}")

        # Display the final result
        print("\n=== Game Over ===")
        my_score = game.scores['host' if host_mode else 'client']
        opponent_score = game.scores['client' if host_mode else 'host']
        
        if my_score > opponent_score:
            print("Congratulations! You won!")
        elif my_score < opponent_score:
            print("Opponent won!")
        else:
            print("Game is a tie!")
            
    except Exception as e:
        print(f"Game error: {e}")
    finally:
        if host_mode:
            server.close()
        client_socket.close()

if __name__ == "__main__":
    mode = input("Choose mode (1: Host, 2: Client): ")
    run_game(mode == "1") 
