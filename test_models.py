import sys
import os

# Change the following line to reflect wherever your
# app engine installation and the mocker library are
APPENGINE_PATH = '/Applications/GoogleAppEngineLauncher.app/Contents/Resources/GoogleAppEngine-default.bundle/Contents/Resources/google_appengine'
#MOCKER_PATH = '../mocker-0.10.1'


# Add app-engine related libraries to your path
paths = [
    APPENGINE_PATH,
    os.path.join(APPENGINE_PATH, 'lib', 'django'),
    os.path.join(APPENGINE_PATH, 'lib', 'webob'),
    os.path.join(APPENGINE_PATH, 'lib', 'yaml', 'lib'),
    #MOCKER_PATH,
]
for path in paths:
  if not os.path.exists(path): 
    raise 'Path does not exist: %s' % path
sys.path = paths + sys.path

import unittest
import time
from google.appengine.api.users import User
from google.appengine.ext import db
from models import Player, Session, GameError
from cards import ThousandCard

import warnings
warnings.filterwarnings("ignore")

from google.appengine.api import apiproxy_stub_map 
from google.appengine.api import datastore_file_stub 
from google.appengine.api import mail_stub 
from google.appengine.api import urlfetch_stub 
from google.appengine.api import user_service_stub 

def prepareEnviroment():
    os.environ['TZ'] = 'UTC' 
    time.tzset()
    os.environ['APPLICATION_ID'] = 'test_app' 
    os.environ['AUTH_DOMAIN'] = 'gmail.com' 
    os.environ['USER_EMAIL'] = 'test@example.com'
    apiproxy_stub_map.apiproxy = apiproxy_stub_map.APIProxyStubMap()
    apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', 
        datastore_file_stub.DatastoreFileStub('test_app', '/dev/null', '/dev/null')) 
    apiproxy_stub_map.apiproxy.RegisterStub('user', user_service_stub.UserServiceStub()) 
    apiproxy_stub_map.apiproxy.RegisterStub('urlfetch', urlfetch_stub.URLFetchServiceStub()) 
    apiproxy_stub_map.apiproxy.RegisterStub('mail', mail_stub.MailServiceStub())

class TestPlayer(unittest.TestCase):
    def setUp(self):
        prepareEnviroment()
        self.user = User(email='tester@google.com')
        self.player = Player(user=self.user)

    def test_goBlind(self):
        self.player.blind = None
        self.player.goBlind()
        self.assertTrue(self.player.blind)
        self.player.blind = True
        self.player.goBlind()
        self.assertTrue(self.player.blind)
        self.player.blind = False
        self.assertRaises(GameError, self.player.goBlind)

    def test_goOpen(self):
        for state in (None, True, False):
            self.player.blind = state
            self.player.goOpen()
            self.assertTrue(not self.player.blind)

    def test_hasPair(self):
        cards = [ThousandCard(x) for x in ('CQ', 'CK', 'DQ')]
        self.player.cards = cards
        deck = ThousandCard.generateDeck()
        for card in deck:
            if str(card) in ('CQ', 'CK', 'DK'):
                self.assertTrue(self.player.hasPair(card))
            else:
                self.assertTrue(not self.player.hasPair(card))

    def test_hasKind(self):
        self.player.cards = [ThousandCard(x) for x in ('CA', 'DA', 'SA')]
        for kind in ('S', 'C', 'D'):
            self.assertTrue(self.player.hasKind(kind))
        self.assertTrue(not self.player.hasKind('H'))

    def test_gamePoints(self):
        self.player.calls = 'D' + 'H'
        self.player.tricks = ThousandCard.generateDeck()
        self.assertEqual(self.player.getGamePoints(), 300)


