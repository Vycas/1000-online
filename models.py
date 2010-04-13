from google.appengine.ext import db
from google.appengine.api import users
from cards import ThousandCard
from random import shuffle

class GameError(Exception):
    pass

class ThousandCardProperty(db.Property):
    data_type = list
    
    def default_value(self):
        return []
    
    def get_value_for_datastore(self, value):
        value = super(ThousandCardProperty, self).get_value_for_datastore(value)
        return ' '.join([str(x) for x in value])

    def make_value_from_datastore(self, value):
        if value is None:
            return None
        if value == '':
            return []
        return [ThousandCard(x) for x in value.split(' ')]

    def validate(self, value):
        if value is not None and not isinstance(value, list):
            raise db.BadValueError('Property %s must be convertible '
                                'to a list instance (%s)' % (self.name, value))
        return super(ThousandCardProperty, self).validate(value)

    def empty(self, value):
        return len(value) == 0

class Player(db.Model):
    user = db.UserProperty(required=True)
    points = db.IntegerProperty(default=0)
    cards = ThousandCardProperty()
    bank = ThousandCardProperty()
    thrown = ThousandCardProperty()
    tricks = ThousandCardProperty()
    blind = db.BooleanProperty()
    bet = db.IntegerProperty()
    passed = db.BooleanProperty(default=False)
    plus = db.BooleanProperty(default=False)
    calls = db.StringProperty()
    barrel = db.IntegerProperty(default=0)
    
    def __cmp__(self, other):
        return self.key().id().__cmp__(other.key().id())
    
    def goBlind(self):
        """
        Chooses to play blind.
        
        Fails if:
            - Choise was already open.
        """
        
        if self.blind is False:
            raise GameError('The choise was already made to be open.')
        
        self.blind = True
        self.put()
    
    def goOpen(self):
        """
        Chooses to play open.
        
        Always succeeds. None -> Open OK. Blind -> Open OK.
        """
        
        self.blind = False
        self.put()
    
    def hasPair(self, card):
        """
        Checks if player have a pair for given card.
        """
        
        v = card.value()
        k = card.kind()
        if v == 'K':
            c = ThousandCard(k+'Q')
            return c in self.cards
        elif v == 'Q':
            c = ThousandCard(k+'K')
            return c in self.cards
        else:
            return False
    
    def hasKind(self, kind):
        """
        Checks if player has card for given kind.
        """
        
        for card in self.cards:
            if card.kind() == kind:
                return True
        return False
    
    def getGamePoints(self):
        """
        Calculates and returns points collected in current game.
        """
        
        points = 0
        for c in self.calls:
            points += ThousandCard.pairs[c]
        for c in self.tricks:
            points += c.points()
        return points

