"""Generate importable records; validate every recorded position independently on import."""
import json
from pathlib import Path
from backend.game import Game

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'samples' / '棋谱样例'
CONFIG = dict(mode='human_human', humanSide=None,
              redAI=dict(maxDepth=4, timeLimitMs=1500),
              blackAI=dict(maxDepth=4, timeLimitMs=1500))


def manual(moves):
    game = Game(CONFIG)
    for move in moves:
        game.apply(move)
    return game.record()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    originals = []
    for path in sorted((ROOT / 'docs/experiments/baseline').glob('game-*.json')):
        record = json.loads(path.read_text(encoding='utf-8'))['record']
        Game.from_record(record)
        originals.append((path.name, record))
    if not originals:
        raise RuntimeError('Missing baseline records')
    samples = [
        ('01-初始局面.json', manual([]), '合成样例：标准初始局面'),
        ('02-开局六步.json', manual([(64,67),(25,22),(82,63),(1,18),(81,82),(0,1)]),
         '合成样例：双方中炮、出马、出车，共六个半回合'),
    ]
    source_name, source = originals[0]
    source_game = Game.from_record(source)
    capture_index = next(i for i, move in enumerate(source_game.moves)
                         if source_game.positions[i].board[move[1]] != 0)
    prefix = Game({k: source[k] for k in CONFIG})
    for move in source_game.moves[:capture_index + 1]:
        prefix.apply(move, human=False)
    samples.append(('03-首次吃子片段.json', prefix.record(), f'真实 AI 实验 {source_name} 的首次吃子前缀'))
    for winner, filename in [('red','04-红方获胜.json'),('black','05-黑方获胜.json')]:
        candidates = [(name, record) for name, record in originals
                      if record['result'] and record['result']['winner'] == winner]
        name, record = min(candidates, key=lambda item: len(item[1]['moves']))
        samples.append((filename, record, f'真实 AI 实验 {name} 的完整棋谱'))
    samples.append(('06-重复局面和棋.json', manual([(82,63),(1,18),(63,82),(18,1)] * 2),
                    '合成样例：双方马往返两轮，触发相同棋盘与行棋方第三次出现'))
    rows = []
    for filename, record, source in samples:
        path = OUT / filename
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        loaded = json.loads(path.read_text(encoding='utf-8'))
        imported = Game.from_record(loaded)
        expected = Game({k: loaded[k] for k in CONFIG})
        for move in loaded['moves']:
            expected.apply((move['from'], move['to']), human=False)
        assert imported.record() == loaded
        for ply, position in enumerate(expected.positions):
            imported.command('seek_replay', {'ply': ply})
            assert imported.state()['board'] == list(position.board)
            assert imported.state()['sideToMove'] == position.side
            assert imported.state()['displayResult'] == position.result()
        result = loaded['result']
        label = '未结束' if result is None else f"{result['winner'] or '和棋'} / {result['reason']}"
        rows.append(f'| [{filename}]({filename}) | {len(loaded["moves"])} | {label} | {source} |')
        print(filename, len(loaded['moves']), label, 'import and every replay node OK')
    (OUT / 'README.md').write_text(
        '# 可导入棋谱样例\n\n在网页点击“导入棋谱”，选择本目录中的一个 JSON 文件，确认后进入回放。'
        '使用“下一步”或“终点”查看过程和结果。步数指半回合（一方走一步）。\n\n'
        '| 文件 | 步数 | 最终结果 | 来源 |\n| --- | --- | --- | --- |\n' + '\n'.join(rows) +
        '\n\n导入只供查看，不增加本次胜负统计。非终局可通过“从此处继续”恢复对局；'
        '导入的 AI 实验棋谱保留 AI 对 AI 模式，继续后由 AI 自动行棋。'
        '初始与开局样例采用人人模式，适合继续手动操作。\n\n'
        '合成样例用于演示功能，不冒充真实比赛。红黑获胜样例直接提取已保存的 AI 实验棋谱，'
        '没有修改走法或胜负。规则为 course-v1，不代表完整竞赛长将长捉裁决。\n\n'
        '所有文件均通过实际 `Game.from_record` 导入校验，并逐节点核对棋盘、行棋方和结果。'
        '重新生成：在项目根目录运行 `.venv/Scripts/python.exe -m scripts.make_sample_records`。\n',
        encoding='utf-8')


if __name__ == '__main__':
    main()
