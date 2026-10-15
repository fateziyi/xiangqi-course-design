import copy
import unittest
from backend.game import Game,Controller
from backend.protocol import Problem
from engine.rules import Position,key

CONFIG=dict(mode='human_human',humanSide=None,redAI=dict(maxDepth=4,timeLimitMs=1500),blackAI=dict(maxDepth=2,timeLimitMs=500))

class GameTests(unittest.TestCase):
    def test_human_and_atomic_invalid(self):
        g=Game(CONFIG)
        g.command('move',{'from':54,'to':45})
        self.assertEqual(g.position.side,'black');self.assertEqual(g.revision,1)
        before=g.record()
        with self.assertRaises(Problem):g.command('move',{'from':45,'to':36})
        self.assertEqual(g.record(),before)

    def test_undo_replay_record(self):
        g=Game(CONFIG)
        for f,t in [(54,45),(27,36),(82,63)]:g.command('move',{'from':f,'to':t})
        record=g.record(); imported=Game.from_record(record)
        self.assertEqual(imported.positions,g.positions);self.assertEqual(imported.record(),record)
        for i in range(4):
            imported.command('seek_replay',{'ply':i})
            self.assertEqual(imported.state()['board'],list(g.positions[i].board))
        g.command('undo',{'scope':'ply'});self.assertEqual(len(g.moves),2);self.assertEqual(g.control,'paused')
        g.command('enter_replay',{'ply':1});g.command('continue_from_replay',{})
        self.assertEqual(len(g.moves),1);self.assertEqual(g.control,'paused')
        imported.command('seek_replay',{'ply':2});old=imported.id
        imported.command('continue_from_replay',{})
        self.assertNotEqual(old,imported.id);self.assertFalse(imported.imported)

    def test_human_round(self):
        for side in ['red','black']:
            config={**CONFIG,'mode':'human_ai','humanSide':side};g=Game(config)
            for m in [(54,45),(27,36),(82,63)][:1 if side=='red' else 2]:g.apply(m,human=False)
            g.command('undo',{'scope':'human_turn'})
            self.assertEqual(len(g.moves),0 if side=='red' else 1)
        g=Game({**CONFIG,'mode':'human_ai','humanSide':'red'})
        g.apply((54,45));g.apply((27,36),human=False);g.command('undo',{'scope':'human_turn'})
        self.assertEqual(g.position,Position.initial())

    def test_import_exit_then_resume_creates_new_identity(self):
        g=Game(CONFIG);g.apply((54,45))
        imported=Game.from_record(g.record());old=imported.id
        imported.command('exit_replay',{});imported.command('resume',{})
        self.assertNotEqual(imported.id,old);self.assertFalse(imported.imported)
        imported.command('move',{'from':27,'to':36})
        self.assertEqual(len(imported.moves),2)

    def test_invalid_records(self):
        g=Game(CONFIG);record=g.record()
        for field,value in [('version',True),('ruleset','other'),('createdAt','2026-01-01'),('moves',[{'from':54,'to':0}]),('result',{'winner':'red','reason':'checkmate'})]:
            bad=copy.deepcopy(record);bad[field]=value
            with self.assertRaises(Problem,msg=field):Game.from_record(bad)
        c=Controller();c.game=g
        bad={**record,'moves':[{'from':54,'to':0}]}
        with self.assertRaises(Problem):c.dispatch(dict(action='import_record',payload={'record':bad},requestId='x',gameId=g.id,revision=0))
        self.assertIs(c.game,g)

    def test_draw_statistics_retract(self):
        c=Controller();c.game=g=Game(CONFIG)
        for f,t in [(82,63),(1,18),(63,82),(18,1)]*2:
            g.command('move',{'from':f,'to':t});c.reconcile()
        self.assertEqual(c.stats()['draws'],1);c.reconcile();self.assertEqual(c.stats()['draws'],1)
        g.command('enter_replay',{'ply':0});c.reconcile();self.assertEqual(c.stats()['draws'],1)
        g.command('exit_replay',{});g.command('undo',{'scope':'ply'});c.reconcile();self.assertEqual(c.stats()['draws'],0)

    def test_wins_statistics(self):
        for winner in ['red','black']:
            b=[0]*90
            for i,p in {4:-1,85:1,49:7,13:5,12:5,14:5}.items():b[i]=p
            if winner=='black':b=[-p for p in reversed(b)]
            side='black' if winner=='red' else 'red'
            c=Controller();c.game=g=Game(CONFIG)
            g.positions=[Position(tuple(b),side,0,(key(b,side),))]
            c.reconcile();c.reconcile()
            self.assertEqual(c.stats()[winner+'Wins'],1)

    def test_revision_and_stale(self):
        c=Controller();c.game=g=Game(CONFIG)
        with self.assertRaises(Problem):c.validate_version(dict(gameId=g.id,revision=True))
        g.command('move',{'from':54,'to':45});g.command('undo',{'scope':'ply'})
        self.assertEqual(g.revision,2)
        with self.assertRaises(Problem):c.validate_version(dict(gameId=g.id,revision=0))

if __name__=='__main__':unittest.main()
