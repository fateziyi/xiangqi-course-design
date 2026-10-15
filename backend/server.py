import asyncio
import json
import os
import uuid
from websockets.asyncio.server import serve
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed
from backend.game import Controller
from backend.protocol import Problem,envelope,error,ai_timeout_seconds
from engine.rules import legal_moves,parse_move


class Server:
    def __init__(self,ai_url=None):
        self.controller=Controller(); self.owner=None; self.task=None
        self.ai_url=ai_url or os.getenv('XIANGQI_AI_URL','ws://127.0.0.1:8766')

    async def send(self,data):
        if self.owner:
            try: await self.owner.send(json.dumps(data,ensure_ascii=False))
            except ConnectionClosed: pass

    async def cancel(self):
        task=self.task
        self.task=None
        if task:
            task.cancel()
            try:await task
            except asyncio.CancelledError:pass
        if self.controller.game: self.controller.game.thinking=None

    def schedule(self,rid=None):
        g=self.controller.game
        if not g or not self.owner: return
        if rid or (g.control=='running' and not g.position.result() and not g.human_turn()):
            g.thinking={'purpose':'recommend' if rid else 'move','side':g.state()['sideToMove']}
            self.task=asyncio.create_task(self.search(rid))

    async def search(self,recommend_id):
        g=self.controller.game; gid,rev=g.id,g.revision
        p=g.positions[g.display] if g.control=='replay' else g.position
        options=g.config[p.side+'AI']; request_id=str(uuid.uuid4())
        try:
            if p.result():
                response={'move':None,'search':{'completedDepth':0,'nodes':0,'elapsedMs':0,'score':0,'pv':[]}}
            else:
                async with connect(self.ai_url,proxy=None,open_timeout=1,close_timeout=.3,max_size=1048576) as ws:
                    request=dict(protocolVersion=1,type='search',requestId=request_id,gameId=gid,revision=rev,position=p.wire(),options=options)
                    await ws.send(json.dumps(request))
                    try: response=json.loads(await asyncio.wait_for(ws.recv(),ai_timeout_seconds(options)))
                    except asyncio.CancelledError:
                        await ws.send(json.dumps(dict(protocolVersion=1,type='cancel',requestId=str(uuid.uuid4()),targetRequestId=request_id)))
                        raise
                if response.get('type')=='error':
                    raise Problem('AI_TIMEOUT' if response.get('code')=='AI_TIMEOUT' else 'AI_UNAVAILABLE',
                                  response.get('message') or 'AI 服务错误')
                if response.get('type')!='search_result' or response.get('protocolVersion')!=1 or response.get('requestId')!=request_id or response.get('gameId')!=gid or response.get('revision')!=rev:
                    raise Problem('AI_INVALID_MOVE','AI 响应关联无效')
                try: move=parse_move(response.get('move'))
                except ValueError: raise Problem('AI_INVALID_MOVE','AI 返回无效走法')
                if move not in legal_moves(p.board,p.side): raise Problem('AI_INVALID_MOVE','AI 返回非法走法')
                search=response.get('search')
                if not isinstance(search,dict) or not all(k in search for k in ('completedDepth','nodes','elapsedMs','score','pv')):
                    raise Problem('AI_INVALID_MOVE','AI 搜索信息缺失')
            if self.controller.game is not g or (g.id,g.revision)!=(gid,rev): return
            g.thinking=None
            if recommend_id:
                await self.send(dict(protocolVersion=1,type='recommendation',requestId=recommend_id,gameId=gid,revision=rev,move=response['move'],search=response['search']))
            else:
                if g.control!='running': return
                g.apply(parse_move(response['move']),human=False); g.revision+=1
                self.controller.reconcile()
            await self.send(self.controller.state())
            if not recommend_id:
                await asyncio.sleep(.3)
                if self.controller.game is g and g.revision==rev+1:
                    self.task=None; self.schedule(); await self.send(self.controller.state())
        except asyncio.CancelledError: raise
        except Exception as e:
            if self.controller.game is not g or (g.id,g.revision)!=(gid,rev): return
            g.thinking=None
            if not recommend_id or g.control=='running':
                g.control='paused'
            g.revision+=1
            code=e.code if isinstance(e,Problem) else ('AI_TIMEOUT' if isinstance(e,TimeoutError) else 'AI_UNAVAILABLE')
            await self.send(error(recommend_id,code,str(e) or 'AI 响应超时，可点击继续重试'))
            await self.send(self.controller.state())

    async def handler(self,ws):
        if self.owner:
            await ws.send(json.dumps(error(None,'CONTROL_BUSY','已有控制连接，请先关闭原页面')))
            await ws.close(); return
        self.owner=ws; seen=set()
        try:
            async for raw in ws:
                rid=None
                try:
                    request=envelope(raw); rid=request['requestId']
                    if rid in seen: raise Problem('DUPLICATE_REQUEST','此 requestId 已处理')
                    seen.add(rid)
                    if request.get('type')!='command': raise Problem('UNSUPPORTED_TYPE','仅接收 command 消息')
                    response,changed=self.controller.dispatch(request)
                    if changed: await self.cancel()
                    if response: await self.send(response)
                    if changed or response is None:
                        self.schedule(rid if response is None else None)
                        await self.send(self.controller.state())
                except (ValueError,TypeError,KeyError,RecursionError) as e:
                    await self.send(error(rid,'INVALID_MESSAGE',str(e)))
                except Problem as e:
                    await self.send(error(rid,e.code,str(e)))
                    if e.code=='STALE_STATE': await self.send(self.controller.state())
        except ConnectionClosed: pass
        finally:
            await self.cancel()
            g=self.controller.game
            if g:
                if g.control=='running': g.control='paused'
                g.revision+=1
            self.owner=None


async def main():
    server=Server()
    port=int(os.getenv('XIANGQI_GAME_PORT','8765'))
    import re
    origins=[None,re.compile(r'http://(127\.0\.0\.1|localhost):\d+')]
    async with serve(server.handler,'127.0.0.1',port,origins=origins,max_size=1048576):
        print(f'Game ws://127.0.0.1:{port}',flush=True)
        await asyncio.Future()

if __name__=='__main__': asyncio.run(main())
