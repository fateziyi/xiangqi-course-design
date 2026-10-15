"""Independent v3 geometry oracle and v4 search/evaluation regressions."""
import importlib
import random
import time
import unittest
from unittest.mock import patch

from ai.search import Search, BudgetExpired, search
from engine.rules import Position, legal_moves, attacked, pseudo_targets
from engine.evaluation import evaluate, evaluate_v3
from scripts.compare_versions import legacy
from tests.test_rules import position


class StrengthV4Tests(unittest.TestCase):
    def test_geometry_matches_original_on_all_squares(self):
        legacy()
        from legacy_engine.rules import attacked as original_attacked
        from legacy_engine.rules import pseudo_targets as original_targets
        from legacy_engine.rules import legal_moves as original_moves
        rng=random.Random(40261012);p=Position.initial()
        for n in range(300):
            if n%3:
                moves=legal_moves(p.board,p.side)
                self.assertEqual(moves,original_moves(p.board,p.side))
                p=Position.initial() if p.result(moves) else p.play(rng.choice(moves))
                board=p.board
            else:
                b=[rng.choice([0]*14+list(range(-7,8))) for _ in range(90)]
                b=[0 if abs(x)==1 else x for x in b];b[4]=-1;b[85]=1;board=tuple(b)
                for side in ('red','black'):
                    self.assertEqual(legal_moves(board,side),original_moves(board,side))
            for target in range(90):
                self.assertEqual(list(pseudo_targets(board,target)),list(original_targets(board,target)))
                for enemy in (-1,1):
                    self.assertEqual(attacked(board,target,enemy),original_attacked(board,target,enemy))

    def test_evaluation_color_symmetry_and_initial_balance(self):
        self.assertEqual(evaluate(Position.initial().board),0)
        rng=random.Random(4026);p=Position.initial()
        for _ in range(120):
            self.assertEqual(evaluate(tuple(-x for x in reversed(p.board))),-evaluate(p.board))
            moves=legal_moves(p.board,p.side)
            p=Position.initial() if p.result(moves) else p.play(rng.choice(moves))

    def test_mobile_horse_and_last_rank_pawn_terms(self):
        # Equal material; use delta against v3 to isolate the new activity terms.
        open_horse=position({4:-1,85:1,49:7,40:4})
        blocked=position({4:-1,85:1,49:7,40:4,31:2,39:2,41:2})
        delta=lambda p:evaluate(p.board)-evaluate_v3(p.board)
        self.assertGreater(delta(open_horse),delta(blocked))
        last_rank=position({4:-1,85:1,49:7,0:7})
        before_last=position({4:-1,85:1,49:7,9:7})
        self.assertLess(delta(last_rank),delta(before_last))

    def test_aspiration_failure_cannot_publish_incomplete_iteration(self):
        module=importlib.import_module('ai.search');calls=[]
        class Interrupted(Search):
            def negamax(self,p,depth,alpha,beta,ply,preferred=None):
                calls.append((depth,alpha,beta))
                if depth==3 and alpha < -1000:raise BudgetExpired()
                return (100 if depth==3 else depth),[self.moves(p)[0]]
        with patch.object(module,'Search',Interrupted):
            answer=search(Position.initial(),dict(maxDepth=3,timeLimitMs=500))
        self.assertEqual(answer['search']['completedDepth'],2)
        self.assertEqual(answer['search']['score'],2)
        self.assertEqual([c[0] for c in calls],[1,2,3,3])
        self.assertLess(calls[-1][1],calls[-2][1])

    def test_filtered_queries_reuse_full_legal_cache(self):
        p=Position.initial();worker=Search(time.monotonic()+1)
        full=worker.moves(p)
        with patch('ai.search.legal_moves',side_effect=AssertionError('cache was not reused')):
            self.assertEqual(worker.moves(p,existence=True),full[:1])
            self.assertEqual(worker.moves(p,captures=True),tuple(m for m in full if p.board[m[1]]))


if __name__=='__main__':unittest.main()
