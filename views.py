from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import users
from models import Session, Player, GameError
import simplejson as json
import os

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
            if s.state in ('waiting', 'ready'):
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
        self.response.out.write(render('stats.html', options()))

class Play(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        try:
            session = getSession(self)
            player = session.getPlayerByUser(user)
            if player is None:
                player = session.join(user)
            return self.response.out.write(render('game.html', {'ingame': True}))
        except GameError, error:
            return self.response.out.write(render('error.html', {'error': error}))

class Start(webapp.RequestHandler):
    def post(self):
        user = users.get_current_user()
        session = getSession(self)
        player = session.getPlayerByUser(user)
        session.start(player)

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
            session.begin(player, upto)

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
        session = getSession(handler)
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
            else:
                response[p + '_username'] = '[Not connected]'
                response[p + '_points'] = ''

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
                if session.bet is not None:
                    next = session.getNextPlayer(player)
                    nextnext = session.getNextPlayer(next)
                    response['player_info'] = 'Took: %d' % player.bet
                    response['opponent1_info'] = 'Took: %d' % next.bet
                    response['opponent2_info'] = 'Took: %d' % nextnext.bet
            elif session.state == 'bettings':
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
                response['info_header'] = winner.user.nickname() + ' takes the bank'
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
                    response['bettings'] = []
                    for bet in range(session.bet, 301, 10):
                        response['bettings'].append(bet)
                else:
                    response['info_header'] = 'Waiting for final bet'
                    response['bank'] = ['BACK'] * len(session.bank)
            elif session.state == 'inGame':
                response['state'] = 'inGame'
                next = session.getNextPlayer(player)
                nextnext = session.getNextPlayer(next)
                offset = max(len(player.thrown), len(next.thrown), len(nextnext.thrown))
                response['bank'] = []
                response['memo'] = []
                for p in (player, next, nextnext):
                    if offset > 0 and len(p.thrown) == offset:
                        response['bank'].append(str(p.thrown[offset-1]))
                    else:
                        response['bank'].append(None)
                    if offset > 1 and len(p.thrown) >= offset-1:
                        response['memo'].append(str(p.thrown[offset-2]))
                    else:
                        response['memo'].append(None)
                response['cards'] = [str(c) for c in sorted(player.cards)]
                if session.trump:
                    response['trump'] = 'Trump: ' + ThousandCard.kinds[session.trump]
                else:
                    response['trump'] = ''
                if session.info:
                    response['info_header'] = session.info

            if turn == player: response['player_turn'] = 'Waiting for turn'
            elif turn == opponent1: response['opponent1_turn'] = 'Waiting for turn'
            elif turn == opponent2: response['opponent2_turn'] = 'Waiting for turn'

        else:
            response['info_header'] = 'Waiting for players'
            response['state'] = 'waiting'
        return response