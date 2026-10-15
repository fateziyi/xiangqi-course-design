"""Reimport every experiment record and independently recompute its summary."""
import argparse
import hashlib
import json
from pathlib import Path
from backend.game import Game
from scripts.benchmark import source_hash


def verify(folder, expected, source=None):
    folder=Path(folder)
    if (folder/'INVALIDATED.json').exists():raise ValueError('Invalidated experiment')
    meta=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
    summary=json.loads((folder/'summary.json').read_text(encoding='utf-8'))
    rows=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(folder.glob('game-*.json'))]
    assert len(rows)==expected and summary['completed']==expected,'Incomplete experiment'
    assert {r['index'] for r in rows}==set(range(expected)),'Duplicate or missing indexes'
    version=source_hash()
    if source:
        base=Path(source);h=hashlib.sha256()
        for sub in ('engine','ai'):
            for p in sorted((base/sub).glob('*.py')):h.update(p.name.encode());h.update(p.read_bytes())
        version=h.hexdigest()
        for name in ('ai/search.py','engine/rules.py','engine/evaluation.py'):
            assert Path(name).read_bytes()==(base/name).read_bytes(),'Current search differs from snapshot'
    assert version==meta.get('newHash',meta.get('sourceHash')),'Different experiment source'
    tally=dict(wins=0,draws=0,losses=0,plies=0,redGames=0,blackGames=0)
    outcomes={'win':'wins','draw':'draws','loss':'losses'}
    for row in rows:
        assert 'error' not in row,row
        game=Game.from_record(row['record']);result=game.position.result()
        assert result is not None and result==row['record']['result']
        side=row.get('newSide',row.get('standardSide'))
        expected_outcome='draw' if result['winner'] is None else 'win' if result['winner']==side else 'loss'
        assert row['outcome']==expected_outcome,row['index']
        tally[outcomes[expected_outcome]]+=1
        tally['redGames' if side=='red' else 'blackGames']+=1
        tally['plies']+=len(game.moves)
        prefix=meta['openings'][row['index']//2]
        assert row['record']['moves'][:len(prefix)]==prefix
        if 'newConfig' in meta:
            assert row['record']['redAI']==meta['newConfig']==meta['oldConfig']==row['record']['blackAI']
        else:
            assert row['record'][side+'AI']==meta['standard']
            assert row['record'][('black' if side=='red' else 'red')+'AI']==meta['basic']
    for name in ('wins','draws','losses'):assert tally[name]==summary[name]
    assert summary['errors']==0
    tally['scoreRate']=(tally['wins']+.5*tally['draws'])/expected
    assert tally['scoreRate']==summary['scoreRate']
    assert tally['redGames']==tally['blackGames']==expected//2
    return dict(folder=str(folder),validated=expected,sourceHash=version,**tally)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('folder');parser.add_argument('--expected',type=int,default=40)
    parser.add_argument('--source',help='Frozen engine/ai snapshot; live search files must still match')
    args=parser.parse_args();result=verify(args.folder,args.expected,args.source)
    (Path(args.folder)/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
