"""Isolated live-modification rehearsal; never alters the production engine."""
import shutil
from pathlib import Path
import subprocess
import sys

def main():
    root=Path.cwd();scratch=root/'.runtime/rehearsal';scratch.mkdir(parents=True,exist_ok=True)
    shutil.copytree(root/'engine',scratch/'engine',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
    target=scratch/'engine/evaluation.py'
    original=target.read_text(encoding='utf-8')
    assert 'CHECK_PENALTY=55' in original
    target.write_text(original.replace('CHECK_PENALTY=55','CHECK_PENALTY=70'),encoding='utf-8')
    code="""import sys;sys.path.insert(0,sys.argv[1]);import engine.evaluation as e;assert e.CHECK_PENALTY==70;import unittest;s=unittest.defaultTestLoader.loadTestsFromNames(['tests.test_rules','tests.test_search']);r=unittest.TextTestRunner().run(s);raise SystemExit(not r.wasSuccessful())"""
    subprocess.run([sys.executable,'-c',code,str(scratch)],check=True)
    assert 'CHECK_PENALTY=55' in (root/'engine/evaluation.py').read_text(encoding='utf-8')
    print('Evaluation weight modified to 70 in scratch, related tests passed; production remains 55.')

if __name__=='__main__':main()
