"""Red-perspective material, phase, mobility and king-zone evaluation.

Pawn = 100. All positional terms use color-symmetric geometry. Mobility is
pseudo-legal activity, not a separate authority for legal moves. Weights are
heuristics; only measured games support a claim of playing strength.
"""
from engine.rules import in_check, pseudo_targets

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


def evaluate_v3(board):
    total=sum(SQUARE_VALUES[p][i] for i,p in enumerate(board) if p)
    # Keep these live constants outside the precomputed table for modification.
    if in_check(board,'red'):total-=CHECK_PENALTY
    if in_check(board,'black'):total+=CHECK_PENALTY
    return total


MOBILITY={4:4,5:2,6:2}
PHASE={4:2,5:4,6:2}
KING_PRESSURE={4:6,5:8,6:6}


def evaluate(board):
    total=evaluate_v3(board)
    phase=min(32,sum(PHASE.get(abs(p),0) for p in board if p))
    endgame=32-phase
    kings={1:divmod(board.index(1),9),-1:divmod(board.index(-1),9)}
    for index,piece in enumerate(board):
        if not piece:continue
        side=1 if piece>0 else -1;kind=abs(piece)
        bonus=0
        if kind in MOBILITY:
            # Horse strength grows as files open; cannons lose screens as
            # material disappears. Keep adjustments modest against material.
            if kind==4:bonus+=30*endgame//32
            if kind==6:bonus-=45*endgame//32
            kr,kc=kings[-side];mobility=pressure=0
            for target in pseudo_targets(board,index):
                occupant=board[target]
                if occupant*side>0:continue
                mobility+=1
                r,c=divmod(target,9)
                if abs(r-kr)<=1 and abs(c-kc)<=1:pressure+=1
            bonus+=MOBILITY[kind]*mobility
            bonus+=KING_PRESSURE[kind]*min(pressure,4)
        elif kind==7:
            advance=9-index//9 if side>0 else index//9
            # A pawn on the last rank can no longer advance. The v3 table
            # over-rewarded it; preserve its horizontal activity value.
            if advance==9:bonus-=55
            elif advance==8:bonus-=20
        total+=side*bonus
    return total
