"""Real sockets on ephemeral loopback ports; no UI ownership interference."""
import asyncio
import json
import time
import unittest
import uuid
from websockets.asyncio.server import serve
from websockets.asyncio.client import connect
from backend.server import Server
from ai.server import AIService
from engine.rules import Position,parse_move,legal_moves
from tests.test_game import CONFIG

class Client:
    def __init__(self,ws):self.ws=ws;self.state=None
    async def recv(self,kind=None,predicate=None,timeout=8):
        async def read():
            while True:
                msg=json.loads(await self.ws.recv())
                if msg['type']=='state':self.state=msg
                if (not kind or msg['type']==kind) and (not predicate or predicate(msg)):return msg
        return await asyncio.wait_for(read(),timeout)
    async def send(self,action,payload=None,request_id=None,revision=None):
        g=self.state and self.state['game']
        req=dict(protocolVersion=1,type='command',requestId=request_id or str(uuid.uuid4()),action=action,
            gameId=g['gameId'] if g else None,revision=(g['revision'] if g else None) if revision is None else revision,payload=payload or {})
        await self.ws.send(json.dumps(req));return req
    async def change(self,action,payload=None):
        req=await self.send(action,payload)
        reply=await self.recv(predicate=lambda m:m.get('requestId')==req['requestId'])
        if reply['type']=='error':raise AssertionError(reply)
        return await self.recv('state')

