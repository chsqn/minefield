import random
import unittest

import rules


DEBUG = False

TILES = rules.ALL_TILES * 4
PLAYER_TILES = 34
DISCARDS = 17

SEAT_WINDS = ('X1', 'X3')

def dummy_callback(to_player, msg_type, **msg_data):
    import pprint
    pprint.pprint((to_player, msg_type, msg_data))

class Game(object):
    # Time limits, in seconds
    DISCARD_TIME_LIMIT = 15
    HAND_TIME_LIMIT = 3*60

    # Additional leeway to accomodate connection problems and UI updates
    EXTRA_TIME = 10

    def __init__(self,
                 east=None,
                 callback=dummy_callback):
        self.callback = callback

        all_tiles = list(TILES)

        if not DEBUG:
            random.shuffle(all_tiles)

        if east == None:
            self.east = random.randrange(2)
        else:
            self.east = east

        # Tiles available for players
        n = PLAYER_TILES
        self.initial_tiles = [all_tiles[:n], all_tiles[n:n*2]]
        self.tiles = [all_tiles[:n], all_tiles[n:n*2]]

        self.dora_ind = all_tiles[n*2]
        self.uradora_ind = all_tiles[n*2+1]

        # Players' hands (None until they've chosen them)
        self.hand = [None, None]

        self.waits = [None, None]

        self.discards = [[], []]

        # Elapsed time in seconds (see beat() for details)
        self.t = 0

        # Move is (move_type, deadline)
        self.moves = [None, None]

        self.finished = False

    @property
    def phase(self):
        # First phase - hand selection
        if not (self.hand[0] and self.hand[1]):
            return 1
        # Second phase - discards
        elif not self.finished:
            return 2
        # Game finished
        else:
            return 3

    @property
    def player_turn(self):
        if len(self.discards[0]) == len(self.discards[1]):
            return self.east
        else:
            return 1-self.east

    def abort(self, culprit, description):
        '''Abort the game and provide explanation.'''

        for i in range(2):
            self.callback(i, 'abort', culprit=culprit, description=description)
            self.finished = True
        self.moves = [None, None]

    def beat(self):
        '''Make time advance by 1 second in the game, handling possible timeouts.
        To be called by external code. Optional.'''
        self.t += 1
        for i in range(2):
            if self.moves[i] is not None and self.t >= self.moves[i][1]:
                self.abort(i, 'time limit exceeded')
                return

    def start_move(self, player, move_type, time_limit):
        assert self.moves[player] is None
        deadline = self.t + time_limit + self.EXTRA_TIME
        self.moves[player] = (move_type, deadline)
        self.send_move(player)

    def end_move(self, player):
        self.moves[player] = None
        self.callback(player, 'end_move')

    def send_move(self, player):
        if self.moves[player] is None:
            return

        move_type, deadline = self.moves[player]
        time_limit = deadline - self.t - self.EXTRA_TIME
        self.callback(player, 'start_move',
                      move_type=move_type, time_limit=time_limit)

    def start(self):
        for i in range(2):
            self.callback(i, 'phase_one',
                          tiles=self.initial_tiles[i],
                          dora_ind=self.dora_ind,
                          you=i,
                          east=self.east)
            self.start_move(i, 'hand', self.HAND_TIME_LIMIT)

    def on_hand(self, player, *, hand):
        if self.phase != 1:
            self.abort(player, 'on_hand: wrong phase')
            return
        if len(hand) != 13:
            self.abort(player, 'on_hand: len != 13')
            return
        if self.hand[player] != None:
            self.abort(player, 'on_hand: hand already sent')
            return
        for tile in hand:
            # this fails if a player doesn't have a tile
            try:
                self.tiles[player].remove(tile)
            except ValueError:
                self.abort(player, 'on_hand: tile not found in choices')
                return

        self.hand[player] = hand
        self.waits[player] = list(rules.waits(hand))

        self.end_move(player)

        # Send the hand back to player (so that he can reconstruct it while replaying).
        self.callback(player, 'hand', hand=hand)

        if self.hand[0] and self.hand[1]:
            # start the second phase
            for i in range(2):
                self.callback(i, 'phase_two')
            self.start_move(self.east, 'discard', self.DISCARD_TIME_LIMIT)
        else:
            self.callback(player, 'wait_for_phase_two')

    def options(self, player, uradora=False):
        return {
            'fanpai_winds': [SEAT_WINDS[player^self.east]],
            'dora_ind': self.dora_ind,
            'uradora_ind': self.uradora_ind if uradora else None,
            'hotei': all(len(self.discards[i]) == DISCARDS for i in range(2)),
            'ippatsu': len(self.discards[1-player]) == 1,
        }

    def furiten(self, player):
        tiles = set(self.discards[player] + self.discards[1-player][:-1])
        return any(wait in tiles for wait in self.waits[player])

    def on_discard(self, player, *, tile):
        if self.phase != 2:
            self.abort(player, 'on_discard: wrong phase')
            return
        if self.player_turn != player:
            self.abort(player, 'on_discard: not your turn')
            return
        if tile not in self.tiles[player]:
            self.abort(player, 'on_discard: tile not found in choices')
            return

        self.tiles[player].remove(tile)
        self.discards[player].append(tile)

        self.end_move(player)

        for i in range(2):
            self.callback(i, 'discarded',
                          player=player,
                          tile=tile)

        # ron
        if tile in self.waits[1-player] and not self.furiten(1-player):
            if self.check_ron(player, tile):
                return

        # draw
        if len(self.discards[0]) == len(self.discards[1]) == DISCARDS:
            self.finished = True
            for i in range(2):
                self.callback(i, 'draw')
        # normal turn
        else:
            self.start_move(self.player_turn, 'discard', self.DISCARD_TIME_LIMIT)

    def check_ron(self, player, tile):
        full_hand = sorted(self.hand[1-player] + [tile])
        hand = rules.best_hand(full_hand, tile, options=self.options(1-player))
        # Check mangan limit
        if hand.limit() == 0:
            return False

        # Compute again, with uradora
        hand = rules.best_hand(full_hand, tile,
                               options=self.options(1-player, uradora=True))
        self.finished = True
        for i in range(2):
            self.callback(i, 'ron',
                player=1-player,
                hand=full_hand,
                tile=tile,
                yaku=hand.yaku,
                yakuman=hand.yakuman,
                dora=hand.dora(),
                points=rules.BASE_POINTS[hand.limit()],
                limit=hand.limit(),
                uradora_ind=self.uradora_ind,
            )

        return True


