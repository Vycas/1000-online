import unittest
from random import shuffle
from cards import Card, ThousandCard

class TestCard(unittest.TestCase):
    def setUp(self):
        self.card = Card('HQ')
        self.kinds = ['S', 'C', 'D', 'H']
        self.values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

    def test_value(self):
        self.assertEqual(self.card.value(), 'Q')

    def test_kind(self):
        self.assertEqual(self.card.kind(), 'H')

    def test_valueName(self):
        self.assertEqual(self.card.valueName(), 'Queen')

    def test_kindName(self):
        self.assertEqual(self.card.kindName(), 'Hearts')

    def test_fullName(self):
        self.assertEqual(self.card.fullName(), 'The Queen of Hearts')

    def test_str(self):
        self.assertEqual(str(self.card), 'HQ')

    def test_invalidKind(self):
        self.assertRaises(ValueError, Card, 'P8')

    def test_invalidValue(self):
        self.assertRaises(ValueError, Card, 'DB')

    def test_generateDeck(self):
        deck = Card.generateDeck()
        self.assertEqual(type(deck), list)
        self.assertEqual(52, len(deck))
        for kind in self.kinds:
            for value in self.values:
                self.assertTrue(Card(kind+value) in deck)

    def test_sorting(self):
        deck = Card.generateDeck()
        shuffle(deck)
        deck = sorted(deck)
        for i in range(0, 52-1):
            if self.kinds.index(deck[i].kind()) == self.kinds.index(deck[i+1].kind()):
                self.assertTrue(self.values.index(deck[i].value()) < self.values.index(deck[i+1].value()))
            else:
                self.assertTrue(self.kinds.index(deck[i].kind()) < self.kinds.index(deck[i+1].kind()))

class TestThousandCard(TestCard):
    def setUp(self):
        self.card = Card('HQ')
        self.kinds = ['S', 'D', 'C', 'H']
        self.values = ['9', 'J', 'Q', 'K', '10', 'A']
        self.points = {'A': 11, '10': 10, 'K': 4, 'Q': 3, 'J': 2, '9': 0}

    def test_generateDeck(self):
        super(TestCard, self)

    def test_sorting(self):
        super(TestCard, self)

    def test_points(self):
        deck = ThousandCard.generateDeck()
        for c in deck:
            self.assertEqual(c.points(), self.points[c.value()])
        self.assertEqual(sum([c.points() for c in deck]), 120)

if __name__ == '__main__':
    unittest.main()