class TestSessionInitialization(unittest.TestCase):
    def setUp(self):
        prepareEnviroment()
        self.user_1 = User(email='tester1@google.com')
        self.user_2 = User(email='tester2@google.com')
        self.user_3 = User(email='tester3@google.com')

    def test_host(self):
        session = Session()
        session.host(self.user_1)
        self.assertEqual(session.player_1.user, self.user_1)
        self.assertEqual(session.dealer.user, self.user_1)
        self.assertEqual(session.player_2, None)
        self.assertEqual(session.player_3, None)
        self.assertEqual(session.state, 'hosted')
    
    def test_join(self):
        session = Session()
        session.host(self.user_1)
        self.assertEqual(session.join(self.user_2).user, self.user_2)
        self.assertEqual(session.player_1.user, self.user_1)
        self.assertEqual(session.player_2.user, self.user_2)
        self.assertEqual(session.player_3, None)
        self.assertEqual(session.join(self.user_3).user, self.user_3)
        self.assertEqual(session.player_1.user, self.user_1)
        self.assertEqual(session.player_2.user, self.user_2)
        self.assertEqual(session.player_3.user, self.user_3)
        self.assertEqual(session.state, 'ready')
        self.assertRaises(GameError, session.join, User(email='yet@another.com'))
    
    def test_isFull(self):
        session = Session()
        self.assertFalse(session.isFull())
        session.host(self.user_1)
        self.assertFalse(session.isFull())
        session.join(self.user_2)
        self.assertFalse(session.isFull())
        session.join(self.user_3)
        self.assertTrue(session.isFull())


class TestSessionCardDealing(unittest.TestCase):
    def setUp(self):
        prepareEnviroment()
        self.user_1 = User(email='tester1@google.com')
        self.user_2 = User(email='tester2@google.com')
        self.user_3 = User(email='tester3@google.com')
        self.player_1 = Player(user=self.user_1)
        self.player_2 = Player(user=self.user_2)
        self.player_3 = Player(user=self.user_3)
        self.player_1.put()
        self.player_2.put()
        self.player_3.put()
        self.session = Session(player_1=self.player_1, player_2=self.player_2, player_3=self.player_3, dealer=self.player_1, state='ready')
        self.states = ('hosted', 'ready', 'bettings', 'collect', 'finalBet', 'inGame', 'endGame')

    def test_getPlayerByUser(self):
        self.assertEqual(self.session.getPlayerByUser(self.user_1), self.session.player_1)
        self.assertEqual(self.session.getPlayerByUser(self.user_2), self.session.player_2)
        self.assertEqual(self.session.getPlayerByUser(self.user_3), self.session.player_3)

    def test_getNextPlayer(self):
        self.assertEqual(self.session.getNextPlayer(self.session.player_1), self.session.player_2)
        self.assertEqual(self.session.getNextPlayer(self.session.player_2), self.session.player_3)
        self.assertEqual(self.session.getNextPlayer(self.session.player_3), self.session.player_1)

    def test_deal(self):
        dealer = self.session.player_1
        nondealer = nextdealer = self.session.player_2
        turn = self.session.player_2
        self.assertRaises(GameError, self.session.deal, nondealer)
        for state in self.states:
            if not state in ('ready', 'endGame'):
                self.session.state = state
                self.assertRaises(GameError, self.session.deal, dealer)
        self.session.state = 'ready'
        self.session.dealer = dealer
        self.session.deal(dealer)
        for p in (self.session.player_1, self.session.player_2, self.session.player_3):
            self.assertEqual(len(p.cards), 7)
            self.assertEqual(len(p.tricks), 0)
            self.assertEqual(len(p.calls), 0)
            self.assertEqual(p.blind, None)
            self.assertEqual(p.passed, False)
            self.assertEqual(p.bet, None)
        self.assertEqual(len(self.session.bank), 3)
        self.assertEqual(len(self.session.memo), 0)
        self.assertEqual(self.session.turn, turn)
        self.assertEqual(self.session.dealer, nextdealer)
        self.assertEqual(self.session.bet, 90)
        self.assertEqual(self.session.state, 'bettings')
        self.assertEqual(self.session.blind, False)
        self.assertEqual(self.session.trump, None)


