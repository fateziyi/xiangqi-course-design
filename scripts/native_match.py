"""Four complete, paired-color games; native handicap, not human Elo evidence."""
import argparse
import asyncio
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import time
from ai.search import search
from backend.pikafish import search as native_search, EXE, NETWORK, VERSION
from backend.game import Game
from engine.rules import parse_move
from scripts.benchmark import openings

NATIVE=dict(engine='pikafish',maxDepth=128,timeLimitMs=500)
SELF=dict(maxDepth=8,timeLimitMs=1500)


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def play(index,prefix,native_side):
    async def run():
        g=Game(dict(mode='ai_ai',humanSide=None,redAI=NATIVE if native_side=='red' else SELF,
            blackAI=NATIVE if native_side=='black' else SELF));searches=[];started=time.monotonic()
        try:
            for move in prefix:g.apply(parse_move(move),human=False)
            while not g.position.result():
                side=g.position.side
                result=await native_search(g.position,NATIVE) if side==native_side else search(g.position,SELF)
                searches.append(dict(side=side,engine='pikafish' if side==native_side else 'self',**{k:v for k,v in result['search'].items() if k!='engine'}))
                g.apply(parse_move(result['move']),human=False)
            winner=g.position.result()['winner']
            return dict(index=index,nativeSide=native_side,prefixLength=len(prefix),record=g.record(),searches=searches,
                outcome='draw' if winner is None else 'win' if winner==native_side else 'loss',elapsedSeconds=time.monotonic()-started)
        except Exception as e:return dict(index=index,nativeSide=native_side,error=repr(e),record=g.record(),searches=searches)
    return asyncio.run(run())


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    out=Path(args.output)
    if out.exists():raise ValueError('Use a new output directory')
    out.mkdir(parents=True)
    prefixes=openings()[:2]
    files=['ai/search.py','engine/rules.py','engine/evaluation.py','backend/pikafish.py']
    meta=dict(native=NATIVE,self=SELF,version=VERSION,workers=2,openings=prefixes,
        hashes={p:digest(p) for p in files},binaryHash=digest(EXE),networkHash=digest(NETWORK))
    (out/'metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');rows=[]
    with ProcessPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(play,2*i+j,prefix,'red' if j==0 else 'black') for i,prefix in enumerate(prefixes) for j in range(2)]
        for future in as_completed(jobs):
            row=future.result();rows.append(row)
            (out/f"game-{row['index']:02}.json").write_text(json.dumps(row,indent=2),encoding='utf-8')
            summary=dict(completed=len(rows),wins=sum(r.get('outcome')=='win' for r in rows),
                draws=sum(r.get('outcome')=='draw' for r in rows),losses=sum(r.get('outcome')=='loss' for r in rows),errors=sum('error' in r for r in rows))
            (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary),flush=True)
    assert all(digest(p)==h for p,h in meta['hashes'].items()),'Source changed during games'


if __name__=='__main__':main()
