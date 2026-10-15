"""Budgeted Negamax/PVS with quiescence and history-safe request-local caches."""
from collections import Counter
import time
from engine.rules import legal_moves, sign, move_json, in_check
from engine.evaluation import evaluate, VALUES

MATE = 100000
MAX_PLY = 64
Q_DEPTH = 8
CACHE_LIMIT = 30000


class BudgetExpired(Exception):
    pass


class Search:
    def __init__(self, deadline):
        self.deadline = deadline
        self.nodes = 0
        self.tt = {}
        self.best_moves = {}
        self.move_cache = {}
        self.eval_cache = {}
        self.killers = {}
        self.history = {}

    def check(self):
        if time.monotonic() >= self.deadline:
            raise BudgetExpired()

    def moves(self, p, captures=False, existence=False):
        cache_key = (p.board, p.side, captures, existence)
        if cache_key not in self.move_cache:
            if len(self.move_cache) >= CACHE_LIMIT:
                self.move_cache.clear()
            full = self.move_cache.get((p.board, p.side, False, False))
            if full is not None:
                selected = tuple(m for m in full if p.board[m[1]]) if captures else full
                self.move_cache[cache_key] = selected[:1] if existence else selected
            else:
                self.move_cache[cache_key] = tuple(legal_moves(
                    p.board, p.side, captures_only=captures, limit=1 if existence else None))
        return self.move_cache[cache_key]

    def static(self, p):
        if p.board not in self.eval_cache:
            if len(self.eval_cache) >= CACHE_LIMIT:
                self.eval_cache.clear()
            self.eval_cache[p.board] = evaluate(p.board)
        return sign(p.side) * self.eval_cache[p.board]

    @staticmethod
    def context_key(p):
        # Exact equality, not only a board hash. Multiplicities matter for draws.
        return (p.board, p.side, p.no_capture, frozenset(Counter(p.keys).items()))

    @staticmethod
    def terminal(p, moves, ply):
        # Checkmate/stalemate always takes precedence over draw thresholds.
        if not moves:
            return -MATE + ply
        if p.no_capture >= 120 or (p.keys and p.keys.count(p.keys[-1]) >= 3):
            return 0
        return None

    def ordered(self, p, moves, preferred=None, ply=0):
        killers = self.killers.get(ply, ())
        def rank(move):
            if move == preferred:
                return 10000000
            victim = p.board[move[1]]
            if victim:
                return 1000000 + 16 * VALUES[abs(victim)] - VALUES[abs(p.board[move[0]])]
            if move in killers:
                return 900000 - killers.index(move)
            return self.history.get((p.side, move), 0)
        return sorted(moves, key=rank, reverse=True)

    def quiescence(self, p, alpha, beta, ply, remaining=Q_DEPTH):
        self.check()
        self.nodes += 1
        if ply >= MAX_PLY:
            # Abort this iteration rather than stand pat while in check.
            raise BudgetExpired()
        checked = in_check(p.board, p.side)
        moves = self.moves(p) if checked else self.moves(p, captures=True)
        has_moves = moves or self.moves(p, existence=True)
        terminal = self.terminal(p, has_moves, ply)
        if terminal is not None:
            return terminal, []
        if checked:
            best, line = -MATE * 2, []
        else:
            best, line = self.static(p), []
            if best >= beta or remaining <= 0:
                return best, line
            alpha = max(alpha, best)
        for move in self.ordered(p, moves, ply=ply):
            value, pv = self.quiescence(p.play(move, validate=False), -beta, -alpha,
                                        ply + 1, remaining - 1)
            value = -value
            if value > best:
                best, line = value, [move] + pv
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return best, line

    def negamax(self, p, depth, alpha, beta, ply, preferred=None):
        self.check()
        if depth <= 0:
            return self.quiescence(p, alpha, beta, ply)
        self.nodes += 1
        if ply >= MAX_PLY:
            raise BudgetExpired()
        moves = self.moves(p)
        terminal = self.terminal(p, moves, ply)
        if terminal is not None:
            return terminal, []
        context = self.context_key(p)
        entry = self.tt.get(context)
        original_alpha = alpha
        if entry and entry[0] >= depth:
            _, stored, flag, cached_line = entry
            value = stored - ply if stored > MATE - MAX_PLY else stored + ply if stored < -MATE + MAX_PLY else stored
            if flag == 'exact' or (flag == 'lower' and value >= beta) or (flag == 'upper' and value <= alpha):
                return value, list(cached_line)
        preferred = preferred or self.best_moves.get((p.board, p.side))
        best, line = -MATE * 2, []
        for index, move in enumerate(self.ordered(p, moves, preferred, ply)):
            child = p.play(move, validate=False)
            if index == 0:
                value, pv = self.negamax(child, depth - 1, -beta, -alpha, ply + 1)
                value = -value
            else:
                value, pv = self.negamax(child, depth - 1, -alpha - 1, -alpha, ply + 1)
                value = -value
                if alpha < value < beta:
                    value, pv = self.negamax(child, depth - 1, -beta, -alpha, ply + 1)
                    value = -value
            if value > best:
                best, line = value, [move] + pv
            alpha = max(alpha, value)
            if alpha >= beta:
                if not p.board[move[1]]:
                    previous = self.killers.get(ply, ())
                    self.killers[ply] = (move,) + tuple(m for m in previous if m != move)[:1]
                    hk = (p.side, move)
                    self.history[hk] = min(800000, self.history.get(hk, 0) + depth * depth)
                break
        if len(self.tt) >= CACHE_LIMIT:
            self.tt.clear()
        flag = 'upper' if best <= original_alpha else 'lower' if best >= beta else 'exact'
        stored = best + ply if best > MATE - MAX_PLY else best - ply if best < -MATE + MAX_PLY else best
        self.tt[context] = (depth, stored, flag, tuple(line))
        if len(self.best_moves) >= CACHE_LIMIT:
            self.best_moves.clear()
        self.best_moves[(p.board, p.side)] = line[0]
        return best, line


def search(position, options):
    started = time.monotonic()
    worker = Search(started + options['timeLimitMs'] / 1000)
    moves = worker.moves(position)
    result = position.result(moves)
    best = None if result else worker.ordered(position, moves)[0]
    pv = [] if best is None else [best]
    score = (-MATE if result and result['winner'] else 0) if result else worker.static(position)
    completed = 0
    if not result:
        for depth in range(1, options['maxDepth'] + 1):
            try:
                low, high = (score - 45, score + 45) if depth >= 3 else (-MATE * 2, MATE * 2)
                value, line = worker.negamax(position, depth, low, high, 0, best)
                if value <= low or value >= high:
                    # Failed aspiration bounds are not a completed iteration.
                    value, line = worker.negamax(position, depth, -MATE * 2, MATE * 2, 0, best)
            except BudgetExpired:
                break
            score, pv, completed = value, line, depth
            best = line[0]
            if score >= MATE - MAX_PLY:
                break
    return dict(move=move_json(best), search=dict(completedDepth=completed, nodes=worker.nodes,
                elapsedMs=round((time.monotonic() - started) * 1000), score=score,
                pv=list(map(move_json, pv))))