class Session(db.Model):
    player_1 = db.ReferenceProperty(Player, collection_name='sessions_as1')
    player_2 = db.ReferenceProperty(Player, collection_name='sessions_as2')
    player_3 = db.ReferenceProperty(Player, collection_name='sessions_as3')
    dealer = db.ReferenceProperty(Player, collection_name='sessions_dealer')
    started = db.DateTimeProperty(auto_now_add=True)
    modified = db.DateTimeProperty(auto_now=True)
    finished = db.DateTimeProperty()
    turn = db.ReferenceProperty(Player)
    bet = db.IntegerProperty()
    state = db.StringProperty()
    blind = db.BooleanProperty(default=False)
    bank = ThousandCardProperty()
    memo = ThousandCardProperty()
    trump = db.StringProperty()
    info = db.StringProperty()

    def __cmp__(self, other):
        return self.key().id().__cmp__(other.key().id())

    def host(self, user):
        """
        One user start the session as host.
        """
        
        player = Player(user=user)
        player.put()
        self.player_1 = player
        self.dealer = player
        self.state = 'hosted'
        self.put()
        return player

    def join(self, user):
        """
        Another user joins this session and becomes its player.
        """

        if self.player_2 is None:
            player = Player(user=user)
            player.put()
            self.player_2 = player
            self.put()
            return player
        elif self.player_3 is None:
            player = Player(user=user)
            player.put()
            self.player_3 = player
            self.state = 'ready'
            self.put()
            return player
        else:
            raise GameError('This session is already full.')
        
    def isFull(self):
        """
        Checks if all three player joined.
        """

        return (self.player_1 is not None) and \
               (self.player_2 is not None) and \
               (self.player_3 is not None)

    def getPlayerByUser(self, user):
        """
        Return the player associated with given user in this session.
        """
        
        if self.player_1 and self.player_1.user == user: return self.player_1
        elif self.player_2 and self.player_2.user == user: return self.player_2
        elif self.player_3 and self.player_3.user == user: return self.player_3
        else: return None

    def getNextPlayer(self, current):
        """
        Returns who is the next after the current player.
        """

        if current == self.player_1:
            return self.player_2
        elif current == self.player_2:
            return self.player_3
        elif current == self.player_3:
            return self.player_1

    def deal(self, player):
        """
        New game is started in given session.
        The game can only be started by dealer.
        Dealer deals the cards.
        The turn is given to player after dealer.

        Fails if:
            - Current game have not been finished.
            - Session is not full.
            - Current user is not a dealer.
        """

        if not self.state in ('ready', 'endGame'):
            raise GameError('Current game have not been finished or session is not full.')
        if player != self.dealer:
            raise GameError('Only the dealer can start the game.')

        cards = ThousandCard.generateDeck()
        shuffle(cards)
        for i, player in enumerate([self.player_1, self.player_2, self.player_3]):
            player.cards = cards[i*7:(i+1)*7]
            player.passed = False
            player.bet = None
            player.blind = None
            player.bank = []
            player.thrown = []
            player.tricks = []
            player.calls = ''
            player.put()
        self.info = '%s deals the cards' % player.user.nickname()
        self.bank = cards[21:24]
        self.memo = []
        self.turn = self.dealer = self.getNextPlayer(self.dealer)
        self.bet = 90
        self.state = 'bettings'
        self.blind = False
        self.trump = None
        self.info = None
        self.put()

    def raiseBet(self, player, bet):
        """
        Tries to raise the bet up to given value.

        Fails if:
            - Bets are already finished
            - The turn is not for the given user
            - Value is bettween 100 and 300
            - Value is not divisible by 10
            - Value is smaller than the current bet

        First to reach 300 finished bettings.
        """

        if self.state != 'bettings':
            raise GameError('Bettings are already finished.')
        if self.turn != player:
            raise GameError('It\'s not your turn to bet.')
        if bet < 100 or bet > 300:
            raise GameError('Bet must be between 100 and 300.')
        if bet % 10 != 0:
            raise GameError('Bets must be divisible by 10.')
        if bet <= self.bet:
            raise GameError('Your bet must be higher than current bet.')

        player.bet = bet
        player.put()
        self.bet = bet
        self.info = '%s raises up to %d' % (player.user.nickname(), bet)
        self.put()
        if bet == 300:
            self.finishBets()
            return
        next = self.getNextPlayer(player)
        if next.passed:
            next = self.getNextPlayer(next)
        if next.passed:
            self.finishBets()
            return
        self.turn = next
        self.put()

    def makePass(self, player):
        """
        Passes the bettings in current game. The player can only pass once in a game.

        Fails if:
            - Bets are already finished
            - The turn is not for the given player
            - Player has already passed
            - Player can not pass if he is the first one
        """

        if self.state != 'bettings':
            raise GameError('Bettings are already finished.')
        if self.turn != player:
            raise GameError('It\'s not your turn to pass.')
        if player.passed:
            raise GameError('This player has already passed.')
        if self.isFirstMove():
            raise GameError('The first player cannot pass the first time.')

        player.passed = True
        player.put()
        self.info = '%s passes' % player.user.nickname()
        self.put()
        next = self.getNextPlayer(player)
        if next.passed:
            next = self.getNextPlayer(next)
        self.turn = next
        self.put()
        if self.betsOver():
            self.finishBets()

    def isFirstMove(self):
        """
        Checks if it is the first move in the game.
        """

        return (self.bet == 90) and (self.dealer == self.turn)

    def betsOver(self):
        """
        Checks if bettings are over.

        Bet are over when:
            - Two of the three player passes
            - 300 points bet is reached
        """

        passed = 0
        if self.player_1.passed: passed += 1
        if self.player_2.passed: passed += 1
        if self.player_3.passed: passed += 1

        if passed == 2:
            return True
        if self.bet == 300:
            return True
        return False

    def betsWinner(self):
        """"
        Returns bets winner (last betting player) which can collect the bank.
        """

        if self.player_1.bet == 300: return self.player_1
        if self.player_2.bet == 300: return self.player_2
        if self.player_3.bet == 300: return self.player_3

        if not self.player_1.passed: return self.player_1
        elif not self.player_2.passed: return self.player_2
        elif not self.player_3.passed: return self.player_3
        else: raise GameError('Unexpected error: all players passed')

    def finishBets(self):
        """
        After bets are over, set game variables and goes to bank collect state.
        """

        player = self.betsWinner()
        self.bet = player.bet
        self.blind = player.blind
        self.state = 'collect'
        self.turn = player
        self.put()
        
    def collectBank(self, player):
        """
        Collect the bank.

        Fails if:
            - Game state is not for collect.
            - The given player is the winner of bettings.
        """

        if self.state != 'collect':
            raise GameError('Bank can not be collected at this game state.')
        if self.betsWinner() != player:
            raise GameError('Only the bets winner can collect the bank.')

        player.cards += self.bank
        player.put()
        self.info = '%s takes the bank' % player.user.nickname()
        self.memo += self.bank
        self.bank = []
        self.state = 'finalBet'
        self.put()

    def discardCard(self, player, card):
        """
        Discards card to the bank.

        Fails if:
            - The turn is not for the given player.
            - There is already 3 cards in bank.
            - Player does not have given card.
            - Game state is not for discarding cards.
        """

        if self.state != 'finalBet':
            raise GameError('You can not put cards in this game state.')
        if self.turn != player:
            raise GameError('It\'s not your turn to go.')
        if len(self.bank) == 3:
            raise GameError('There is already 3 cards in bank.')
        if not card in player.cards:
            raise GameError('Player does not have given card.')

        player.cards.remove(card)
        self.bank.append(card)
        player.put()
        self.put()

    def retrieveCard(self, player, card):
        """
        Retrieves card from the bank in final bet state (in case of mistake).

        Fails if:
            - Game state is not final bet.
            - The turn is not for the given player.
            - Bank does not contain given card.
        """

        if self.state != 'finalBet':
            raise GameError('Retrieving cards is possible only in final bet state.')
        if self.turn != player:
            raise GameError('It\'s not your turn to go.')
        if not card in self.bank:
            raise GameError('Bank does not contain given card.')

        self.bank.remove(card)
        self.put()
        player.cards.append(card)
        player.put()

    def takePlus(self, player):
        """
        Takes a plus (passes the game after bettings) for a player.
        
        Fails if:
            - Game state is not final bet.
            - The turn is not for the given player.
            - Player already has a plus. (It is only possible to pass once after bettings.)
        """
        
        if self.state != 'finalBet':
            raise GameError('Taking a plus is possible only in final bet state.')
        if self.turn != player:
            raise GameError('It\'s not your turn to go.')
        if player.plus:
            raise GameError('Player already has a plus.')
        
        player.plus = True
        player.bet = 0
        player.put()
        self.state = 'endGame'
        nextdealer = self.getNextPlayer(self.getNextPlayer(self.dealer))
        self.dealer = nextdealer
        self.turn = nextdealer
        self.info = '%s passes the game' % player.user.nickname()
        self.put()
        opponent1 = self.getNextPlayer(player)
        opponent2 = self.getNextPlayer(opponent1)
        for op in (opponent1, opponent2):
            pts = 60
            if self.blind:
                pts *= 2
            if op.points >= 880:
                pts = 0                
            op.points += pts
            op.bet = pts
            op.put()

    def start(self, player, finalBet):
        """
        Called after bank collection and final bet. Start the main game.

        Fails if:
            - The turn is not for the given player.
            - Game state is not final bet.
            - 3 cards have not been discarded.
            - Final bet is not bettween 100 and 300
            - Final bet is not divisible by 10
            - Final bet is smaller than current bet.
        """

        if self.turn != player:
            raise GameError('It\'s not your turn.')
        if self.state != 'finalBet':
            raise GameError('Game can be begun only in final bet state.')
        if len(self.bank) != 3:
            raise GameError('3 cards must be discarded before begining the game.')
        if finalBet < 100 or finalBet > 300:
            raise GameError('Bet must be between 100 and 300.')
        if finalBet % 10 != 0:
            raise GameError('Bet must be divisible by 10.')
        if finalBet < self.bet:
            raise GameError('Your bet must be higher or equal than current bet.')
        if self.blind and (finalBet != self.bet) and (finalBet < self.bet * 2):
            raise GameError('When blind, your final bet must be double than current bet or equal.')

        if self.blind and (finalBet > self.bet * 2):
            self.blind = False
            player.blind = False
        self.bet = finalBet
        player.bet = finalBet
        self.state = 'inGame'
        self.info = '%s plays %d' % (player.user.nickname(), finalBet)
        player.tricks = self.bank
        self.bank = []
        player.put()
        self.put()
    
    def putCard(self, player, card):
        """
        Puts card to the bank.

        Fails if:
            - The turn is not for the given player.
            - Player does not have given card.
            - Game state is not for putting cards.
            - Given card doesn't match bank kind.
        """

        if self.state != 'inGame':
            raise GameError('You can not put cards in this game state.')
        if self.turn != player:
            raise GameError('It\'s not your turn to go.')
        if not card in player.cards:
            raise GameError('Player does not have given card.')

        if len(self.bank) > 0:
            first = self.bank[0]
            if (first.kind() == card.kind()) or (not player.hasKind(first.kind())):
                player.cards.remove(card)
                player.thrown.append(card)
                self.bank.append(card)
            else:
                raise GameError('You must put the card with matching kind.')
        else:
            player.cards.remove(card)
            player.thrown.append(card)
            self.bank.append(card)

        player.bank = [card]
        self.info = ''
        if (len(self.bank) == 1) and player.hasPair(card):
            player.calls += card.kind()
            self.trump = card.kind()
            self.info = '%s calls %d (%s)' % (player.user.nickname(), 
                        ThousandCard.pairs[self.trump], ThousandCard.kinds[self.trump])
        if len(self.bank) == 3:
            self.bank[0].player = self.getNextPlayer(player)
            self.bank[1].player = self.getNextPlayer(self.bank[0].player)
            self.bank[2].player = player
            anyTrumps = ([c.kind() for c in self.bank].count(self.trump) > 0)
            for c in self.bank:
                if anyTrumps:
                    c.isTrump = (c.kind() == self.trump)
                else:
                    c.isTrump = (c.kind() == self.bank[0].kind())
            bestCard = sorted(self.bank, cmp=cardCompare)[-1]
            bestCard.player.tricks += self.bank
            bestCard.player.put()
            self.bank = []
            self.turn = bestCard.player
            self.info = bestCard.player.user.nickname() + ' takes the trick'
            if len(player.cards) == 0:
                w = self.betsWinner()
                for p in (self.player_1, self.player_2, self.player_3):
                    pts = p.getGamePoints()
                    if p == w:
                        if pts >= self.bet:
                            pts = self.bet
                            self.info = "%s succeeds playing %d" % (p.user.nickname(), self.bet)
                        else:
                            pts = -self.bet
                            self.info = "%s fails playing %d" % (p.user.nickname(), self.bet)
                        if self.blind:
                            self.info += " (Blind)"
                            pts *= 2
                        p.points += pts
                    else:
                        if self.blind:
                            pts *= 2
                        pts = int(round(pts, -1))
                        if p.points >= 880:
                            pts = 0
                        p.points += pts
                    if p.points >= 1000:
                        self.state = 'finish'
                        self.info = '%s has won the game!' % p.user.nickname()
                        #TODO: add finish date
                        self.put()
                    elif p.points >= 880:
                        p.barrel += 1
                        if p.barrel > 3:
                            p.barrel = 0
                            p.points -= 120
                    p.bet = pts
                    p.put()
                h = History(session=self,
                            player_1=self.player_1.points,
                            player_2=self.player_2.points,
                            player_3=self.player_3.points)
                h.put()
                if self.state != 'finish':
                    self.state = 'endGame'
                self.put()
                return
        else:
            self.turn = self.getNextPlayer(player)
        player.put()
        self.put()

    def getPlayerOffset(self, player):
        """
        Returns given player offset in current game.
        That is, how far away the player is from the first player.
        """

        if (len(self.bank) == 0) or (self.state != 'inGame'):
            return 0
        else:
            card = player.bank[0]
            nextcard = self.getNextPlayer(player).bank[0]
            if self.bank[0] == card: return 0
            elif self.bank[0] == nextcard: return 1
            else: return 2


class History(db.Model):
    session = db.ReferenceProperty(Session)
    datetime = db.DateTimeProperty(auto_now_add=True)
    player_1 = db.IntegerProperty()
    player_2 = db.IntegerProperty()
    player_3 = db.IntegerProperty()


class Chat(db.Model):
    session = db.ReferenceProperty(Session)
    player = db.ReferenceProperty(Player)
    datetime = db.DateTimeProperty(auto_now_add=True)
    message = db.StringProperty()


def cardCompare(self, other):
    """
    Compares to cards with respect to trump.
    """
    
    t1 = self.isTrump
    t2 = other.isTrump
    if (t1 == False) and (t2 == True):
        return -1
    elif (t1 == True) and (t2 == False):
        return 1
    else:
        v1 = self.value()
        v2 = other.value()
        if self.value_order.index(v1) < self.value_order.index(v2):
            return -1
        elif self.value_order.index(v1) > self.value_order.index(v2):
            return 1
        else:
            return 0
