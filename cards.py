class Card:
    """
    Represents a card.

    Card can have kind and value. Card is encoded into string using
    following notation: [Kind][Value]
    
    Kinds:
        S - Spades
        C - Clubs
        D - Diamonds
        H - Hearts

    Values:
        2..10
        A - Ace
        K - King
        Q - Queen
        J - Jack

    Examples:
        The queen of hearts -> HQ
        The ace of clubs -> CA
        Seven of spades -> S7

    >>> c = Card('HQ')
    >>> c.value()
    'Q'
    >>> c.kind()
    'H'
    >>> c.valueName()
    'Queen'
    >>> c.kindName()
    'Hearts'
    >>> c.fullName()
    'The Queen of Hearts'
    >>> d = Card('D8')
    >>> d < c
    True
    >>> Card('H0')
    Traceback (most recent call last):
        ...
    ValueError: Invalid value code given for the card.
    >>> Card('W7')
    Traceback (most recent call last):
        ...
    ValueError: Invalid kind code given for the card.
    """

    def __init__(self, code):
        if not code[0] in self.kinds.keys():
            raise ValueError('Invalid kind code given for the card.')
        if not code[1:] in self.values.keys():
            raise ValueError('Invalid value code given for the card.')
        self.code = code

    def __str__(self):
        return self.code

    #def __repr__(self):
    #    return repr(self.code)

    def __hash__(self):
        return hash(self.code)

    def __cmp__(self, other):
        k1 = self.kind_order.index(self.kind())
        k2 = self.kind_order.index(other.kind())
        if k1 < k2: return -1
        elif k1 > k2: return 1
        else:
            v1 = self.value_order.index(self.value())
            v2 = self.value_order.index(other.value())
            if v1 < v2: return -1
            elif v1 > v2: return 1
            else: return 0

    def kind(self):
        return self.code[0]

    def value(self):
        return self.code[1:]

    def kindName(self):
        return self.kinds[self.kind()]

    def valueName(self):
        return self.values[self.value()]

    def fullName(self):
        return "The %s of %s" % (self.valueName(), self.kindName())

    @classmethod
    def generateDeck(cls):
        return [cls(kind + value) for value in cls.values.keys() for kind in cls.kinds.keys()]

    kinds = {'S': 'Spades', 'C': 'Clubs', 'D': 'Diamonds', 'H': 'Hearts'}
    values = {'A': 'Ace', 'K': 'King', 'Q': 'Queen', 'J': 'Jack',
              '10': 'Ten', '9': 'Nine', '8': 'Eight', '7': 'Seven', '6': 'Six',
              '5': 'Five', '4': 'Four', '3': 'Three', '2': 'Two'}
    
    kind_order = ('S', 'C', 'D', 'H')
    value_order = ('2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A')


class ThousandCard(Card):
    """
    A limitation to traditional card, allowing value to be only
    Ace, 10, King, Queen, Jack, and 9.
    
    Also implemented point counting.
    """

    def points(self):
        return self.weight[self.value()]

    pairs = {'S': 40, 'C': 60, 'D': 80, 'H': 100}
    weight = {'A': 11, '10': 10, 'K': 4, 'Q': 3, 'J': 2, '9': 0}
    values = {'A': 'Ace', 'K': 'King', 'Q': 'Queen', 'J': 'Jack', '10': 'Ten', '9': 'Nine'}
    value_order = ('9', 'J', 'Q', 'K', '10', 'A')


if __name__ == "__main__":
    import doctest
    doctest.testmod()
