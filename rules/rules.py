import itertools
import unittest

# The groups are of the form:
# ('pon', tile)
# ('chi', tile)
# ('pair', tile)
# The pair is always first.

# We take advantage of the lexicographical ordering of tiles.

def find_pair(tiles):
    for i in range(len(tiles)-1):
        if tiles[i] == tiles[i+1]:
            # don't count false duplicates
            if i+2 < len(tiles) and tiles[i+1] == tiles[i+2]:
                continue
            yield (('pair', tiles[i]), tiles[:i]+tiles[i+2:])

def begin_pon(tiles):
    if len(tiles) >= 3 and tiles[0] == tiles[1] == tiles[2]:
        yield (('pon', tiles[0]), tiles[3:])

def begin_chi(tiles):
    t1 = tiles[0]
    suit = t1[0]
    n = int(t1[1])
    if suit == 'X' or n >= 8:
        # honor, or number tile >= 8
        return
    t2 = suit+str(n+1)
    t3 = suit+str(n+2)
    if t2 in tiles and t3 in tiles:
        tiles = list(tiles)
        tiles.remove(t1)
        tiles.remove(t2)
        tiles.remove(t3)
        yield (('chi', t1), tiles)

def decompose_regular(tiles):
    def all_groups(tiles):
        if tiles == []:
            yield []
        else:
            beginning_groups = itertools.chain(
                begin_pon(tiles),
                begin_chi(tiles))
            for group, new_tiles in beginning_groups:
                for groups in all_groups(new_tiles):
                    yield [group] + groups

    for pair, new_tiles in find_pair(tiles):
        for groups in all_groups(new_tiles):
            yield [pair] + groups

def is_all_pairs(tiles):
    return all(tiles[i] == tiles[i+1] for i in range(0, len(tiles), 2))

def is_terminal(tile):
    return tile[0] in 'MPS' and tile[1] in '19'

def is_honor(tile):
    return tile[0] == 'X'

def is_junchan_group(g):
    type, tile = g
    if type in ['pon', 'pair']:
        return is_terminal(tile)
    else:
        return tile[0] in 'MPS' and tile[1] in '17'

def is_chanta_group(g):
    type, tile = g
    return is_junchan_group(g) or is_honor(tile)

def is_chi_boundary(tile, chi_tile):
    if tile[0] != chi_tile[0]:
        return False
    n = int(tile[1])
    cn = int(chi_tile[1])
    return n == cn or n == cn+2

def suits_of_tiles(tiles):
    return set(t[0] for t in tiles)

class Hand(object):
    RECOGNIZED_YAKU = ['pinfu',
                       'iipeiko',
                       'tanyao',
                       'fanpai',
                       'nikoniko',
                       'chanta',
                       'junchan',
                       'honitsu',
                       'chinitsu']

    def __init__(self, tiles, wait, type, groups=None, options={}):
        self.tiles = tiles
        self.wait = wait
        self.type = type
        self.groups = groups
        self.options = options

    def yaku_pinfu(self):
        if self.type != 'regular':
            return False
        pair_tile = self.groups[0][1]
        if pair_tile[0] == 'X':
            if pair_tile in ['X5', 'X6', 'X7']: # dragons
                return False
            if pair_tile in self.options.get('fanpai_winds', []):
                return False
        if any(type == 'pon' for type, tile in self.groups):
            return False
        for type, tile in self.groups[1:]:
            if is_chi_boundary(self.wait, tile):
                return True
        return False

    def yaku_iipeiko(self):
        if self.type != 'regular':
            return False
        for i in range(1,len(self.groups)-1):
            if self.groups[i][0] == 'chi' and self.groups[i] == self.groups[i+1]:
                return True
        return False

    def yaku_tanyao(self):
        return not any(is_terminal(t) or is_honor(t) for t in self.tiles)

    def yaku_fanpai(self):
        if self.type != 'regular':
            return False
        if 'fanpai_winds' not in self.options:
            return False
        fanpai_winds = self.options['fanpai_winds']
        return any(type == 'pon' and tile in fanpai_winds
                   for type, tile in self.groups)

    def yaku_nikoniko(self):
        return self.type == 'pairs'

    def yaku_junchan(self):
        if self.type != 'regular':
            return False
        return (all(is_junchan_group(g) for g in self.groups) and
                any(type == 'chi' for t in self.groups))

    def yaku_chanta(self):
        if self.type != 'regular':
            return False
        if self.yaku_junchan():
            return False
        return (all(is_junchan_group(g) for g in self.groups) and
                any(type == 'chi' for t in self.groups))

    def yaku_honitsu(self):
        suits = suits_of_tiles(self.tiles)
        return len(suits) == 2 and 'X' in suits

    def yaku_chinitsu(self):
        return suits_of_tiles(self.tiles) == set(['X'])

    def all_yaku(self):
        result = []
        for name in self.RECOGNIZED_YAKU:
            m = getattr(self, 'yaku_' + name)
            if m():
                result.append(name)
        return result

