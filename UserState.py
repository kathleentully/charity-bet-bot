from collections import namedtuple
from math import floor

Deal = namedtuple('Deal', 'price tickets')
#should be ordered high to low, too lazy to enforce
EVENT_PRICES = [
    Deal(price=20, tickets=25),
    Deal(price=10, tickets=11),
    Deal(price=1, tickets=1)
]

class UserState:
    def __init__(self, tickets_available=0,amount_owed=0,bets=[]):
        self.tickets_available = tickets_available
        self.amount_owed = amount_owed
        self.bets = bets

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