"""One isolated computation. Parent owns lifetime and cancellation."""
import json
import sys
from ai.search import search
from engine.rules import parse_position
from backend.protocol import options

if __name__=='__main__':
    data=json.load(sys.stdin)
    result=search(parse_position(data['position']),options(data['options']))
    print(json.dumps(result),flush=True)