def all_hands(tiles, wait, options={}):
    for groups in decompose_regular(tiles):
        yield Hand(tiles, wait, 'regular', groups=groups, options=options)
    if is_all_pairs(tiles):
        yield Hand(tiles, wait, 'pairs', options=options)
    #if is_kokushi(tiles): # to be implemented

class RulesTestCase(unittest.TestCase):
    def test_find_pair(self):
        self.assertEquals(list(find_pair(['M1','M2','M3'])), [])
        self.assertEquals(list(find_pair(['M1','M1','M3'])),
                          [(('pair', 'M1'), ['M3'])])

    def test_find_pair_dupes(self):
        self.assertEquals(len(list(find_pair(['M1', 'M1', 'M1']))), 1)
        self.assertEquals(len(list(find_pair(['M1', 'M1', 'M1', 'M1']))), 1)

    def test_begin_pon(self):
        self.assertEqual(list(begin_pon('M1 M1 M1'.split())), [(('pon', 'M1'), [])])
        self.assertEqual(list(begin_pon('M1 M1 M2'.split())), [])

    def test_begin_chi(self):
        self.assertEqual(list(begin_chi('M1 M2 M3 M4'.split())), [(('chi', 'M1'), ['M4'])])
        self.assertEqual(list(begin_chi('M1 M2 M4'.split())), [])

    def test_decompose(self):
        tiles = 'M1 M1 M2 M2 M3 M3 M4 M4'.split()
        self.assertEqual(list(decompose_regular(tiles)),
                         [[('pair', 'M1'), ('chi', 'M2'), ('chi', 'M2')],
                          [('pair', 'M4'), ('chi', 'M1'), ('chi', 'M1')]])

    def test_is_all_pairs(self):
        self.assertTrue(is_all_pairs('M1 M1 M2 M2'.split()))
        self.assertFalse(is_all_pairs('M1 M1 M2 M3'.split()))

class HandTestCase(unittest.TestCase):
    def assertYaku(self, tiles_str, wait, yaku_sets):
        tiles = tiles_str.split()
        result = set()
        # In the tests, we assume that East (X1) is the only fanpai wind.
        for hand in all_hands(tiles, wait, {'fanpai_winds': ['X1']}):
            result.add(frozenset(hand.all_yaku()))
        self.assertEqual(result, set(frozenset(y) for y in yaku_sets))

    def test_yaku(self):
        self.assertYaku('M2 M2 M3 M3 M4 M4 P2 P3 P4 P7 P7 P7 S2 S2', 'M3',
                        [['iipeiko', 'tanyao']])
        self.assertYaku('M1 M2 M3 M4 M5 M6 M6 M7 M8 P2 P2 P2 X1 X1', 'M1',
                        [[]])
        self.assertYaku('M1 M1 M1 M1 M2 M2 M2 M2 M3 M3 M3 M3 M9 M9', 'M1',
                        [['pinfu', 'ryanpeiko', 'junchan', 'chinitsu'],
                         ['sananko', 'chinitsu']])
        self.assertYaku('M1 M2 M2 M3 M3 M3 M3 M4 M4 M4 M5 M5 M6 M6', 'M1',
                        [['pinfu', 'iipeiko', 'chinitsu'],
                         ['pinfu', 'iipeiko', 'chinitsu']])
        self.assertYaku('P1 P2 P3 S5 S5 X5 X5 X5 X6 X6 X6 X7 X7 X7', 'S5',
                        [['daisangen']])
        self.assertYaku('P1 P2 P3 S5 S5 S5 X5 X5 X5 X6 X6 X6 X7 X7', 'S5',
                        [['fanpai', 'fanpai', 'shosangen']])
        self.assertYaku('P1 P2 P3 S9 S9 S9 X5 X5 X5 X6 X6 X7 X7 X7', 'P1',
                        [['fanpai', 'fanpai', 'chanta', 'sananko',
                          'shosangen']])
        self.assertYaku('M1 M9 P1 P9 S1 S9 S9 X1 X2 X3 X4 X5 X5 X7', 'S1',
                        [['kokushi']])
        self.assertYaku('M1 M1 M2 M2 M3 M3 M7 M7 M8 M8 M9 M9 X5 X5', 'M3',
                        [['chanta', 'honitsu', 'ryanpeiko']])
        self.assertYaku('M2 M3 M4 M5 M6 M7 P3 P3 P3 P5 P6 P7 S4 S4', 'M7',
                        [['tanyao']])
        self.assertYaku('X1 X1 X1 M2 M3 M4 M5 M6 M7 M8 M8 M8 M9 M9', 'X1',
                        [['fanpai', 'honitsu']])
        self.assertYaku('X1 X1 M2 M3 M4 M5 M6 M7 M8 M8 M8 M9 M9 M9', 'X1',
                        [['honitsu']])
        self.assertYaku('M2 M3 M4 M5 M6 M7 P2 P3 P4 P5 P6 P7 P8 P8', 'P7',
                        [['pinfu', 'tanyao']])

if __name__ == '__main__':
    unittest.main()