class TestSessionBettings(unittest.TestCase):
    def setUp(self):
        prepareEnviroment()
        self.user_1 = User(email='tester1@google.com')
        self.user_2 = User(email='tester2@google.com')
        self.user_3 = User(email='tester3@google.com')
        self.session = Session()
        self.session.host(self.user_1)
        self.session.join(self.user_2)
        self.session.join(self.user_3)
        self.session.deal(self.session.dealer)

    def test_raiseBetPreconditions(self):
        turn = self.session.player_2
        nextturn = nonturn = self.session.player_3
        self.session.state = 'incorrect'
        self.assertRaises(GameError, self.session.raiseBet, turn, 200)
        self.session.state = 'bettings'
        self.assertRaises(GameError, self.session.raiseBet, nonturn, 200)
        self.assertRaises(GameError, self.session.raiseBet, turn, 90)
        self.assertRaises(GameError, self.session.raiseBet, turn, 310)
        self.assertRaises(GameError, self.session.raiseBet, turn, 199)
        self.session.bet = 150
        self.assertRaises(GameError, self.session.raiseBet, turn, 140)
    
    def test_raiseBetPassout(self):
        self.session.raiseBet(self.session.player_2, 160)
        self.assertEqual(self.session.bet, 160)
        self.assertEqual(self.session.player_2.bet, 160)
        self.assertEqual(self.session.turn, self.session.player_3)
        self.session.player_1.passed = True
        self.session.raiseBet(self.session.player_3, 170)
        self.assertEqual(self.session.turn, self.session.player_2)
        self.session.player_3.passed = True
        self.session.raiseBet(self.session.player_2, 180)
        self.assertEqual(self.session.state, 'collect')
        self.assertEqual(self.session.turn, self.session.player_2)
        
    def test_raiseBet300(self):
        self.session.raiseBet(self.session.player_2, 300)
        self.assertEqual(self.session.state, 'collect')
        self.assertEqual(self.session.bet, 300)
        self.assertEqual(self.session.turn, self.session.player_2)
    
    def test_makePassPreconditions(self):
        turn = self.session.player_2
        nextturn = nonturn = self.session.player_3
        self.session.state = 'incorrect'
        self.assertRaises(GameError, self.session.makePass, turn)
        self.session.state = 'bettings'
        self.assertRaises(GameError, self.session.makePass, nonturn)
        turn.passed = True
        self.assertRaises(GameError, self.session.makePass, turn)
        turn.passed = False
        self.session.bet = 90
        self.session.dealer = turn
        self.assertRaises(GameError, self.session.makePass, turn)
        
    def test_makePassScenario1(self):
        #Scenario-1: 100->pass->pass
        self.session.raiseBet(self.session.player_2, 100)
        self.session.makePass(self.session.player_3)
        self.assertTrue(self.session.player_3.passed)
        self.assertEqual(self.session.turn, self.session.player_1)
        self.session.makePass(self.session.player_1)
        self.assertTrue(self.session.player_1.passed)
        self.assertEqual(self.session.state, 'collect')
        self.assertEqual(self.session.turn, self.session.player_2)
        
    def test_makePassScenario2(self):
        #Scenario-2: 100->110->pass->120->pass
        self.session.turn = self.session.player_2
        self.session.player_1.passed = False
        self.session.player_2.passed = False
        self.session.player_3.passed = True
        self.session.bet = self.session.player_1.bet = 120
        self.session.makePass(self.session.player_2)
        self.assertEqual(self.session.state, 'collect')
        self.assertEqual(self.session.turn, self.session.player_1)
    
    def test_isFirstMove(self):
        self.assertTrue(self.session.isFirstMove())
        self.session.raiseBet(self.session.turn, 100)
        self.assertFalse(self.session.isFirstMove())
    
    def test_betsOverPassout(self):
        #Scenario-1: 2 players hit pass
        self.assertFalse(self.session.betsOver())
        self.session.raiseBet(self.session.turn, 100)
        self.assertFalse(self.session.betsOver())
        self.session.makePass(self.session.turn)
        self.assertFalse(self.session.betsOver())
        self.session.makePass(self.session.turn)
        self.assertTrue(self.session.betsOver())
    
    def test_betsOver300(self):
        #Scenario-2: 300 is reached
        self.assertFalse(self.session.betsOver())
        self.session.raiseBet(self.session.turn, 300)
        self.assertTrue(self.session.betsOver())
    
    def test_betsWinnerPassout(self):
        self.session.raiseBet(self.session.player_2, 200)
        self.session.makePass(self.session.player_3)
        self.session.makePass(self.session.player_1)
        self.assertEqual(self.session.betsWinner(), self.session.player_2)
    
    def test_betsWinner300(self):
        self.session.raiseBet(self.session.player_2, 300)
        self.assertEqual(self.session.betsWinner(), self.session.player_2)


