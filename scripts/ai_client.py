"""Independent executable AI client, no browser/game process needed."""
import asyncio
import json
import uuid
import argparse
from websockets.asyncio.client import connect
from engine.rules import Position

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='ws://127.0.0.1:8766')
    parser.add_argument('--engine',choices=('self','pikafish'),default='self')
    parser.add_argument('--time-ms',type=int,default=1500);args=parser.parse_args()
    config=dict(maxDepth=128 if args.engine=='pikafish' else 8,timeLimitMs=args.time_ms)
    if args.engine=='pikafish':config['engine']='pikafish'
    async with connect(args.url,proxy=None) as ws:
        request=dict(protocolVersion=1,type='search',requestId=str(uuid.uuid4()),gameId='cli-example',revision=0,
                     position=Position.initial().wire(),options=config)
        await ws.send(json.dumps(request))
        print(await ws.recv())

if __name__=='__main__':asyncio.run(main())
