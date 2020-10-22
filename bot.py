from collections import namedtuple
from dotenv import load_dotenv
import discord
from discord.ext.commands import Bot
from math import floor
from os import getenv
from random import choice

load_dotenv()

ADMIN_USERS = [int(x) for x in getenv("ADMIN_USERS").split(",")]
COMMAND_PREFIX = '!!'
game_state = {}
Deal = namedtuple('Deal', 'price tickets')
#should be ordered high to low, too lazy to enforce
EVENT_PRICES = [
    Deal(price=20, tickets=25),
    Deal(price=10, tickets=11),
    Deal(price=1, tickets=1)
]
log_channel = None
bot = Bot(command_prefix=COMMAND_PREFIX)


class UserState:
    def __init__(self):
        self.tickets_available = 0
        self.amount_owed = 0

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

def admin_func(func):
    async def wrapper(context, *args):
        if context.message.author.id not in ADMIN_USERS:
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
            await log(f'{context.prefix}{context.command} {args} from {context.message.author} FAILED:\n{e.message}')
    return wrapper

async def send_user_game_state(user):
    await user.send(f'You are registered with {game_state[user].tickets_available} tickets available and you owe ${game_state[user].amount_owed}')


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
        charge_amt = charge_amt.strip().lstrip('$')
        charge_amt = int(charge_amt)
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

@bot.command(name='draw', help='')
@admin_func
@log_function_call
async def draw(context, *args):
    all_entries = []
    for user, state in game_state.items():
        all_entries += [user] * state.tickets_available
        await log(f'{user}: {state.tickets_available}')
    await log(f'Entries in drawing: {", ".join(all_entries)}')

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

bot.run(getenv("TOKEN"))