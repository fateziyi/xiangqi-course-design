import asyncio
import json
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from backend.game import Game
from backend.protocol import options, Problem
from backend import pikafish
from engine.rules import Position, key, legal_moves, parse_move
from tests.test_game import CONFIG


class NativeContractTests(unittest.TestCase):
    def test_coordinate_roundtrip_and_fen(self):
        self.assertEqual(pikafish.uci_move((64,67)),'b2e2')
        for start in range(90):
            for end in range(90):
                if start!=end:self.assertEqual(pikafish.from_uci(pikafish.uci_move((start,end))),(start,end))
        for bad in ('0000','a0a0','j0a1','a:a1','a0a10'):
            with self.assertRaises(ValueError):pikafish.from_uci(bad)
        self.assertEqual(pikafish.fen(Position.initial().board,'red'),
            'rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1')

    def test_engine_configuration_and_records(self):
        native=dict(engine='pikafish',maxDepth=128,timeLimitMs=10000)
        self.assertEqual(options(native),native)
        self.assertEqual(options(dict(engine='self',maxDepth=8,timeLimitMs=1500)),dict(maxDepth=8,timeLimitMs=1500))
        for bad in (dict(engine='unknown',maxDepth=8,timeLimitMs=500),dict(maxDepth=128,timeLimitMs=500),
                    dict(engine='pikafish',maxDepth=129,timeLimitMs=500),dict(engine='pikafish',maxDepth=128,timeLimitMs=True)):
            with self.assertRaises(ValueError):options(bad)
        game=Game({**CONFIG,'redAI':native});record=game.record()
        self.assertEqual(record['version'],2);self.assertEqual(Game.from_record(record).record(),record)
        record['version']=1
        with self.assertRaises(Problem):Game.from_record(record)
        old=Game(CONFIG).record();self.assertEqual(old['version'],1)
        self.assertEqual(Game.from_record(old).record(),old)
        old['version']=2
        with self.assertRaises(Problem):Game.from_record(old)

    def test_complete_history_and_incoherent_rejection(self):
        record=json.loads(Path('samples/人机棋谱/象棋棋谱-2026-10-12T09-18-52.159Z.json').read_text(encoding='utf-8'))
        game=Game.from_record(record)
        p=game.positions[40];command=pikafish.history_command(p)
        self.assertEqual(command.split(' moves ')[1].split(),[pikafish.uci_move(m) for m in game.moves[:40]])
        p=Position.initial()
        bad=Position(p.board,'red',0,p.keys*2)
        with self.assertRaises(ValueError):pikafish.history_command(bad)
        q=p.play((54,45));bad=Position(q.board,q.side,7,q.keys)
        # Clock can legitimately include an earlier segment. This history
        # starts with clock six and faithfully reaches the specified seven.
        self.assertIn(' - - 6 1 moves ',pikafish.history_command(bad))

    def test_info_exact_bounds_and_mate(self):
        self.assertIsNone(pikafish.parse_info('info depth 9 score cp 80 lowerbound nodes 30 pv b2e2'))
        info=pikafish.parse_info('info depth 21 seldepth 30 multipv 1 score cp 33 nodes 300 time 50 pv b2e2 b9c7')
        self.assertEqual(info['completedDepth'],21);self.assertEqual(info['pv'][0],(64,67))
        self.assertEqual(pikafish.parse_info('info depth 12 score mate -3 nodes 200 pv b2e2')['score'],-99994)


class NativeProcessTests(unittest.IsolatedAsyncioTestCase):
    async def test_initialization_timeout_reaps_process(self):
        owned=[];original=asyncio.create_subprocess_exec
        async def spawn(*args,**kwargs):
            proc=await original(*args,**kwargs);owned.append(proc)
            async def stalled_read():await asyncio.Future()
            proc.stdout.readline=stalled_read
            return proc
        with patch('backend.pikafish.asyncio.create_subprocess_exec',spawn), patch.object(pikafish,'NATIVE_STARTUP_SECONDS',.2):
            with self.assertRaises(TimeoutError):
                await pikafish.search(Position.initial(),dict(maxDepth=128,timeLimitMs=500))
        self.assertTrue(owned);self.assertIsNotNone(owned[0].returncode)

    async def test_actual_native_search_and_legal_pv(self):
        record=json.loads(Path('samples/人机棋谱/象棋棋谱-2026-10-12T09-18-52.159Z.json').read_text(encoding='utf-8'))
        game=Game.from_record(record)
        for p in (Position.initial(),game.positions[27],game.positions[84]):
            before=p.wire();result=await pikafish.search(p,dict(maxDepth=128,timeLimitMs=500))
            self.assertEqual(result['search']['engine'],'pikafish')
            self.assertLess(result['search']['elapsedMs'],1500)
            self.assertIn(parse_move(result['move']),legal_moves(p.board,p.side))
            self.assertEqual(p.wire(),before)
            for move in result['search']['pv']:p=p.play(parse_move(move))
        self.assertEqual(p.result(),dict(winner='red',reason='checkmate'))

    async def test_native_cancel_reaps_owned_process(self):
        owned=[];original=asyncio.create_subprocess_exec
        async def spawn(*args,**kwargs):
            proc=await original(*args,**kwargs);owned.append(proc);return proc
        with patch('backend.pikafish.asyncio.create_subprocess_exec',spawn):
            task=asyncio.create_task(pikafish.search(Position.initial(),dict(maxDepth=128,timeLimitMs=10000)))
            for _ in range(200):
                if owned:break
                await asyncio.sleep(.005)
            self.assertTrue(owned)
            await asyncio.sleep(.05);started=time.monotonic();task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
            self.assertLess(time.monotonic()-started,.2)
            self.assertIsNotNone(owned[0].returncode)

    async def test_missing_engine_explicit_and_terminal_without_engine(self):
        with patch.object(pikafish,'EXE',Path('nonexistent-pikafish.exe')):
            with self.assertRaisesRegex(RuntimeError,'missing'):
                await pikafish.search(Position.initial(),dict(maxDepth=128,timeLimitMs=100))
            p=Position.initial();p=Position(p.board,p.side,0,p.keys*3)
            result=await pikafish.search(p,dict(maxDepth=128,timeLimitMs=100))
            self.assertIsNone(result['move']);self.assertEqual(result['search']['score'],0)


if __name__=='__main__':unittest.main()
