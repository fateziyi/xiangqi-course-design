import unittest
import json
from pathlib import Path
from ai.search import search,MATE
from engine.rules import Position,parse_move,legal_moves,parse_position
from tests.test_rules import position

class SearchTests(unittest.TestCase):
    def test_ten_unique_mates(self):
        for case in json.loads(Path('fixtures/mate_one.json').read_text(encoding='utf-8')):
            p=parse_position(case['position']);expected=parse_move(case['expected'])
            mates=[m for m in legal_moves(p.board,p.side) if p.play(m).result()=={'winner':p.side,'reason':'checkmate'}]
            self.assertEqual(mates,[expected],case['id'])
            result=search(p,dict(maxDepth=4,timeLimitMs=1500))
            self.assertEqual(result['move'],case['expected'],case['id'])
    def test_budget_and_pv(self):
        p=Position.initial();before=p.wire()
        result=search(p,dict(maxDepth=12,timeLimitMs=100))
        self.assertLess(result['search']['elapsedMs'],200)
        self.assertIn(parse_move(result['move']),legal_moves(p.board,p.side))
        q=p
        for m in result['search']['pv']:q=q.play(parse_move(m))
        self.assertEqual(before,p.wire())
        self.assertEqual(result['search']['pv'][0],result['move'])

    def test_terminal(self):
        p=position({4:-1,85:1,49:7,13:5,12:5,14:5},'black')
        result=search(p,dict(maxDepth=4,timeLimitMs=500))
        self.assertIsNone(result['move']);self.assertEqual(result['search']['completedDepth'],0)
        self.assertEqual(result['search']['score'],-MATE)

    def test_mate_one(self):
        p=position({4:-1,85:1,49:7,3:-5,5:-5,18:5})
        result=search(p,dict(maxDepth=3,timeLimitMs=500))
        q=p.play(parse_move(result['move']))
        self.assertEqual(q.result(),{'winner':'red','reason':'checkmate'})
        self.assertEqual(result['move'],{'from':18,'to':22})

if __name__=='__main__':unittest.main()
