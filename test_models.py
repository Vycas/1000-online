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


class TestSession(unittest.TestCase):
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
        self.session = Session(player_1=self.player_1, player_2=self.player_2, player_3=self.player_3, dealer=self.player_1)
        self.states = ('waiting', 'ready', 'bettings', 'collect', 'finalBet', 'inGame', 'endGame')

    def test_host(self):
        session = Session()
        session.host(self.user_1)
        self.assertEqual(session.player_1.user, self.user_1)
        self.assertEqual(session.dealer.user, self.user_1)
        self.assertEqual(session.player_2, None)
        self.assertEqual(session.player_3, None)
        self.assertEqual(session.state, 'waiting')
    
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
    
    def test_getPlayerByUser(self):
        self.assertEqual(self.session.getPlayerByUser(self.user_1), self.player_1)
        self.assertEqual(self.session.getPlayerByUser(self.user_2), self.player_2)
        self.assertEqual(self.session.getPlayerByUser(self.user_3), self.player_3)
    
    def test_getNextPlayer(self):
        self.assertEqual(self.session.getNextPlayer(self.player_1), self.session.player_2)
        self.assertEqual(self.session.getNextPlayer(self.player_2), self.session.player_3)
        self.assertEqual(self.session.getNextPlayer(self.player_3), self.session.player_1)
    
    def test_start(self):
        dealer = self.player_1
        nondealer = nextdealer = self.player_2
        self.assertRaises(GameError, self.session.start, nondealer)
        for state in self.states:
            if not state in ('ready', 'endGame'):
                self.session.state = state
                self.assertRaises(GameError, self.session.start, dealer)
        self.session.state = 'ready'
        self.session.start(dealer)
        for p in (self.session.player_1, self.session.player_2, self.session.player_3):
            self.assertEqual(len(p.cards), 7)
            self.assertEqual(len(p.tricks), 0)
            self.assertEqual(len(p.calls), 0)
            self.assertEqual(p.blind, None)
            self.assertEqual(p.passed, False)
            self.assertEqual(p.bet, None)
        self.assertEqual(len(self.session.bank), 3)
        self.assertEqual(self.session.dealer, nextdealer)
        self.assertEqual(self.session.bet, 90)
        self.assertEqual(self.session.state, 'bettings')
        self.assertEqual(self.session.blind, False)
        self.assertEqual(self.session.trump, None)
    
    def 

if __name__ == '__main__':
    unittest.main()
