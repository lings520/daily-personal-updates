"""Download SHA-256 pinned Noto SC fonts once into a caller-selected cache directory."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]

def install(directory):
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=True)
    for item in json.loads((ROOT/'config/chinese-fonts.json').read_text()):
        path=directory/item['name']
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']:continue
        with urlopen(item['url'],timeout=60) as response:content=response.read()
        if hashlib.sha256(content).hexdigest()!=item['sha256']:raise ValueError('Font checksum mismatch: '+item['name'])
        temporary=path.with_suffix('.tmp');temporary.write_bytes(content);temporary.replace(path)
    print(json.dumps({'font_dir':str(directory)}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--font-dir',required=True)
    install(parser.parse_args().font_dir)
