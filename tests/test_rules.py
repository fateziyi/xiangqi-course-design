import unittest
from engine.rules import *

def position(pieces,side='red',no_capture=0):
    b=[0]*90
    for i,p in pieces.items(): b[i]=p
    return Position(tuple(b),side,no_capture,(key(b,side),))

class RulesTests(unittest.TestCase):
    def test_initial(self):
        p=Position.initial()
        self.assertEqual(len(legal_moves(p.board,p.side)),44)
        self.assertEqual(sum(x!=0 for x in p.board),32)
        self.assertFalse(in_check(p.board,'red'))
        self.assertEqual(parse_position(p.wire()),p)

    def test_rook_and_cannon(self):
        p=position({85:1,4:-1,49:7,72:5,74:7,76:-7,64:6,37:7,10:-5})
        rook=set(pseudo_targets(p.board,72))
        self.assertIn(73,rook); self.assertNotIn(75,rook)
        cannon=set(pseudo_targets(p.board,64))
        self.assertIn(10,cannon); self.assertNotIn(37,cannon); self.assertIn(55,cannon)

    def test_horse_leg(self):
        p=position({85:1,4:-1,49:7,58:4,49:7})
        targets=set(pseudo_targets(p.board,58))
        self.assertNotIn(39,targets); self.assertIn(75,targets)
        p=position({85:1,4:-1,66:-4,75:7,49:7})
        self.assertFalse(in_check(p.board,'red'))
        p=position({85:1,4:-1,66:-4,49:7})
        self.assertTrue(in_check(p.board,'red'))

    def test_elephant_and_advisor(self):
        p=position({85:1,4:-1,49:7,83:3,75:7,84:2})
        self.assertNotIn(67,set(pseudo_targets(p.board,83)))
        self.assertIn(63,set(pseudo_targets(p.board,83)))
        self.assertEqual(set(pseudo_targets(p.board,84)),{76})
        p=position({85:1,4:-1,49:7,47:3})
        self.assertNotIn(31,set(pseudo_targets(p.board,47)))

    def test_pawns_and_palace(self):
        p=Position.initial()
        self.assertEqual(set(pseudo_targets(p.board,54)),{45})
        p=position({85:1,4:-1,36:7,53:-7})
        self.assertEqual(set(pseudo_targets(p.board,36)),{27,37})
        self.assertEqual(set(pseudo_targets(p.board,53)),{62,52})
        self.assertEqual(set(pseudo_targets(p.board,85)),{76,84,86})

    def test_facing_and_self_check(self):
        p=position({85:1,4:-1,49:5})
        self.assertNotIn((49,48),legal_moves(p.board,'red'))
        p=position({85:1,4:-1,49:-5,76:5})
        self.assertNotIn((76,75),legal_moves(p.board,'red'))
        self.assertIn((76,49),legal_moves(p.board,'red'))
        self.assertNotIn((76,4),legal_moves(p.board,'red'))

    def test_mate_and_stalemate(self):
        mate=position({4:-1,85:1,49:7,13:5,12:5,14:5},'black')
        self.assertEqual(mate.result(),{'winner':'red','reason':'checkmate'})
        stale=position({4:-1,85:1,49:7,21:5,23:5,9:5},'black')
        self.assertFalse(in_check(stale.board,'black'))
        self.assertEqual(stale.result(),{'winner':'red','reason':'stalemate'})

    def test_draws_and_priority(self):
        p=Position.initial()
        for m in [(82,63),(1,18),(63,82),(18,1)]*2: p=p.play(m)
        self.assertEqual(p.result()['reason'],'threefold')
        p=Position(p.board,p.side,120,(key(p.board,p.side),))
        self.assertEqual(p.result()['reason'],'no_capture_limit')
        mate=position({4:-1,85:1,49:7,13:5,12:5,14:5},'black',120)
        self.assertEqual(mate.result()['reason'],'checkmate')

    def test_immutable_and_capture_counter(self):
        p=Position.initial(); q=p.play((54,45))
        self.assertEqual(p,Position.initial()); self.assertEqual(q.no_capture,1)
        p=position({85:1,4:-1,49:7,72:5,63:-7},no_capture=19)
        self.assertEqual(p.play((72,63)).no_capture,0)
        with self.assertRaises(ValueError): parse_move({'from':True,'to':20})

if __name__=='__main__': unittest.main()