class GameTestCase(unittest.TestCase):
    def setUp(self):
        from collections import deque

        global DEBUG
        DEBUG = True # suppress randomization

        self.messages = deque()

        self.g = Game(east=0, callback=self.callback)
        self.g.start()

    def assertMessage(self, player, msg_type, msg={}):
        our_m = self.messages.popleft()
        self.assertEqual(our_m, (player, msg_type, msg))

    def assertNoMessage(self, msg_type):
        self.assertFalse(any(_msg_type == msg_type
                             for (player, _msg_type, msg) in self.messages))

    def assertMessageBoth(self, msg_type, msg={}):
        self.assertMessage(0, msg_type, msg)
        self.assertMessage(1, msg_type, msg)

    def callback(self, to_player, msg_type, **msg_data):
        self.messages.append((to_player, msg_type, msg_data))

    def test_init(self):
        # the game has just been created
        n = PLAYER_TILES
        self.assertMessage(0, 'phase_one',
                           {'tiles': TILES[:n],
                            'dora_ind': 'M1',
                            'you': 0,
                            'east': 0})
        self.assertMessage(0, 'start_move', {'move_type': 'hand', 'time_limit': Game.HAND_TIME_LIMIT})
        self.assertMessage(1, 'phase_one',
                           {'tiles': TILES[n:n*2],
                            'dora_ind': 'M1',
                            'you': 1,
                            'east': 0})
        self.assertMessage(1, 'start_move', {'move_type': 'hand', 'time_limit': Game.HAND_TIME_LIMIT})

    def start_game(self, s1, s2):
        self.test_init()
        self.g.on_hand(0, hand=s1.split())
        self.assertMessage(0, 'end_move', {})
        self.assertMessage(0, 'hand', {'hand': s1.split()})
        self.assertMessage(0, 'wait_for_phase_two')
        self.g.on_hand(1, hand=s2.split())
        self.assertMessage(1, 'end_move', {})
        self.assertMessage(1, 'hand', {'hand': s2.split()})
        self.assertMessageBoth('phase_two')

    def test_draw_scenario(self):
        self.start_game('M1 M2 M3 M4 M5 M6 M7 M8 M9 P1 P2 P3 P4',
                        'M1 M2 M3 M4 M5 M6 M7 M8 M9 P1 P2 P3 P4')

        for i in range(DISCARDS):
            for j in range(2):
                # Just discard the first choice
                t = self.g.tiles[j][0]
                self.discard(j, t)
        self.assertMessageBoth('draw')

    def discard(self, player, tile):
        self.assertMessage(player, 'start_move', {'move_type': 'discard', 'time_limit': Game.DISCARD_TIME_LIMIT})
        self.g.on_discard(player, tile=tile)
        self.assertMessage(player, 'end_move', {})
        self.assertMessageBoth('discarded', {'player': player,
                                             'tile': tile})

    def test_win(self):
        # P0: 13-sided kokushi
        # P1: riichi ippatsu dora - 3 fan, not enough for mangan
        self.start_game('M1 M9 P1 P9 S1 S9 X1 X2 X3 X4 X5 X6 X7',
                        'M1 M2 M3 M4 M5 M6 P7 P8 P9 S1 S2 S3 S4')

        # P1's winning tile - there should be no 'ron' message
        self.discard(0, 'S4')
        self.assertNoMessage('ron')

        # Rising Sun!
        self.discard(1, 'P1')
        self.assertMessageBoth('ron', {
            'player': 0,
            'yaku': ['kokushi'],
            'yakuman': True,
            'hand': 'M1 M9 P1 P1 P9 S1 S9 X1 X2 X3 X4 X5 X6 X7'.split(),
            'points': 32000,
            'limit': 5,
            'dora': 0,
            'uradora_ind': 'M2',
            'tile': 'P1'
        })


    def test_furiten(self):
        # P0: junk
        # P1: riichi tanyao sanshoku on S5, but only riichi tanyao on S8
        self.start_game('M2 M9 P1 P9 S1 S9 X1 X2 X3 X4 X5 X6 X7',
                        'M6 M7 M8 P6 P7 P8 S2 S3 S4 S5 S6 S7 S8')

        # P1's winning tile - there should be no 'ron' message
        # riichi ippatsu tanyao - no mangan
        self.discard(0, 'S8')
        self.assertNoMessage('ron')

        self.discard(1, 'P1')

        # P1 would win now, but she's in furiten
        self.discard(0, 'S5')
        self.assertNoMessage('ron')

    def test_short_hand(self):
        self.test_init()
        self.g.on_hand(1, hand='M1 M2 M3'.split())
        self.assertMessageBoth('abort', {'culprit': 1, 'description': 'on_hand: len != 13'})
        self.assertTrue(self.g.finished)

    def test_tiles_outside_initial(self):
        self.test_init()
        self.g.on_hand(0, hand=['M1']*13)
        self.assertMessageBoth('abort', {'culprit': 0, 'description': 'on_hand: tile not found in choices'})
        self.assertTrue(self.g.finished)

    def test_hand_time_limit(self):
        self.test_init()
        hand = 'M2 M9 P1 P9 S1 S9 X1 X2 X3 X4 X5 X6 X7'.split()
        self.g.on_hand(0, hand=hand)
        self.assertMessage(0, 'end_move', {})
        self.assertMessage(0, 'hand', {'hand': hand})
        self.assertMessage(0, 'wait_for_phase_two')
        for i in range(self.g.HAND_TIME_LIMIT + self.g.EXTRA_TIME):
            self.g.beat()
        self.assertMessageBoth('abort', {'culprit': 1, 'description': 'time limit exceeded'})

    def test_discard_time_limit(self):
        self.start_game('M1 M2 M3 M4 M5 M6 M7 M8 M9 P1 P2 P3 P4',
                        'M1 M2 M3 M4 M5 M6 M7 M8 M9 P1 P2 P3 P4')
        self.assertMessage(0, 'start_move', {'move_type': 'discard', 'time_limit': Game.DISCARD_TIME_LIMIT})
        for i in range(self.g.DISCARD_TIME_LIMIT + self.g.EXTRA_TIME):
            self.g.beat()
        self.assertMessageBoth('abort', {'culprit': 0, 'description': 'time limit exceeded'})


if __name__ == '__main__':
    unittest.main()
