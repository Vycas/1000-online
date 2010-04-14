from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import users
from google.appengine.ext import db
from models import Session, Player, History, GameError
from cards import ThousandCard
from pygooglechart import *
import models
import simplejson as json
import os
import time
import datetime

def render(name, options):
    path = os.path.join(os.path.dirname(__file__), 'templates', name)
    return template.render(path, options)

def options(current={}):
    user = users.get_current_user()
    opts = {'user': user}
    if user:
        opts.update({'username': user.nickname()})
    opts.update(current)
    return opts

def getSession(handler):
    try:
        session = Session.get_by_id(int(handler.request.get('id')))
        if not session:
            raise GameError('This session does not exist.')
        return session
    except ValueError:
        raise GameError('Bad session identifier.')

class Welcome(webapp.RequestHandler):
    def get(self):
        self.response.out.write(render('welcome.html', options()))

class About(webapp.RequestHandler):
    def get(self):
        self.response.out.write(render('about.html', options()))

class Login(webapp.RequestHandler):
    def get(self):
        self.redirect(users.create_login_url('/sessions'))

class Logout(webapp.RequestHandler):
    def get(self):
        self.redirect(users.create_logout_url('/'))

class Sessions(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        players = Player.all().filter('user =', user).fetch(100)
        result = []
        for player in players:
            s = None
            for p in (player.sessions_as1, player.sessions_as2, player.sessions_as3):
                if p.count() > 0:
                    s = p[0]
                    break
            if not s:
                continue
            line = {}
            line['id'] = s.key().id()
            line['hostedby'] = s.player_1.user.nickname()
            line['started'] = s.started
            line['lastmove'] = s.modified
            if s.state in ('hosted', 'ready'):
                line['turn'] = s.dealer.user.nickname()
            else:
                line['turn'] = s.turn.user.nickname()
            line['state'] = s.state
            result.append(line)
        domain = self.request.headers.get('host', 'no host')
        self.response.out.write(render('sessions.html', options({'sessions': result, 'domain': domain})))

class Host(webapp.RequestHandler):
    def post(self):
        user = users.get_current_user()
        session = Session()
        session.host(user)
        domain = self.request.headers.get('host', 'no host')
        self.response.out.write(render('host.html', options({'id': session.key().id(), 'domain': domain})))

class Stats(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        session = getSession(self)
        query = db.GqlQuery("SELECT * FROM History " + "WHERE session = :1 ORDER BY datetime", session)
        results = query.fetch(1000)
        points = [[p for p in (r.player_1, r.player_2, r.player_3)] for r in results]
        players = []
        for p in (session.player_1, session.player_2, session.player_3):
            if p and p.user:
                name = p.user.nickname()
                if p.plus:
                    name += ' +'
                players.append(name)
            else:
                players.append('[Not connected]')
        colors = ['FFBF00', '85AC1E', 'FF7100']
        data1 = [p[0] for p in points]
        data2 = [p[1] for p in points]
        data3 = [p[2] for p in points]
        data = data1 + data2 + data3
        if len(data) > 0:
            minimum = min(0, round(min(data1 + data2 + data3)-100, -2))
        else:
            minimum = 0
        chart = SimpleLineChart(680, 300, 'Progress of the game', players, colors, y_range=(minimum, 1000))
        chart.set_legend_position('r')
        chart.set_grid(0, 10000.0 / (1000-minimum), 5, 5)
        chart.set_axis_labels(Axis.BOTTOM, range(1, len(points)+1))
        chart.set_axis_range(Axis.LEFT, minimum, 1000)
        chart.add_data(data1)
        chart.add_data(data2)
        chart.add_data(data3)
        self.response.out.write(render('stats.html', {'ingame': True,
                                                      'session': session.key().id(),
                                                      'players': players,
                                                      'points': points,
                                                      'chart': chart.get_url()}))

class Play(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        try:
            session = getSession(self)
            player = session.getPlayerByUser(user)
            if player is None:
                player = session.join(user)
            return self.response.out.write(render('game.html', {'ingame': True, 'session': session.key().id()}))
        except GameError, error:
            return self.response.out.write(render('error.html', {'error': error}))

class Deal(webapp.RequestHandler):
    def post(self):
        user = users.get_current_user()
        session = getSession(self)
        player = session.getPlayerByUser(user)
        session.deal(player)

class GoOpen(webapp.RequestHandler):
    def post(self):
        user = users.get_current_user()
        session = getSession(self)
        player = session.getPlayerByUser(user)
        player.goOpen()

class GoBlind(webapp.RequestHandler):
    def post(self):
        user = users.get_current_user()
        session = getSession(self)
        player = session.getPlayerByUser(user)
        player.goBlind()

class RaiseBet(webapp.RequestHandler):
    def post(self):
        user = users.get_current_user()
        session = getSession(self)
        player = session.getPlayerByUser(user)
        upto = int(self.request.get('upto'))
        if session.state == 'bettings':
            session.raiseBet(player, upto)
        elif session.state == 'finalBet':
            session.start(player, upto)

class MakePass(webapp.RequestHandler):
    def post(self):
        user = users.get_current_user()
        session = getSession(self)
        player = session.getPlayerByUser(user)
        session.makePass(player)

class CollectBank(webapp.RequestHandler):
    def post(self):
        user = users.get_current_user()
        session = getSession(self)
        player = session.getPlayerByUser(user)
        session.collectBank(player)

class PutCard(webapp.RequestHandler):
    def post(self):
        user = users.get_current_user()
        session = getSession(self)
        player = session.getPlayerByUser(user)
        card = self.request.get('card')
        card = ThousandCard(card)
        if session.state == 'finalBet':
            session.discardCard(player, card)
        else:
            session.putCard(player, card)

class RetrieveCard(webapp.RequestHandler):
    def post(self):
        user = users.get_current_user()
        session = getSession(self)
        player = session.getPlayerByUser(user)
        card = self.request.get('card')
        card = ThousandCard(card)
        session.retrieveCard(player, card)

class TakePlus(webapp.RequestHandler):
    def post(self):
        user = users.get_current_user()
        session = getSession(self)
        player = session.getPlayerByUser(user)
        session.takePlus(player)

class Update(webapp.RequestHandler):
    def get(self):
        try:
            state = self.getState(self)
            out = json.dumps(state, separators=(',',':'))
            self.response.headers['Content-Type'] = 'application/json'
            return self.response.out.write(out)
        except GameError, error:
            return self.response.out.write(render('error.html', {'error': error}))
    
    def getState(self, handler):
        response = {}
        user = users.get_current_user()
        id = self.request.get('id')
        last = self.request.get('last')
        response['last'] = repr(time.time())
        session = getSession(handler)
        lastChat = self.request.get('last_chat')
        if lastChat:
            stamp = datetime.datetime.fromtimestamp(float(lastChat)+1)
            query = db.GqlQuery("SELECT * FROM Chat " + "WHERE session = :1 AND datetime > :2 ORDER BY datetime", session, stamp)
        else:
            query = db.GqlQuery("SELECT * FROM Chat " + "WHERE session = :1 ORDER BY datetime", session)
        results = query.fetch(100)
        if results:
            response['last_chat'] = repr(time.mktime(results[-1].datetime.timetuple()))
        response['chat'] = [{'datetime': r.datetime.strftime('%Y.%m.%d %H:%M:%S'), 
                             'player': r.player.user.nickname(), 
                             'message': r.message} for r in results]
        
        player = session.getPlayerByUser(user)
        if player is None:
            player = session.join(user)

        if session.player_1 == player:
            opponent1, opponent2 = session.player_2, session.player_3
        elif session.player_2 == player:
            opponent1, opponent2 = session.player_3, session.player_1
        elif session.player_3 == player:
            opponent1, opponent2 = session.player_1, session.player_2

        for p in ('player', 'opponent1', 'opponent2'):
            pl = eval(p)
            response[p + '_turn'] = ''
            response[p + '_info'] = ''
            if pl:
                response[p + '_username'] = pl.user.nickname()
                response[p + '_points'] = str(pl.points) + ' points'
                response[p + '_plus'] = pl.plus
                response[p + '_barrel'] = pl.barrel
            else:
                response[p + '_username'] = '[Not connected]'
                response[p + '_points'] = ''
                response[p + '_plus'] = False
                response[p + '_barrel'] = 0

        response['info_header'] = ''

        if session.isFull():
            turn = session.turn
            if player.blind is True:
                response['state'] = 'go_blind'
                response['cards'] = ['BACK'] * 7
            elif player.blind is False:
                response['state'] = 'go_open'
                response['cards'] = [str(c) for c in sorted(player.cards)]
            else:
                response['state'] = 'open_or_blind'
                response['cards'] = ['BACK'] * 7
            if session.state == 'ready':
                turn = session.dealer
                response['state'] = 'ready'
            elif session.state == 'bettings':
                response['info_header'] = session.info
                response['bank'] = ['BACK'] * 3
                response['passed'] = player.passed
                response['first'] = session.isFirstMove()
                if not player.passed:
                    response['bettings'] = []
                    for bet in range(session.bet + 10, 301, 10):
                        response['bettings'].append(bet)
                for p in ('player', 'opponent1', 'opponent2'):
                    pl = eval(p)
                    if pl.passed:
                        response[p + '_info'] = 'Pass'
                    elif pl.bet:
                        response[p + '_info'] = 'Bet %d' % pl.bet
                        if (pl.blind):
                            response[p + '_info'] += ' (Blind)'
                    else:
                        response[p + '_info'] = ''
            elif session.state == 'collect':
                winner = session.betsWinner()
                response['info_header'] = '%s takes the bank' % session.betsWinner().user.nickname()
                response['state'] = 'collect'
                response['cards'] = [str(c) for c in sorted(player.cards)]
                if player == winner:
                    response['bank'] = [str(c) for c in session.bank]
                else:
                    if session.blind:
                        response['bank'] = ['BACK'] * 3
                    else:
                        response['bank'] = [str(c) for c in session.bank]
            elif session.state == 'finalBet':
                response['state'] = 'finalBet'
                response['cards'] = [str(c) for c in sorted(player.cards)]
                if turn == player:
                    response['info_header'] = 'Discard 3 card and make final bet'
                    response['bank'] = [str(c) for c in session.bank]
                    if session.blind:
                        response['bettings'] = [session.bet]
                        for bet in range(session.bet*2, 301, 10):
                            response['bettings'].append(bet)
                    else:
                        response['bettings'] = []
                        for bet in range(session.bet, 301, 10):
                            response['bettings'].append(bet)
                else:
                    response['info_header'] = 'Waiting for final bet'
                    response['bank'] = ['BACK'] * len(session.bank)
            elif session.state == 'inGame':
                response['state'] = 'inGame'
                opponent1 = session.getNextPlayer(player)
                opponent2 = session.getNextPlayer(opponent1)
                offset = max(len(player.thrown), len(opponent1.thrown), len(opponent2.thrown))
                response['bank'] = []
                response['memo'] = []
                response['taken'] = 'Taken: ' + str(player.getGamePoints())
                for pl in ('player', 'opponent1', 'opponent2'):
                    p = eval(pl)
                    if p == session.betsWinner():
                        response[pl + '_info'] = 'Plays %d' % session.bet
                        if session.blind:
                            response[pl + '_info'] += ' (Blind)'
                    if offset > 0 and len(p.thrown) == offset:
                        response['bank'].append(str(p.thrown[offset-1]))
                    else:
                        response['bank'].append(None)
                    if offset > 1 and len(p.thrown) >= offset-1:
                        response['memo'].append(str(p.thrown[offset-2]))
                    else:
                        response['memo'].append(None)
                if len(player.thrown) == 0:
                    if session.blind:
                        response['memo'] = ['BACK'] * 3
                    else:
                        response['memo'] = [str(c) for c in session.memo]
                response['cards'] = [str(c) for c in sorted(player.cards)]
                if session.trump:
                    response['trump'] = 'Trump: ' + ThousandCard.kinds[session.trump]
                else:
                    response['trump'] = ''
                if session.info:
                    response['info_header'] = session.info
            elif session.state == 'endGame':
                turn = session.dealer
                response['state'] = 'ready'
                response['info_header'] = session.info
                opponent1 = session.getNextPlayer(player)
                opponent2 = session.getNextPlayer(opponent1)
                response['player_info'] = 'Took: %d' % player.bet
                response['opponent1_info'] = 'Took: %d' % opponent1.bet
                response['opponent2_info'] = 'Took: %d' % opponent2.bet
                response['cards'] = []
                response['bank'] = [(len(p.thrown) > 0 and str(p.thrown[-1])) or None for p in (player, opponent1, opponent2)]
            elif session.state == 'finish':
                response['state'] = 'finish'
                response['info_header'] = session.info
                response['player_info'] = 'Took: %d' % player.bet
                response['opponent1_info'] = 'Took: %d' % opponent1.bet
                response['opponent2_info'] = 'Took: %d' % opponent2.bet
                response['cards'] = []
                response['bank'] = [str(p.thrown[-1]) for p in (player, opponent1, opponent2)]

            if turn == player: response['player_turn'] = True
            elif turn == opponent1: response['opponent1_turn'] = True
            elif turn == opponent2: response['opponent2_turn'] = True

        else:
            response['info_header'] = 'Waiting for players'
            response['state'] = 'hosted'
        return response

class Chat(webapp.RequestHandler):
    def post(self):
        user = users.get_current_user()
        session = getSession(self)
        player = session.getPlayerByUser(user)
        message = self.request.get('message')
        chat = models.Chat()
        chat.session = session
        chat.player = player
        chat.message = message
        chat.put()