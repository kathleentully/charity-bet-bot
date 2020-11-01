from collections import namedtuple
from dotenv import load_dotenv
import discord
from discord.ext.commands import Bot
from math import floor
from os import getenv
from random import choice
import traceback 

load_dotenv()

ADMIN_USERS = [int(x) for x in getenv("ADMIN_USERS").split(",")]
COMMAND_PREFIX = '!'
game_state = {}
Deal = namedtuple('Deal', 'price tickets')
#should be ordered high to low, too lazy to enforce
EVENT_PRICES = [
    Deal(price=20, tickets=25),
    Deal(price=10, tickets=11),
    Deal(price=1, tickets=1)
]
open_bets = {}
bet_id_cursor = 0
used_bet_ids = set()
bet_id_semaphore = True # green light
log_channel = None
bot = Bot(command_prefix=COMMAND_PREFIX)


class UserState:
    def __init__(self):
        self.tickets_available = 0
        self.amount_owed = 0
        self.bets = []

    def __str__(self):
        return f'Tickets available: {self.tickets_available}, Amount owed: ${self.amount_owed}'

    def buyin(self, money_amount):
        charge = 0
        tickets = 0
        for deal in EVENT_PRICES:
            number_of_sets = floor(money_amount / deal.price)
            charge += number_of_sets * deal.price
            money_amount -= number_of_sets * deal.price
            tickets += number_of_sets * deal.tickets

        self.amount_owed += charge
        self.tickets_available += tickets


async def log(msg):
    if log_channel:
        await log_channel.send(f'LOG: {msg}')
    else:
        print(msg)


def get_new_bet_id():
    global bet_id_semaphore, bet_id_cursor
    while not bet_id_semaphore:
        continue
    bet_id_semaphore = False

    new_bet_id = bet_id_cursor
    while new_bet_id in used_bet_ids:
        bet_id_cursor += 1
        new_bet_id = bet_id_cursor
    used_bet_ids.add(new_bet_id)

    bet_id_semaphore = True
    return new_bet_id


def is_admin(user):
    return user.id in ADMIN_USERS


def admin_func(func):
    async def wrapper(context, *args):
        if not is_admin(context.message.author):
            await log(f'{context.message.author} attempted {context.prefix}{context.command}')
            await context.message.author.send(f'You are not an admin so you cannot execute {context.prefix}{context.command}')
            return
        await func(context, *args)
    return wrapper


def log_function_call(func):
    async def wrapper(context, *args):
        await log(f'Received {context.prefix}{context.command} {args} from {context.message.author}')
        try:
            await func(context, *args)
        except Exception as e:
            traceback.print_exc() 
            await log(f'{context.prefix}{context.command} {args} from {context.message.author} FAILED:\n{e}\nStack trace logged')
    return wrapper


async def send_user_game_state(user):
    await user.send(f'You are registered with {game_state[user].tickets_available} tickets available and you owe ${game_state[user].amount_owed}')
    if game_state[user].bets:
        bet_string = ''
        for bet_id in game_state[user].bets:
            bet_string += f'\n  - Bet {bet_id}: Pool of {open_bets[bet_id]["amount"]} tickets with {", ".join([participant.display_name for participant in open_bets[bet_id]["participants"]])} participating'
        await user.send(f'You have {len(game_state[user].bets)} open bet{"s" if len(game_state[user].bets) != 1 else ""}:{bet_string}')


@bot.event
async def on_ready():
    global log_channel
    log_channel = bot.get_channel(int(getenv("LOG_CHANNEL")))
    await log(f'Bot connected as {bot.user}')



@bot.command(name='register', help='')
@log_function_call
async def register(context):
    global game_state
    game_state.setdefault(context.message.author, UserState())
    await log(f'{context.message.author} registered: {game_state[context.message.author]}')
    await context.message.author.send(f'You are registered with {game_state[context.message.author].tickets_available} tickets available')
    await context.message.author.send(f'Tickets prices are {", ".join([f"${x.price} for {x.tickets} tickets" for x in EVENT_PRICES])}')
    await context.message.author.send(f'Use the following command to buyin: {context.prefix}buyin <amount of money>')


