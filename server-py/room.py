
import unittest
import logging

from game import Game
from utils import make_key

logger = logging.getLogger('room')


class Room(object):
    def __init__(self, nicks=['P1', 'P2'], game_class=Game):
        self.game = game_class(callback=self.send_to_player)
        self.nicks = nicks
        self.players = [None, None]
        self.messages = [[], []]
        self.keys = self.make_keys()
        self.aborted = False
        self.id = None

    def init_from_data(self, data):
        self.game = Game.from_data(data['game'], callback=self.send_to_player)
        del data['game']
        self.players = [None, None]
        super(Room, self).init_from_data(data)

    def start_game(self):
        logger.info('[room %s] starting', self.id)
        self.game.start()

    def make_keys(self):
        return (make_key(), make_key())

    def send_to_player(self, idx, msg_type, **msg):
        self.messages[idx].append((msg_type, msg))
        if self.players[idx]:
            logger.info('[room %s] send to %d: %s %r', self.id, idx, msg_type, msg)
            self.players[idx].send(msg_type, **msg)

    def add_player(self, idx, player, n_received=0):
        assert not self.players[idx]
        self.players[idx] = player
        player.set_room(self, idx)
        self.replay_messages(idx, n_received)

    def remove_player(self, idx):
        self.players[idx] = None

    def replay_messages(self, idx, n_received):
        messages = self.messages[idx]
        for msg_type, msg in messages[n_received:]:
            # we don't replay move info, only send the last one to the player
            if msg_type in ['start_move', 'end_move']:
                continue

            logger.info('[room %s] replay to %d: %s %r', self.id, idx, msg_type, msg)

            self.players[idx].send('replay', msg={'type': msg_type, **msg})
        self.game.send_move(idx)

    def send_to_game(self, idx, msg_type, **msg):
        logger.info('[room %s] receive from %d: %s %r', self.id, idx, msg_type, msg)
        try:
            handler = getattr(self.game, 'on_'+msg_type)
            handler(idx, **msg)
        except:
            logger.exception('exception after receiving')
            self.abort()

    def beat(self):
        if self.finished:
            return

        try:
            self.game.beat()
        except:
            logger.exception('exception in beat')
            self.abort()

    def abort(self):
        self.aborted = True
        for idx in range(2):
            if self.players[idx]:
                self.players[idx].shutdown()

    @property
    def finished(self):
        return self.aborted or self.game.finished


class RoomTest(unittest.TestCase):
    class MockGame(object):
        def __init__(self, nicks=None, east=None, callback=None):
            self.callback = callback
            self.started = False

        def start(self):
            assert not self.started
            self.started = True

        def on_ping(self, idx, **msg):
            self.callback(1-idx, 'pong', **msg)

        def on_crash(self, idx, **msg):
            raise RuntimeError('crashed')

        def send_move(self, idx):
            pass

    class MockPlayer(object):
        def __init__(self):
            self.messages = []
            self.finished = False
            self.room = None
            self.idx = None

        def send(self, msg_type, **msg):
            self.messages.append((msg_type, msg))

        def shutdown(self):
            self.finished = True

        def set_room(self, room, idx):
            self.room = room
            self.idx = idx

    def create_room(self, players=[None, None]):
        room = Room(game_class=self.MockGame)
        for idx, player in enumerate(players):
            if player:
                room.add_player(idx, player)
        room.start_game()
        return room

    def test_create(self):
        room = self.create_room()
        self.assertIsInstance(room.game, self.MockGame)
        self.assertTrue(room.game.started)

    def test_send_immediately(self):
        player0 = self.MockPlayer()
        room = self.create_room([player0, None])
        room.game.callback(0, 'ping_0')
        self.assertEquals(len(player0.messages), 1)
        self.assertEquals(player0.messages[0][0], 'ping_0')

        player1 = self.MockPlayer()
        room.add_player(1, player1)
        room.game.callback(1, 'ping_1')
        self.assertEquals(len(player1.messages), 1)
        self.assertEquals(player1.messages[0][0], 'ping_1')

    def test_replay_after_connect(self):
        room = self.create_room()
        room.game.callback(0, 'a')
        room.game.callback(0, 'b')
        room.game.callback(1, 'c')
        room.game.callback(1, 'd')
        room.game.callback(0, 'e')
        player0 = self.MockPlayer()
        room.add_player(0, player0, n_received=1)
        self.assertEquals(len(player0.messages), 2)
        self.assertEquals(player0.messages[0], ('replay', {'msg': {'type': 'b'}}))
        self.assertEquals(player0.messages[1], ('replay', {'msg': {'type': 'e'}}))

    def test_send_to_game(self):
        player0 = self.MockPlayer()
        player1 = self.MockPlayer()
        room = self.create_room([player0, player1])
        room.send_to_game(1, 'ping')
        self.assertEquals(len(player0.messages), 1)
        self.assertEquals(player0.messages[0][0], 'pong')

    def test_send_and_crash(self):
        player0 = self.MockPlayer()
        player1 = self.MockPlayer()
        room = self.create_room([player0, player1])
        room.send_to_game(0, 'crash')
        self.assertTrue(player0.finished)
        self.assertTrue(player1.finished)

if __name__ == '__main__':
    #logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(name)s: %(message)s')
    unittest.main()
