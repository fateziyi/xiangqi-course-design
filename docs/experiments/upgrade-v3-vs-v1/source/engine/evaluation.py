"""Static red-perspective evaluation. Precomputed squares preserve v1 weights.

The upgrade addresses tactical horizon errors in search rather than claiming
unvalidated strength from arbitrary weight changes. Pawn = 100.
"""
from engine.rules import in_check

VALUES={1:0,2:200,3:200,4:420,5:900,6:450,7:100}
CHECK_PENALTY=55
GUARD_BONUS=12


def square_value(kind, advance, center):
    value=VALUES[kind]
    if kind==7:value+=advance*8+(65 if advance>=5 else 0)+center*3
    elif kind==4:value+=center*8+min(advance,7)*5
    elif kind==5:value+=center*3+advance*2
    elif kind==6:value+=center*5+min(advance,6)*3
    elif kind in (2,3):value+=GUARD_BONUS
    elif kind==1:value-=(4-center)*15
    return value


SQUARE_VALUES = {
    piece: tuple((1 if piece>0 else -1)*square_value(
        abs(piece),9-i//9 if piece>0 else i//9,4-abs(i%9-4)) for i in range(90))
    for piece in list(range(-7,0))+list(range(1,8))
}


def evaluate(board):
    total=sum(SQUARE_VALUES[p][i] for i,p in enumerate(board) if p)
    # Keep these live constants outside the precomputed table for modification.
    if in_check(board,'red'):total-=CHECK_PENALTY
    if in_check(board,'black'):total+=CHECK_PENALTY
    return total