@bot.command(name='status', help='')
@log_function_call
async def status(context):
    global game_state
    if context.message.author not in game_state:
        await context.message.author.send(f'You are not registered. Use {context.prefix}register to register')
    await send_user_game_state(context.message.author)


@bot.command(name='buyin', help='')
@log_function_call
async def buyin(context, charge_amt: int):
    global game_state
    if context.message.author not in game_state:    
        game_state.setdefault(context.message.author, UserState())
        await log(f'{context.message.author} registered: {game_state[context.message.author]}')
    try:
        charge_amt = int(charge_amt.strip().lstrip('$'))
    except:
        await log(f'Failed to convert first argument [{charge_amt}] to an int')
        await context.message.author.send(f'Invalid input value. Please input a whole number value.')
        return
    
    await log(f'{context.message.author}: amount owed: ${game_state[context.message.author].amount_owed}, tickets: {game_state[context.message.author].tickets_available} | buying in ${charge_amt}')
    game_state[context.message.author].buyin(charge_amt)

    await log(f'{context.message.author}: amount owed: ${game_state[context.message.author].amount_owed}, tickets: {game_state[context.message.author].tickets_available} | bought in ${charge_amt}')
    await send_user_game_state(context.message.author)


@bot.command(name='drawprep', help='')
@admin_func
@log_function_call
async def drawprep(context, *args):
    for user in game_state.keys():
        await user.send('The drawing is about to happen! Get in your final bets and buyins!')
        await send_user_game_state(user)
        ### send open bets
    standings()


@bot.command(name='draw', help='')
@admin_func
@log_function_call
async def draw(context, *args):
    all_entries = []
    for user, state in game_state.items():
        all_entries += [user] * state.tickets_available
        await log(f'{user}: {state.tickets_available}')
    await log(f'Entries in drawing: {", ".join([entry.display_name for entry in all_entries])}')

    if not len(all_entries):
        await log('No entries, no winner')
        return

    winner = choice(all_entries)
    await log(f'Winner: {winner}')
    await context.send(f'And the winner is {winner.mention}!!')


@bot.command(name='settleall', help='')
@admin_func
@log_function_call
async def settleall(context, *args):
    total = 0
    for user, state in game_state.items():
        await log(f'{user}: ${state.amount_owed}')
        total += state.amount_owed
    await log(f'total: ${total}')


@bot.command(name='resetuser', help='')
@admin_func
@log_function_call
async def resetuser(context, *args):
    for mention in context.message.mentions:
        game_state[mention] = UserState()
        await send_user_game_state(mention)


@bot.command(name='bet', help='')
@log_function_call
async def bet(context, charge_amt: int, *args):
    try:
        charge_amt = int(charge_amt.strip())
    except:
        await log(f'Failed to convert first argument [{charge_amt}] to an int')
        await context.message.author.send(f'Invalid input value. Please input a whole number value.')
        return


    if context.message.author not in context.message.mentions and not is_admin(context.message.author):
        await log(f'Failed to create bet because {context.message.author} is not in the betting group and not an admin')
        await context.message.author.send(f'You do not have permissions to create bets for other people. If you meant to enter a bet including yourself, be sure to mention yourself.')
        return


    should_cancel = False
    for mention in context.message.mentions:
        if mention not in game_state:
            should_cancel = True
            await log(f'Failed to create bet because {mention} is not registered.')
            await mention.send(f'You are not registered and therefore do not have enough tickets available to place this bet. Use {context.prefix}buyin <amount of money> to add more tickets and try again.')
        elif game_state[mention].tickets_available < charge_amt:
            should_cancel = True
            await log(f'Failed to create bet because {mention} only has {game_state[mention].tickets_available} tickets available.')
            await mention.send(f'You do not have enough tickets available to place this bet. Use {context.prefix}buyin <amount of money> to add more tickets and try again.')
    if should_cancel:
        await log(f'Bet canceled')
        return


    bet_id = get_new_bet_id()
    bet = {
        "amount": 0,
        "participants": []
    }

    for mention in context.message.mentions:
        bet["amount"] += charge_amt
        bet["participants"].append(mention)
        game_state[mention].bets.append(bet_id)
        game_state[mention].tickets_available -= charge_amt
    
    open_bets[bet_id] = bet

    for mention in context.message.mentions:
        await mention.send(f'You have bet {charge_amt} tickets on bet id {bet_id}. When the game is over, any participant can finalize the win by typing {context.prefix}won {bet_id} <mention winning user(s) on one line>\nIf the amount cannot be split evenly, the remainder will be shared in the order the users are mentioned.')
    await context.send(f'Bet {bet_id} created for {bet["amount"]} total with users {", ".join([x.display_name for x in context.message.mentions])}. GLHF!')
    await log(f'Bet {bet_id} created for {charge_amt} each, {bet["amount"]} total with users {", ".join([x.display_name for x in context.message.mentions])}')


