"""Run only against the P0 bootstrap, before replacing the service handlers."""
import asyncio
import json
from urllib.request import urlopen
from websockets.asyncio.client import connect

async def main():
    assert '中国象棋' in urlopen('http://127.0.0.1:5173').read().decode()
    for port in (8765, 8766):
        async with connect(f'ws://127.0.0.1:{port}', proxy=None) as ws:
            await ws.send(json.dumps(dict(protocolVersion=1,type='command',requestId='p0',action='hello',payload={})))
            data=json.loads(await ws.recv())
            assert data['protocolVersion']==1
            print(port, data['type'], 'real JSON roundtrip passed')

if __name__=='__main__': asyncio.run(main())