class TestSessionFinalBet(unittest.TestCase):
    def setUp(self):
        prepareEnviroment()
        self.user_1 = User(email='tester1@google.com')
        self.user_2 = User(email='tester2@google.com')
        self.user_3 = User(email='tester3@google.com')
        self.session = Session()
        self.session.host(self.user_1)
        self.session.join(self.user_2)
        self.session.join(self.user_3)
        self.session.deal(self.session.dealer)
        self.session.raiseBet(self.session.turn, 200)
        self.session.makePass(self.session.turn)
        self.session.makePass(self.session.turn)
    
    def test_collectBank(self):
        turn = self.session.player_2
        nonturn = self.session.player_3
        self.session.state = 'incorrect'
        self.assertRaises(GameError, self.session.collectBank, turn)
        self.session.state = 'collect'
        self.assertRaises(GameError, self.session.collectBank, nonturn)
        self.session.collectBank(self.session.turn)
        self.assertEqual(self.session.state, 'finalBet')
        self.assertEqual(len(self.session.turn.cards), 10)
        self.assertEqual(len(self.session.bank), 0)
        self.assertEqual(len(self.session.memo), 3)

    def test_discardCard(self):
        turn = self.session.turn
        nonturn = self.session.getNextPlayer(turn)
        self.session.collectBank(turn)
        mycard = turn.cards[0]
        nonmycard = nonturn.cards[0]
        self.session.state = 'incorrect'
        self.assertRaises(GameError, self.session.discardCard, turn, mycard)
        self.session.state = 'finalBet'
        self.assertRaises(GameError, self.session.discardCard, nonturn, mycard)
        self.assertRaises(GameError, self.session.discardCard, turn, nonmycard)
        self.session.discardCard(turn, mycard)
        self.assertTrue(mycard in self.session.bank)
        self.assertFalse(mycard in turn.cards)
        self.session.discardCard(turn, turn.cards[0])
        self.session.discardCard(turn, turn.cards[0])
        self.assertRaises(GameError, self.session.discardCard, turn, turn.cards[0])

    def test_retrieveCard(self):
        turn = self.session.turn
        nonturn = self.session.getNextPlayer(turn)
        self.session.collectBank(turn)
        self.session.discardCard(turn, turn.cards[0])
        card = self.session.bank[0]
        self.session.state = 'incorrect'
        self.assertRaises(GameError, self.session.retrieveCard, turn, card)
        self.session.state = 'finalBet'
        self.assertRaises(GameError, self.session.retrieveCard, nonturn, card)
        self.session.retrieveCard(turn, card)
        self.assertTrue(card in turn.cards)
        self.assertFalse(card in self.session.bank)
        self.assertRaises(GameError, self.session.retrieveCard, turn, card)

    def test_takePlusPreconditions(self):
        turn = self.session.turn
        nonturn = self.session.getNextPlayer(turn)
        self.session.state = 'incorrect'
        self.assertRaises(GameError, self.session.takePlus, turn)
        self.session.state = 'finalBet'
        self.assertRaises(GameError, self.session.takePlus, nonturn)
        turn.plus = True
        self.assertRaises(GameError, self.session.takePlus, turn)

    def test_takePlusCommon(self):
        player = self.session.turn
        dealer = self.session.dealer
        player.points = 0
        self.session.state = 'finalBet'
        self.session.takePlus(player)
        self.assertTrue(player.plus)
        self.assertEqual(self.session.state, 'endGame')
        newdealer = self.session.getNextPlayer(self.session.getNextPlayer(dealer))
        self.assertEqual(self.session.dealer, newdealer)
        self.assertEqual(self.session.turn, newdealer)
        self.assertEqual(player.points, 0)

    def test_takePlusOpen(self):
        player = self.session.turn
        opponent1 = self.session.getNextPlayer(player)
        opponent2 = self.session.getNextPlayer(opponent1)
        opponent1.points = 100
        opponent2.points = 100
        self.session.state = 'finalBet'
        self.session.takePlus(player)
        self.assertEqual(opponent1.points, 160)
        self.assertEqual(opponent2.points, 160)
        self.assertEqual(opponent1.bet, 60)
        self.assertEqual(opponent2.bet, 60)
    
    def test_takePlusBlind(self):
        player = self.session.turn
        opponent1 = self.session.getNextPlayer(player)
        opponent2 = self.session.getNextPlayer(opponent1)
        opponent1.points = 100
        opponent2.points = 100
        self.session.state = 'finalBet'
        self.session.blind = True
        self.session.takePlus(player)
        self.assertEqual(opponent1.points, 220)
        self.assertEqual(opponent2.points, 220)
        self.assertEqual(opponent1.bet, 120)
        self.assertEqual(opponent2.bet, 120)
    
    def test_takePlusOver880(self):
        player = self.session.turn
        opponent1 = self.session.getNextPlayer(player)
        opponent2 = self.session.getNextPlayer(opponent1)
        opponent1.points = 880
        opponent2.points = 100
        self.session.state = 'finalBet'
        self.session.takePlus(player)
        self.assertEqual(opponent1.points, 880)
        self.assertEqual(opponent2.points, 160)
        self.assertEqual(opponent1.bet, 0)
        self.assertEqual(opponent2.bet, 60)

    def test_startPreconditions(self):
        turn = self.session.turn
        nonturn = self.session.getNextPlayer(turn)
        self.session.collectBank(turn)
        self.session.bet = 150
        for i in range(3):
            self.session.discardCard(turn, turn.cards[0])
        self.session.state = 'incorrect'
        self.assertRaises(GameError, self.session.start, turn, 200)
        self.session.state = 'finalBet'
        self.assertRaises(GameError, self.session.start, nonturn, 200)
        self.assertRaises(GameError, self.session.start, turn, 90)
        self.assertRaises(GameError, self.session.start, turn, 310)
        self.assertRaises(GameError, self.session.start, turn, 140)
        self.assertRaises(GameError, self.session.start, turn, 151)
        self.session.retrieveCard(turn, self.session.bank[0])
        self.assertRaises(GameError, self.session.start, turn, 160)
        self.session.discardCard(turn, turn.cards[0])
        self.session.bet = 120
        self.session.blind = True
        self.assertRaises(GameError, self.session.start, turn, 130)
        
    def test_startOpen(self):
        turn = self.session.turn
        self.session.collectBank(turn)
        self.session.bet = 150
        for i in range(3):
            self.session.discardCard(turn, turn.cards[0])
        self.session.start(turn, 160)
        self.assertEqual(self.session.turn, turn)
        self.assertEqual(self.session.bet, 160)
        self.assertEqual(self.session.state, 'inGame')
        self.assertEqual(len(self.session.bank), 0)
        self.assertEqual(len(self.session.turn.tricks), 3)
    
    def test_startBlind(self):
        turn = self.session.turn
        self.session.collectBank(turn)
        self.session.bet = 120
        self.session.blind = True
        for i in range(3):
            self.session.discardCard(turn, turn.cards[0])
        self.session.start(turn, 120)
        self.assertEqual(self.session.bet, 120)
        self.assertEqual(self.session.blind, True)
    
    def test_startBlindOverDouble(self):
        turn = self.session.turn
        self.session.collectBank(turn)
        self.session.bet = 120
        self.session.blind = True
        for i in range(3):
            self.session.discardCard(turn, turn.cards[0])
        self.session.start(turn, 250)
        self.assertEqual(self.session.bet, 250)
        self.assertEqual(self.session.blind, False)


