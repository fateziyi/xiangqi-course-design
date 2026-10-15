"""Reproducible 40-game benchmark. Every completed game is saved immediately.

Run from repository root. Uses CPU worker processes, never agent delegation.
No move cap is substituted for a ruleset result; failures are preserved.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import time
from ai.search import search
from engine.rules import Position,legal_moves,move_json,parse_move
from backend.game import Game

STANDARD=dict(maxDepth=8,timeLimitMs=1500)
BASIC=dict(maxDepth=2,timeLimitMs=500)
OUT=Path('docs/experiments')

def source_hash():
    h=hashlib.sha256()
    for folder in ['engine','ai']:
        for p in sorted(Path(folder).glob('*.py')):h.update(p.name.encode());h.update(p.read_bytes())
    return h.hexdigest()

def openings():
    data=[]
    for i in range(20):
        rng=random.Random(20261012+i);p=Position.initial();moves=[]
        for _ in range((i%5)*2):
            move=rng.choice(legal_moves(p.board,p.side));moves.append(move_json(move));p=p.play(move)
        data.append(moves)
    return data

def play(index,prefix,standard_side):
    start=time.monotonic()
    game=Game(dict(mode='ai_ai',humanSide=None,redAI=STANDARD if standard_side=='red' else BASIC,
        blackAI=STANDARD if standard_side=='black' else BASIC))
    searches=[]
    try:
        for m in prefix:game.apply(parse_move(m),human=False)
        while not game.position.result():
            side=game.position.side
            res=search(game.position,STANDARD if side==standard_side else BASIC)
            searches.append(dict(side=side,**res['search']))
            game.apply(parse_move(res['move']),human=False)
        result=game.position.result()
        return dict(index=index,standardSide=standard_side,prefixLength=len(prefix),elapsedSeconds=round(time.monotonic()-start,2),
            outcome='draw' if result['winner'] is None else 'win' if result['winner']==standard_side else 'loss',record=game.record(),searches=searches)
    except Exception as e:
        return dict(index=index,standardSide=standard_side,error=repr(e),record=game.record(),searches=searches)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=6);parser.add_argument('--output',default=str(OUT/'baseline'))
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    prefix_list=openings();version=source_hash()
    meta=dict(startedAt=datetime.now().astimezone().isoformat(),python=platform.python_version(),platform=platform.platform(),
        processor=platform.processor(),logicalCPUs=os.cpu_count(),workers=args.workers,sourceHash=version,standard=STANDARD,basic=BASIC,seed=20261012,openings=prefix_list)
    (out/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    results=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        jobs=[pool.submit(play,2*i+j,prefix,'red' if j==0 else 'black') for i,prefix in enumerate(prefix_list) for j in range(2)]
        for future in as_completed(jobs):
            result=future.result();results.append(result)
            (out/f"game-{result['index']:02}.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            summary=dict(completed=len(results),wins=sum(r.get('outcome')=='win' for r in results),draws=sum(r.get('outcome')=='draw' for r in results),
                losses=sum(r.get('outcome')=='loss' for r in results),errors=sum('error' in r for r in results),sourceHash=version)
            summary['scoreRate']=(summary['wins']+summary['draws']*.5)/len(results)
            (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
            print(json.dumps(summary),flush=True)
    assert source_hash()==version,'Sources changed during benchmark; invalidate results.'
    print('COMPLETE',flush=True)

if __name__=='__main__':main()
