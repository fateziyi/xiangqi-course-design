import json
from pathlib import Path
import random
import time
import unittest
from ai.search import Search, search, MATE
from engine.rules import Position, key, legal_moves, parse_move
from engine.evaluation import evaluate
from scripts.compare_versions import legacy
from tests.test_rules import position


class SearchUpgradeTests(unittest.TestCase):
    def test_capture_horizon_trap_both_colors(self):
        # Rook takes pawn, opposing rook recaptures. Depth-one static search
        # used to treat the pawn as free; the hand-authored expectation is avoid.
        p=position({4:-1,85:1,49:7,27:5,18:-7,9:-5})
        for mirrored in (False, True):
            if mirrored:
                b=tuple(-x for x in reversed(p.board))
                q=Position(b,'black',0,(key(b,'black'),));trap=(62,71)
            else: q=p;trap=(27,18)
            old,parser=legacy()
            self.assertEqual(parse_move(old(parser(q.wire()),dict(maxDepth=1,timeLimitMs=500))['move']),trap)
            answer=search(q,dict(maxDepth=1,timeLimitMs=500))
            self.assertGreaterEqual(answer['search']['completedDepth'],1)
            self.assertNotEqual(parse_move(answer['move']),trap)
            worker=Search(time.monotonic()+1)
            score,_=worker.quiescence(q.play(trap),-MATE*2,MATE*2,1)
            self.assertGreater(score,600)  # opponent sees winning rook exchange

    def test_checked_quiescence_cannot_stand_pat(self):
        p=position({4:-1,85:1,49:7,76:-5})
        worker=Search(time.monotonic()+1)
        _,pv=worker.quiescence(p,-1,0,0,remaining=0)
        self.assertTrue(pv)
        self.assertIn(pv[0],legal_moves(p.board,p.side))
        for move in pv:p=p.play(move)

    def test_quiescence_stalemate_and_draw_priority(self):
        p=position({4:-1,85:1,49:7,13:5,12:5,14:5},'black')
        p=Position(p.board,p.side,120,p.keys*3)
        worker=Search(time.monotonic()+1)
        self.assertEqual(worker.quiescence(p,-MATE*2,MATE*2,0)[0],-MATE)
        p=Position.initial();p=Position(p.board,p.side,0,p.keys*3)
        self.assertEqual(worker.quiescence(p,-MATE*2,MATE*2,0)[0],0)

    def test_history_safe_table_context(self):
        p=Position.initial()
        repeated=Position(p.board,p.side,0,p.keys*3)
        near_limit=Position(p.board,p.side,119,p.keys)
        self.assertNotEqual(Search.context_key(p),Search.context_key(repeated))
        self.assertNotEqual(Search.context_key(p),Search.context_key(near_limit))
        worker=Search(time.monotonic()+2)
        worker.negamax(p,1,-MATE*2,MATE*2,0)
        self.assertEqual(worker.negamax(repeated,1,-MATE*2,MATE*2,0)[0],0)

    def test_filtered_move_generation_and_v1_evaluation(self):
        _,parser=legacy()
        from legacy_engine.rules import legal_moves as old_moves
        from legacy_engine.evaluation import evaluate as old_evaluate
        from engine.evaluation import evaluate_v3
        p=Position.initial();rng=random.Random(20261012)
        for _ in range(80):
            moves=legal_moves(p.board,p.side)
            self.assertEqual(moves,old_moves(p.board,p.side))
            self.assertEqual(legal_moves(p.board,p.side,captures_only=True),[m for m in moves if p.board[m[1]]])
            self.assertEqual(legal_moves(p.board,p.side,limit=1),moves[:1])
            self.assertEqual(evaluate_v3(p.board),old_evaluate(p.board))
            mirror=tuple(-x for x in reversed(p.board))
            self.assertEqual(evaluate(mirror),-evaluate(p.board))
            if p.result(moves):break
            p=p.play(rng.choice(moves))

    def test_user_record_regression_and_budget(self):
        record=json.loads(Path('samples/人机棋谱/象棋棋谱-2026-10-12T09-18-52.159Z.json').read_text(encoding='utf-8'))
        from backend.game import Game
        game=Game.from_record(record)
        self.assertEqual(len(game.moves),85)
        self.assertEqual(game.position.result(),dict(winner='red',reason='checkmate'))
        # Validate the actual user positions, returned PV, budget and input
        # immutability. These are not claims of uniquely optimal human play.
        for ply in (1,27,43,75):
            p=game.positions[ply];before=p.wire()
            answer=search(p,dict(maxDepth=8,timeLimitMs=100))
            self.assertLess(answer['search']['elapsedMs'],250)
            self.assertIn(parse_move(answer['move']),legal_moves(p.board,p.side))
            for m in answer['search']['pv']:p=p.play(parse_move(m))
            self.assertEqual(game.positions[ply].wire(),before)

    def test_pvs_matches_full_window_root(self):
        p=position({4:-1,85:1,49:7,27:5,18:-7,9:-5})
        worker=Search(time.monotonic()+5)
        value,pv=worker.negamax(p,2,-MATE*2,MATE*2,0)
        # Independently enumerate every root move with a full window. Reuse
        # only quiescence as the leaf definition, no PVS/root-bound decisions.
        scores={}
        for m in legal_moves(p.board,p.side):
            child=p.play(m);answers=[]
            for reply in legal_moves(child.board,child.side):
                leaf=child.play(reply)
                w=Search(time.monotonic()+2)
                answers.append(w.quiescence(leaf,-MATE*2,MATE*2,2)[0])
            scores[m]=min(answers) if answers else MATE-1
        self.assertEqual(value,max(scores.values()))
        self.assertEqual(scores[pv[0]],value)


if __name__=='__main__':unittest.main()
