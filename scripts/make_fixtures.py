"""Deterministic fixtures. Expected mate is reasoned geometrically, not generated."""
import json
from pathlib import Path
from engine.rules import Position,key,move_json

def main():
    out=[]
    for start in [18,19,20,24,25]:
        b=[0]*90
        for i,p in {4:-1,85:1,49:7,3:-5,5:-5,start:5}.items():b[i]=p
        for mirror in (False,True):
            board=[-p for p in reversed(b)] if mirror else b
            side='black' if mirror else 'red'
            move=(89-start,67) if mirror else (start,22)
            out.append(dict(id=f'rook-file-{start}-'+side,position=Position(tuple(board),side,0,(key(board,side),)).wire(),expected=move_json(move)))
    Path('fixtures').mkdir(exist_ok=True)
    Path('fixtures/mate_one.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
