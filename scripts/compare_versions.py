"""Matched-budget old/new games and record review; preserves all outcomes."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import time
import types
from ai.search import search
from backend.game import Game
from engine.rules import parse_move
from scripts.benchmark import openings, source_hash

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'docs/experiments/pre-upgrade-v1/source'
CONFIG = dict(maxDepth=8, timeLimitMs=1500)


def configure(old_source, config):
    global OLD, CONFIG
    OLD = Path(old_source).resolve()
    CONFIG = config


def legacy():
    if 'legacy_search' not in sys.modules:
        package = types.ModuleType('legacy_engine'); package.__path__ = [str(OLD/'engine')]
        sys.modules['legacy_engine'] = package
        for name, path in [('legacy_engine.rules', OLD/'engine/rules.py'),
                           ('legacy_engine.evaluation', OLD/'engine/evaluation.py'),
                           ('legacy_search', OLD/'ai/search.py')]:
            module = types.ModuleType(name); module.__file__ = str(path)
            sys.modules[name] = module
            code = path.read_text(encoding='utf-8-sig').replace('from engine.', 'from legacy_engine.')
            exec(compile(code, str(path), 'exec'), module.__dict__)
    return sys.modules['legacy_search'].search, sys.modules['legacy_engine.rules'].parse_position


def old_search(position):
    fn, parser = legacy()
    return fn(parser(position.wire()), CONFIG)


def review_one(record, ply):
    game = Game.from_record(record); p = game.positions[ply]
    before = p.wire()
    old = old_search(p); new = search(p, CONFIG)
    assert p.wire() == before
    return dict(plyBefore=ply, played=record['moves'][ply], old=old, new=new)


def play(index, prefix, new_side):
    start = time.monotonic()
    game = Game(dict(mode='ai_ai', humanSide=None, redAI=CONFIG, blackAI=CONFIG))
    searches = []
    try:
        for move in prefix: game.apply(parse_move(move), human=False)
        while not game.position.result():
            side = game.position.side
            answer = search(game.position, CONFIG) if side == new_side else old_search(game.position)
            searches.append(dict(side=side, version='new' if side==new_side else 'old', **answer['search']))
            game.apply(parse_move(answer['move']), human=False)
        result = game.position.result()
        return dict(index=index, newSide=new_side, prefixLength=len(prefix),
                    outcome='draw' if result['winner'] is None else 'win' if result['winner']==new_side else 'loss',
                    elapsedSeconds=round(time.monotonic()-start, 2), record=game.record(), searches=searches)
    except Exception as e:
        return dict(index=index, newSide=new_side, error=repr(e), record=game.record(), searches=searches)


def snapshot_hash():
    h=hashlib.sha256()
    for folder in ['engine','ai']:
        for p in sorted((OLD/folder).glob('*.py')): h.update(p.name.encode());h.update(p.read_bytes())
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--record'); parser.add_argument('--games', type=int, default=40)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--old-source', default=str(OLD))
    parser.add_argument('--time-ms', type=int, default=1500)
    parser.add_argument('--depth', type=int, default=8)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(); out=Path(args.output)
    if not 100<=args.time_ms<=10000 or not 1<=args.depth<=12:raise ValueError('Invalid search budget')
    configure(args.old_source,dict(maxDepth=args.depth,timeLimitMs=args.time_ms))
    if out.exists() and any(out.glob('game-*.json')): raise RuntimeError('Use a fresh output directory')
    out.mkdir(parents=True, exist_ok=True)
    version = source_hash()
    if args.record:
        record=json.loads(Path(args.record).read_text(encoding='utf-8')); Game.from_record(record)
        with ProcessPoolExecutor(max_workers=args.workers, initializer=configure, initargs=(str(OLD),CONFIG)) as pool:
            jobs=[pool.submit(review_one,record,i) for i in range(len(record['moves']))
                  if (i%2==0) == (record['humanSide']=='black')]
            rows=[]
            for future in as_completed(jobs):
                row=future.result();rows.append(row)
                print('review',row['plyBefore']+1,'played',row['played'],'new',row['new']['move'],flush=True)
        (out/'review.json').write_text(json.dumps(dict(recordSource=args.record,config=CONFIG,
            oldSource=str(OLD),oldHash=snapshot_hash(),newHash=version,positions=sorted(rows,key=lambda r:r['plyBefore'])),
            ensure_ascii=False,indent=2),encoding='utf-8')
    else:
        if args.games<2 or args.games>40 or args.games%2: raise ValueError('games must be even, 2..40')
        prefixes=openings()[:args.games//2]
        (out/'metadata.json').write_text(json.dumps(dict(startedAt=datetime.now().astimezone().isoformat(),
            python=platform.python_version(),platform=platform.platform(),logicalCPUs=os.cpu_count(),
            workers=args.workers,oldSource=str(OLD),oldHash=snapshot_hash(),newHash=version,oldConfig=CONFIG,newConfig=CONFIG,
            seed=20261012,openings=prefixes),ensure_ascii=False,indent=2),encoding='utf-8')
        results=[]
        with ProcessPoolExecutor(max_workers=args.workers, initializer=configure, initargs=(str(OLD),CONFIG)) as pool:
            jobs=[pool.submit(play,2*i+j,prefix,'red' if j==0 else 'black')
                  for i,prefix in enumerate(prefixes) for j in range(2)]
            for future in as_completed(jobs):
                result=future.result();results.append(result)
                (out/f"game-{result['index']:02}.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
                summary=dict(completed=len(results),wins=sum(r.get('outcome')=='win' for r in results),
                    draws=sum(r.get('outcome')=='draw' for r in results),losses=sum(r.get('outcome')=='loss' for r in results),
                    errors=sum('error' in r for r in results),oldHash=snapshot_hash(),newHash=version)
                summary['scoreRate']=(summary['wins']+summary['draws']*.5)/len(results)
                (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
                print(json.dumps(summary),flush=True)
    assert source_hash()==version, 'Sources changed during experiment; invalidate results'


if __name__ == '__main__': main()