class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_mixed_100_plies_and_v2_record(self):
        c=self.c;total=0;games=0
        native=dict(engine='pikafish',maxDepth=128,timeLimitMs=500)
        basic=dict(maxDepth=2,timeLimitMs=100)
        while total<100:
            await c.change('new_game',{**CONFIG,'mode':'ai_ai','redAI':native if games%2==0 else basic,
                'blackAI':basic if games%2==0 else native})
            last=0
            while total<100 and c.state['game']['status']!='finished':
                msg=await c.recv('state',timeout=8)
                new=msg['game']['historyLength']
                total+=new-last;last=new
            if c.state['game']['status']!='finished':await c.change('pause')
            await c.send('export_record');record=(await c.recv('record'))['record']
            self.assertEqual(record['version'],2)
            from backend.game import Game
            self.assertEqual(Game.from_record(record).record(),record)
            games+=1
        await c.change('import_record',{'record':record})
        self.assertEqual(c.state['game']['control'],'replay')
        self.assertTrue(any(c.state['game'][s+'AI'].get('engine')=='pikafish' for s in ('red','black')))
        print(f'Native/self mixed real WebSocket: {total} legal plies across {games} game(s)')

    async def test_native_service_cancel_and_disconnect(self):
        from unittest.mock import patch
        owned=[];original=asyncio.create_subprocess_exec
        async def spawn(*args,**kwargs):
            proc=await original(*args,**kwargs);owned.append(proc);return proc
        async def request(ws,rid):
            await ws.send(json.dumps(dict(protocolVersion=1,type='search',requestId=rid,gameId='native-cancel',revision=0,
                position=Position.initial().wire(),options=dict(engine='pikafish',maxDepth=128,timeLimitMs=10000))))
        with patch('backend.pikafish.asyncio.create_subprocess_exec',spawn):
            async with connect(self.aiurl,proxy=None) as ws:
                await request(ws,'native-1')
                for _ in range(200):
                    if owned:break
                    await asyncio.sleep(.005)
                self.assertTrue(owned)
                started=time.monotonic()
                await ws.send(json.dumps(dict(protocolVersion=1,type='cancel',requestId='native-stop',targetRequestId='native-1')))
                reply=json.loads(await asyncio.wait_for(ws.recv(),1))
                self.assertEqual(reply['type'],'ack');self.assertLess(time.monotonic()-started,.2)
                self.assertIsNotNone(owned[0].returncode)
                await request(ws,'native-2')
                for _ in range(200):
                    if len(owned)==2:break
                    await asyncio.sleep(.005)
                self.assertEqual(len(owned),2)
            for _ in range(200):
                if self.ai.job.done():break
                await asyncio.sleep(.005)
            self.assertTrue(self.ai.job.done());self.assertIsNotNone(owned[1].returncode)

    async def asyncSetUp(self):
        self.ai=AIService();self.ais=await serve(self.ai.handler,'127.0.0.1',0)
        aiport=self.ais.sockets[0].getsockname()[1]
        self.aiurl=f'ws://127.0.0.1:{aiport}'
        self.server=Server(self.aiurl)
        self.gs=await serve(self.server.handler,'127.0.0.1',0)
        self.url=f'ws://127.0.0.1:{self.gs.sockets[0].getsockname()[1]}'
        self.ws=await connect(self.url,proxy=None);self.c=Client(self.ws)
        await self.c.send('hello');await self.c.recv('state')

    async def asyncTearDown(self):
        await self.ws.close();self.gs.close();await self.gs.wait_closed()
        self.ais.close();await self.ais.wait_closed()

    async def test_modes_and_human_game(self):
        c=self.c
        await c.change('new_game',CONFIG)
        for f,t in [(82,63),(1,18),(63,82),(18,1)]*2:await c.change('move',{'from':f,'to':t})
        self.assertEqual(c.state['game']['result']['reason'],'threefold')
        self.assertEqual(c.state['stats']['draws'],1)
        for side in ('red','black'):
            await c.change('new_game',{**CONFIG,'mode':'human_ai','humanSide':side})
            if side=='red':await c.change('move',{'from':54,'to':45})
            await c.recv('state',lambda m:m['game']['historyLength']==(2 if side=='red' else 1))
            self.assertEqual(c.state['game']['sideToMove'],side)
            await c.change('undo',{'scope':'human_turn'}) if side=='red' else await c.change('pause')

    async def test_duplicate_invalid_stale_owner_and_record(self):
        c=self.c;await c.change('new_game',CONFIG)
        await self.ws.send('not json');self.assertEqual((await c.recv('error'))['code'],'INVALID_MESSAGE')
        await self.ws.send(b'{}');self.assertEqual((await c.recv('error'))['code'],'INVALID_MESSAGE')
        req=await c.send('move',{'from':54,'to':45});await c.recv('ack');await c.recv('state')
        await self.ws.send(json.dumps(req));self.assertEqual((await c.recv('error'))['code'],'DUPLICATE_REQUEST')
        await c.send('move',{'from':27,'to':36},revision=0);self.assertEqual((await c.recv('error'))['code'],'STALE_STATE');await c.recv('state')
        async with connect(self.url,proxy=None) as second:self.assertEqual(json.loads(await second.recv())['code'],'CONTROL_BUSY')
        await c.send('export_record');record=(await c.recv('record'))['record']
        before=c.state['game']['board']
        bad={**record,'moves':[{'from':54,'to':0}]}
        await c.send('import_record',{'record':bad});self.assertEqual((await c.recv('error'))['code'],'INVALID_RECORD')
        self.assertEqual(before,self.server.controller.game.state()['board'])
        await c.change('import_record',{'record':record})
        self.assertEqual(c.state['game']['control'],'replay');self.assertEqual(c.state['stats']['redWins'],0)
        await c.change('seek_replay',{'ply':0});await c.change('continue_from_replay')
        self.assertEqual(c.state['game']['control'],'paused')

    async def test_recommend_cancel_and_new_game(self):
        c=self.c;await c.change('new_game',CONFIG)
        before=c.state['game']['board']
        await c.send('recommend');rec=await c.recv('recommendation')
        self.assertEqual(rec['gameId'],c.state['game']['gameId'])
        self.assertIn(parse_move(rec['move']),legal_moves(Position.initial().board,'red'))
        await c.recv('state');self.assertEqual(c.state['game']['board'],before)
        strong=dict(maxDepth=12,timeLimitMs=10000)
        await c.change('new_game',{**CONFIG,'mode':'ai_ai','redAI':strong,'blackAI':strong})
        await asyncio.sleep(.1)
        start=time.monotonic();await c.change('pause')
        self.assertLess(time.monotonic()-start,.2)
        ply=c.state['game']['historyLength'];await asyncio.sleep(.25)
        self.assertEqual(self.server.controller.game.state()['historyLength'],ply)
        await c.change('new_game',{**CONFIG,'mode':'human_ai','humanSide':'black'})
        await c.recv('state',lambda m:m['game']['historyLength']==1)
        self.assertEqual(c.state['game']['sideToMove'],'black')

    async def test_disconnect_restore(self):
        c=self.c;await c.change('new_game',CONFIG);gid=c.state['game']['gameId']
        await self.ws.close();await asyncio.sleep(.05)
        self.ws=await connect(self.url,proxy=None);self.c=Client(self.ws)
        await self.c.send('hello');msg=await self.c.recv('state')
        self.assertEqual(msg['game']['gameId'],gid);self.assertEqual(msg['game']['control'],'paused')

    async def test_ai_error_is_paused(self):
        self.server.ai_url='ws://127.0.0.1:1'
        await self.c.change('new_game',{**CONFIG,'mode':'human_ai','humanSide':'black'})
        msg=await self.c.recv('error');self.assertIn(msg['code'],('AI_UNAVAILABLE','AI_TIMEOUT'))
        await self.c.recv('state');self.assertEqual(self.c.state['game']['control'],'paused')
        self.assertEqual(self.c.state['game']['historyLength'],0)

    async def test_100_ai_plies(self):
        fast=dict(maxDepth=2,timeLimitMs=100)
        total=0;games=0;c=self.c
        while total<100:
            await c.change('new_game',{**CONFIG,'mode':'ai_ai','redAI':fast,'blackAI':dict(maxDepth=1,timeLimitMs=100)})
            games+=1;previous=0
            while total<100:
                msg=await c.recv('state',lambda m:m['game']['historyLength']>previous,timeout=10)
                ply=msg['game']['historyLength'];total+=ply-previous;previous=ply
                if msg['game']['status']=='finished':break
        if c.state['game']['status']!='finished':await c.change('pause')
        self.assertGreaterEqual(total,100)
        print(f'\nAI vs AI real WebSocket: {total} legal plies across {games} game(s)')

    async def test_direct_ai_cancel_and_validation(self):
        async with connect(self.aiurl,proxy=None) as ws:
            await ws.send(json.dumps(dict(protocolVersion=1,type='unknown',requestId='bad')))
            self.assertEqual(json.loads(await ws.recv())['code'],'UNSUPPORTED_TYPE')
            request=dict(protocolVersion=1,type='search',requestId='search-a',gameId='direct',revision=0,
                position=Position.initial().wire(),options=dict(maxDepth=12,timeLimitMs=10000))
            await ws.send(json.dumps(request))
            await ws.send(json.dumps(dict(protocolVersion=1,type='cancel',requestId='cancel-a',targetRequestId='search-a')))
            msg=json.loads(await ws.recv());self.assertEqual(msg['type'],'ack')
            request['requestId']='search-b';request['options']=dict(maxDepth=1,timeLimitMs=100)
            await ws.send(json.dumps(request));msg=json.loads(await ws.recv())
            self.assertEqual(msg['type'],'search_result');self.assertEqual(msg['requestId'],'search-b')
            request['requestId']='invalid';request['position']['board']=[0]*90
            await ws.send(json.dumps(request));self.assertEqual(json.loads(await ws.recv())['code'],'INVALID_MESSAGE')

    async def test_ai_illegal_and_timeout_responses(self):
        for behavior in ('illegal','timeout'):
            async def fake(ws):
                req=json.loads(await ws.recv())
                if behavior=='timeout':await asyncio.sleep(2.1);return
                await ws.send(json.dumps(dict(protocolVersion=1,type='search_result',requestId=req['requestId'],
                    gameId=req['gameId'],revision=req['revision'],move={'from':54,'to':0},search={})))
            service=await serve(fake,'127.0.0.1',0)
            try:
                self.server.ai_url=f"ws://127.0.0.1:{service.sockets[0].getsockname()[1]}"
                cfg={**CONFIG,'mode':'human_ai','humanSide':'black','redAI':dict(maxDepth=1,timeLimitMs=100)}
                await self.c.change('new_game',cfg)
                msg=await self.c.recv('error');self.assertEqual(msg['code'],'AI_TIMEOUT' if behavior=='timeout' else 'AI_INVALID_MOVE')
                await self.c.recv('state');self.assertEqual(self.c.state['game']['historyLength'],0)
                self.assertEqual(self.c.state['game']['control'],'paused')
            finally:service.close();await service.wait_closed()

    async def test_replay_recommend_and_export(self):
        c=self.c;await c.change('new_game',CONFIG);await c.change('move',{'from':54,'to':45})
        await c.change('enter_replay',{'ply':0});await c.send('recommend')
        msg=await c.recv('recommendation');self.assertIsNotNone(msg['move']);await c.recv('state')
        self.assertEqual(c.state['game']['displayPly'],0);self.assertEqual(c.state['game']['historyLength'],1)
        await c.send('export_record');record=(await c.recv('record'))['record'];self.assertEqual(len(record['moves']),1)
        await c.change('exit_replay');self.assertEqual(c.state['game']['control'],'paused')

    async def test_replay_recommend_failure_preserves_node(self):
        c=self.c;await c.change('new_game',CONFIG)
        await c.change('move',{'from':54,'to':45})
        await c.change('enter_replay',{'ply':0})
        before=c.state['game']
        self.server.ai_url='ws://127.0.0.1:1'
        await c.send('recommend');await c.recv('error');await c.recv('state')
        after=c.state['game']
        for field in ('control','displayPly','historyLength','board','lastMove','sideToMove'):
            self.assertEqual(after[field],before[field],field)
        # Failure must not prevent navigating or exporting the original history.
        await c.change('seek_replay',{'ply':1})
        await c.send('export_record')
        self.assertEqual((await c.recv('record'))['record']['moves'],[{'from':54,'to':45}])

    async def test_native_slow_start_keeps_full_search_budget(self):
        from unittest.mock import patch
        original=asyncio.create_subprocess_exec
        async def delayed_spawn(*args,**kwargs):
            proc=await original(*args,**kwargs)
            read=proc.stdout.readline
            async def readline():
                raw=await read()
                if raw.strip()==b'readyok':await asyncio.sleep(1.6)
                return raw
            proc.stdout.readline=readline
            return proc
        with patch('backend.pikafish.asyncio.create_subprocess_exec',delayed_spawn):
            native=dict(engine='pikafish',maxDepth=128,timeLimitMs=500)
            await self.c.change('new_game',{**CONFIG,'mode':'human_ai','humanSide':'black','redAI':native})
            await self.c.recv('state',lambda m:m['game']['historyLength']==1,timeout=8)
            self.assertEqual(self.c.state['game']['control'],'running')

if __name__=='__main__':unittest.main()