class TestSessionGameplay(unittest.TestCase):
    def setUp(self):
        prepareEnviroment()
        self.user_1 = User(email='tester1@google.com')
        self.user_2 = User(email='tester2@google.com')
        self.user_3 = User(email='tester3@google.com')
        self.session = Session()
        self.session.host(self.user_1)
        self.session.join(self.user_2)
        self.session.join(self.user_3)
        self.session.dealer = self.session.player_1
        self.session.turn = self.session.player_1
        self.session.player_1.points = 0
        self.session.player_2.points = 0
        self.session.player_3.points = 0
        self.session.player_1.bet = 130
        self.session.player_2.bet = None
        self.session.player_3.bet = None
        self.session.player_1.passed = False
        self.session.player_2.passed = True
        self.session.player_3.passed = True
        self.session.player_1.calls = ''
        self.session.player_2.calls = ''
        self.session.player_3.calls = ''
        self.session.player_1.cards = [ThousandCard(x) for x in ('SA', 'S10', 'SK', 'SQ', 'D9', 'DJ', 'H10')]
        self.session.player_2.cards = [ThousandCard(x) for x in ('SJ', 'S9', 'CA', 'CK', 'CQ', 'CJ', 'C9')]
        self.session.player_3.cards = [ThousandCard(x) for x in ('C10', 'HA', 'HK', 'HJ', 'H9', 'DA', 'D10')]
        self.session.player_1.tricks = [ThousandCard(x) for x in ('DK', 'DQ', 'HQ')]
        self.session.bet = 130
        self.session.blind = False
        self.session.memo = [ThousandCard(x) for x in ('SA', 'S10', 'DJ')]
        self.session.bank = []
        self.session.trump = None
        self.session.state = 'inGame'
    
    def test_putCardPreconditions(self):
        turn = self.session.turn
        nonturn = self.session.getNextPlayer(turn)
        mycard = turn.cards[0]
        nonmycard = nonturn.cards[0]
        self.session.state = 'incorrect'
        self.assertRaises(GameError, self.session.putCard, turn, mycard)
        self.session.state = 'inGame'
        self.assertRaises(GameError, self.session.putCard, nonturn, mycard)
        self.assertRaises(GameError, self.session.putCard, turn, nonmycard)
    
    def test_putFirstCard(self):
        turn = self.session.turn
        nextturn = self.session.getNextPlayer(turn)
        card = turn.cards[0]
        self.session.putCard(turn, card)
        self.assertTrue(not card in turn.cards)
        self.assertTrue(card in turn.thrown)
        self.assertTrue(card in self.session.bank)
        self.assertEqual(self.session.turn, nextturn)
    
    def test_putOtherCard(self):
        self.session.putCard(self.session.player_1, ThousandCard('SA'))
        self.assertRaises(GameError, self.session.putCard, self.session.player_2, ThousandCard('C9'))
        card = ThousandCard('S9')
        self.session.putCard(self.session.player_2, card)
        self.assertFalse(card in self.session.player_2.cards)
        self.assertTrue(card in self.session.player_2.thrown)
        self.assertTrue(card in self.session.bank)
        self.assertEqual(self.session.turn, self.session.player_3)
    
    def test_putFinalCard(self):
        cards = [ThousandCard('SA'), ThousandCard('S9'), ThousandCard('HA')]
        self.session.putCard(self.session.player_1, cards[0])
        self.session.putCard(self.session.player_2, cards[1])
        self.session.putCard(self.session.player_3, cards[2])
        self.assertEqual(self.session.turn, self.session.player_1)
        for c in cards:
            self.assertTrue(c in self.session.player_1.tricks)
            self.assertFalse(c in self.session.bank)
        cards = [ThousandCard('DJ'), ThousandCard('SJ'), ThousandCard('D10')]
        self.session.putCard(self.session.player_1, cards[0])
        self.session.putCard(self.session.player_2, cards[1])
        self.session.putCard(self.session.player_3, cards[2])
        self.assertEqual(self.session.turn, self.session.player_3)
        for c in cards:
            self.assertTrue(c in self.session.player_3.tricks)
            self.assertFalse(c in self.session.bank)
    
    def test_putFinalCardWithTrumps(self):
        cards = [ThousandCard('SA'), ThousandCard('S9'), ThousandCard('H9')]
        self.session.trump = 'H'
        self.session.putCard(self.session.player_1, cards[0])
        self.session.putCard(self.session.player_2, cards[1])
        self.session.putCard(self.session.player_3, cards[2])
        self.assertEqual(self.session.turn, self.session.player_3)
        for c in cards:
            self.assertTrue(c in self.session.player_3.tricks)
            self.assertFalse(c in self.session.bank)
    
    def test_pairCall(self):
        self.session.putCard(self.session.player_1, ThousandCard('SA'))
        self.session.putCard(self.session.player_2, ThousandCard('S9'))
        self.session.putCard(self.session.player_3, ThousandCard('HK'))
        self.assertTrue(self.session.trump is None)
        self.assertEqual(self.session.player_3.calls, '')
        self.session.turn = self.session.player_3
        self.session.putCard(self.session.player_3, ThousandCard('C10'))
        self.session.putCard(self.session.player_1, ThousandCard('S10'))
        self.session.putCard(self.session.player_2, ThousandCard('CQ'))
        self.assertTrue(self.session.trump is None)
        self.assertEqual(self.session.player_2.calls, '')
        self.session.turn = self.session.player_1
        self.session.putCard(self.session.player_1, ThousandCard('SQ'))
        self.assertEqual(self.session.trump, 'S')
        self.assertTrue('S' in self.session.player_1.calls)

    def processGame(self):
        self.session.putCard(self.session.player_1, ThousandCard('SA'))
        self.session.putCard(self.session.player_2, ThousandCard('S9'))
        self.session.putCard(self.session.player_3, ThousandCard('HA'))
        self.session.putCard(self.session.player_1, ThousandCard('SQ'))
        self.session.putCard(self.session.player_2, ThousandCard('SJ'))
        self.session.putCard(self.session.player_3, ThousandCard('H9'))
        self.session.putCard(self.session.player_1, ThousandCard('DJ'))
        self.session.putCard(self.session.player_2, ThousandCard('C9'))
        self.session.putCard(self.session.player_3, ThousandCard('D10'))
        self.session.putCard(self.session.player_3, ThousandCard('DA'))
        self.session.putCard(self.session.player_1, ThousandCard('D9'))
        self.session.putCard(self.session.player_2, ThousandCard('CJ'))
        self.session.putCard(self.session.player_3, ThousandCard('C10'))
        self.session.putCard(self.session.player_1, ThousandCard('SK'))
        self.session.putCard(self.session.player_2, ThousandCard('CA'))
        self.session.putCard(self.session.player_1, ThousandCard('H10'))
        self.session.putCard(self.session.player_2, ThousandCard('CQ'))
        self.session.putCard(self.session.player_3, ThousandCard('HJ'))
        self.session.putCard(self.session.player_1, ThousandCard('S10'))
        self.session.putCard(self.session.player_2, ThousandCard('CK'))

    def test_gameFinishSuccess(self):
        self.processGame()
        self.session.putCard(self.session.player_3, ThousandCard('HK'))
        self.assertEqual(self.session.state, 'endGame')
        self.assertEqual(self.session.turn, self.session.dealer)
        self.assertEqual(self.session.player_1.points, 130)
        self.assertEqual(self.session.player_2.points, 0)
        self.assertEqual(self.session.player_3.points, 30)
    
    def test_gameFinishFail(self):
        self.processGame()
        self.session.bet = 150
        self.session.putCard(self.session.player_3, ThousandCard('HK'))
        self.assertEqual(self.session.state, 'endGame')
        self.assertEqual(self.session.turn, self.session.dealer)
        self.assertEqual(self.session.player_1.points, -150)
        self.assertEqual(self.session.player_2.points, 0)
        self.assertEqual(self.session.player_3.points, 30)
    
    def test_gameFinishBlindSuccess(self):
        self.processGame()
        self.session.blind = True
        self.session.putCard(self.session.player_3, ThousandCard('HK'))
        self.assertEqual(self.session.state, 'endGame')
        self.assertEqual(self.session.turn, self.session.dealer)
        self.assertEqual(self.session.player_1.points, 260)
        self.assertEqual(self.session.player_2.points, 0)
        self.assertEqual(self.session.player_3.points, 50)

    def test_gameFinishBlindFail(self):
        self.processGame()
        self.session.bet = 150
        self.session.blind = True
        self.session.putCard(self.session.player_3, ThousandCard('HK'))
        self.assertEqual(self.session.state, 'endGame')
        self.assertEqual(self.session.turn, self.session.dealer)
        self.assertEqual(self.session.player_1.points, -300)
        self.assertEqual(self.session.player_2.points, 0)
        self.assertEqual(self.session.player_3.points, 50)
    
    def test_over880(self):
        self.processGame()
        self.session.player_3.points = 880
        self.session.putCard(self.session.player_3, ThousandCard('HK'))
        self.assertEqual(self.session.state, 'endGame')
        self.assertEqual(self.session.turn, self.session.dealer)
        self.assertEqual(self.session.player_1.points, 130)
        self.assertEqual(self.session.player_2.points, 0)
        self.assertEqual(self.session.player_3.points, 880)
    
    def test_sessionFinish(self):
        self.processGame()
        self.session.player_1.points = 870
        self.session.putCard(self.session.player_3, ThousandCard('HK'))
        self.assertEqual(self.session.state, 'finish')
        self.assertEqual(self.session.turn, self.session.dealer)
        self.assertEqual(self.session.player_1.points, 1000)
        self.assertEqual(self.session.player_2.points, 0)
        self.assertEqual(self.session.player_3.points, 30)

if __name__ == '__main__':
    unittest.main()