@bot.command(name='won', help='')
@log_function_call
async def won(context, bet_id: int, *args):
    try:
        bet_id = int(bet_id.strip())
    except:
        await log(f'Failed to convert first argument [{bet_id}] to an int')
        await context.message.author.send(f'Invalid input value. Please input a whole number value.')
        return

    if bet_id not in open_bets:
        if bet_id in used_bet_ids:
            await log(f'Bet id {bet_id} has already been closed')
            await context.send(f'Bet id {bet_id} has already been closed')
        else:
            await log(f'Bet id {bet_id} is not valid')
            await context.send(f'Bet id {bet_id} is not valid')
        return

    bet = open_bets[bet_id]

    if context.message.author not in bet["participants"] or not is_admin(context.message.author):
        await log(f'Failed to close bet because {context.message.author} is not in the betting group {", ".join([p.display_name for b in bet["participants"]])} and not an admin')
        await context.send(f'{context.message.author.mention} You do not have permissions to close bets for other people.')
        return

    for mention in context.message.mentions:
        if mention not in bet["participants"]:
            await log(f'Failed to close bet because {mention} is not in the betting group {", ".join([p.display_name for b in bet["participants"]])}')
            await context.send(f'{mention} cannot win a bet in which they were not participants.')
            return


    amount_per_winner = floor(bet["amount"] / len(context.message.mentions))
    remainder = bet["amount"] - len(context.message.mentions) * amount_per_winner

    for mention in context.message.mentions:
        if remainder > 0:
            remainder -= 1
            amount_awarded = amount_per_winner + 1
        else:
            amount_awarded = amount_per_winner
        
        game_state[mention].tickets_available += amount_awarded

        await log(f'{amount_awarded} tickets awarded to {mention}. They now have {game_state[mention].tickets_available} tickets available.')
        await mention.send(f'You have been awarded {amount_awarded} tickets. You now have {game_state[mention].tickets_available} tickets available. Congrats!')
    
    for participant in bet["participants"]:
        game_state[participant].bets.remove(bet_id)

    del open_bets[bet_id]

    await context.send(f'Bet {bet_id} completed with the winners: {", ".join([x.display_name for x in context.message.mentions])}. Congrats!')
    await log(f'Bet {bet_id} completed with winners {", ".join([x.display_name for x in context.message.mentions])}')


@bot.command(name='standings', help='')
@log_function_call
async def standings(context, *args):
    FORMAT_STRING = '\n{rank:4d} {name} {tickets} ticket{ticket_s}'
    current_standings = 'Current standings:'
    count = 1

    for user, user_state in sorted(game_state.items(), key=lambda item: item[1].tickets_available, reverse=True):
        current_standings += FORMAT_STRING.format(rank=count,
                                                  name=user.mention,
                                                  tickets=user_state.tickets_available,
                                                  ticket_s='' if user_state.tickets_available == 1 else 's')
        count += 1

    await context.send(current_standings)
    await log(f'Standings output')


bot.run(getenv("TOKEN"))