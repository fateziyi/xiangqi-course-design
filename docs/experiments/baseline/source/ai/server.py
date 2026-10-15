import asyncio
import json
import os
import sys
from pathlib import Path
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed
from backend.protocol import envelope,error,Problem,options
from engine.rules import parse_position

ROOT=Path(__file__).resolve().parents[1]

class AIService:
    def __init__(self):self.busy=False

    async def compute(self,ws,request):
        proc=None
        try:
            flags={'creationflags':0x08000000} if sys.platform=='win32' else {}
            proc=await asyncio.create_subprocess_exec(sys.executable,'-m','ai.worker',cwd=ROOT,
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,**flags)
            raw=json.dumps(dict(position=request['position'],options=request['options'])).encode()
            stdout,stderr=await asyncio.wait_for(proc.communicate(raw),request['options']['timeLimitMs']/1000+1.2)
            if proc.returncode:raise RuntimeError('搜索工作进程失败')
            result=json.loads(stdout)
            await ws.send(json.dumps(dict(protocolVersion=1,type='search_result',requestId=request['requestId'],
                gameId=request['gameId'],revision=request['revision'],**result)))
        except asyncio.CancelledError:raise
        except (RuntimeError,ValueError,TimeoutError) as e:
            try:await ws.send(json.dumps(error(request['requestId'],'AI_TIMEOUT' if isinstance(e,TimeoutError) else 'AI_UNAVAILABLE',str(e))))
            except ConnectionClosed:pass
        except ConnectionClosed:pass
        finally:
            if proc and proc.returncode is None:
                proc.terminate();await proc.wait()
            self.busy=False

    async def handler(self,ws):
        task=None;target=None;seen=set()
        try:
            async for raw in ws:
                rid=None
                try:
                    data=envelope(raw);rid=data['requestId']
                    if rid in seen:raise Problem('DUPLICATE_REQUEST','重复 requestId')
                    seen.add(rid)
                    if data.get('type')=='cancel':
                        if not isinstance(data.get('targetRequestId'),str):raise ValueError('targetRequestId 无效')
                        if task and target==data['targetRequestId']:
                            task.cancel()
                            try:await task
                            except asyncio.CancelledError:pass
                            task=None
                        await ws.send(json.dumps(dict(protocolVersion=1,type='ack',requestId=rid)))
                    elif data.get('type')=='search':
                        parse_position(data.get('position'));options(data.get('options'))
                        if not isinstance(data.get('gameId'),str) or not 1<=len(data['gameId'])<=128 or type(data.get('revision')) is not int or data['revision']<0:
                            raise ValueError('搜索关联字段无效')
                        if self.busy:raise Problem('CONTROL_BUSY','AI 正在搜索，请稍后重试')
                        self.busy=True;target=rid;task=asyncio.create_task(self.compute(ws,data))
                    else:raise Problem('UNSUPPORTED_TYPE','仅接收 search/cancel')
                except Problem as e:await ws.send(json.dumps(error(rid,e.code,str(e))))
                except (ValueError,TypeError,KeyError,RecursionError) as e:await ws.send(json.dumps(error(rid,'INVALID_MESSAGE',str(e))))
        except ConnectionClosed:pass
        finally:
            if task and not task.done():
                task.cancel()
                try:await task
                except asyncio.CancelledError:pass

async def main():
    service=AIService();port=int(os.getenv('XIANGQI_AI_PORT','8766'))
    async with serve(service.handler,'127.0.0.1',port,origins=[None],max_size=1048576):
        print(f'AI ws://127.0.0.1:{port}',flush=True)
        await asyncio.Future()

if __name__=='__main__':asyncio.run(main())
