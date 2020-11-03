from datetime import datetime
import json
import os

from UserState import UserState

FILE_SUFFIX = '-game_state.json'

def save_game_state(game_state, open_bets, used_bet_ids):
    with open(datetime.now().strftime('%y%m%d%H%M%S') + FILE_SUFFIX, 'w') as save_file:
        json.dump({
            "game_state": {user.id: user_state.__dict__ for user, user_state in game_state.items()},
            "open_bets": {bet_id: {
                "amount": bet_info["amount"],
                "participants": [participant.id for participant in bet_info["participants"]]
            } for bet_id, bet_info in open_bets.items()},
            "used_bet_ids": list(used_bet_ids)
        }, save_file)


async def load_game_state(bot, file_name=None):
    if not file_name:
        files = sorted([candidate_file for candidate_file in os.listdir() if candidate_file.endswith(FILE_SUFFIX)], reverse=True)
        if not files:
            return {}, {}, set()
        file_name = files[0]
        
    with open(file_name, 'r') as load_file:
        full_game_state = json.load(load_file)
        return ({await bot.fetch_user(int(user_id)): UserState(tickets_available=user_state["tickets_available"],
                                                      amount_owed=user_state["amount_owed"],
                                                      bets=user_state["bets"]
                                                     ) for user_id, user_state in full_game_state["game_state"].items()},
                {await bet_id: {
                    "amount": bet_info["amount"],
                    "participants": [await bot.fetch_user(participant_id) for participant_id in bet_info["participants"]]
                } for bet_id, bet_info in full_game_state["open_bets"].items()},
                set(full_game_state["used_bet_ids"]))