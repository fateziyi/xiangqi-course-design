"""Static score from red's perspective. Pawn = 100.

All location terms mirror red/black around the horizontal river axis.
Weights are deliberately readable for the course's live modification exercise.
"""
from engine.rules import in_check

VALUES={1:0,2:200,3:200,4:420,5:900,6:450,7:100}
CHECK_PENALTY=55
GUARD_BONUS=12

def evaluate(board):
    total=0
    for i,p in enumerate(board):
        if not p:continue
        s=1 if p>0 else -1;kind=abs(p);r,c=divmod(i,9)
        advance=9-r if s==1 else r
        center=4-abs(c-4)
        value=VALUES[kind]
        if kind==7:value+=advance*8+(65 if advance>=5 else 0)+center*3
        elif kind==4:value+=center*8+min(advance,7)*5
        elif kind==5:value+=center*3+advance*2
        elif kind==6:value+=center*5+min(advance,6)*3
        elif kind in (2,3):value+=GUARD_BONUS
        elif kind==1:value-=abs(c-4)*15
        total+=s*value
    # Explicit safety term, separate from material and piece-square bonuses.
    if in_check(board,'red'):total-=CHECK_PENALTY
    if in_check(board,'black'):total+=CHECK_PENALTY
    return total
