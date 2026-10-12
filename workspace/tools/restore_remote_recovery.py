"""Download, verify, and restore the 2026-10-12 GitHub recovery release."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import tarfile
import urllib.request

BASE = 'https://github.com/ificanli/EffectMaker/releases/download/recovery-2026-10-12/'

def download(url, target, expected=None):
    temporary = target.with_name(target.name + '.download')
    if target.exists() and expected:
        if sha256(target) == expected:
            return
    with urllib.request.urlopen(url, timeout=120) as response, temporary.open('wb') as output:
        while chunk := response.read(4 * 1024**2):
            output.write(chunk)
    if expected and sha256(temporary) != expected:
        raise RuntimeError(f'SHA-256 mismatch: {target.name}')
    temporary.replace(target)

def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as file:
        while chunk := file.read(4 * 1024**2):
            digest.update(chunk)
    return digest.hexdigest()

class PartsReader:
    def __init__(self, paths):
        self.paths = iter(paths)
        self.current = None
    def read(self, size=-1):
        if size < 0:
            size = 1024**2
        output = bytearray()
        while len(output) < size:
            if self.current is None:
                try:
                    self.current = next(self.paths).open('rb')
                except StopIteration:
                    break
            chunk = self.current.read(size-len(output))
            if chunk:
                output.extend(chunk)
            else:
                self.current.close()
                self.current = None
        return bytes(output)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True, help='Existing cloned project to restore into')
    parser.add_argument('--downloads', type=Path, help='Folder for resumable downloaded parts')
    parser.add_argument('--groups', nargs='*', help='Restore selected groups only')
    parser.add_argument('--overwrite', action='store_true', help='Replace differing files in the destination')
    args = parser.parse_args()
    root = args.project.resolve()
    if not (root/'.git').is_dir():
        raise RuntimeError('Clone EffectMaker first; destination must contain .git')
    downloads = (args.downloads or root/'.git/recovery-downloads').resolve()
    downloads.mkdir(parents=True, exist_ok=True)
    manifest_path = downloads/'recovery-manifest.json'
    download(BASE+'recovery-manifest.json', manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for name, group in manifest['groups'].items():
        if args.groups and name not in args.groups:
            continue
        parts = []
        for part in group['parts']:
            path = downloads/part['name']
            print(f'Download and verify {part["name"]}', flush=True)
            download(BASE+part['name'], path, part['sha256'])
            parts.append(path)
        expected = {entry['path']:entry for entry in group['entries']}
        restored = set()
        with gzip.GzipFile(fileobj=PartsReader(parts), mode='rb') as stream:
            with tarfile.open(fileobj=stream, mode='r|') as archive:
                for member in archive:
                    if not member.isfile() or member.name not in expected:
                        raise RuntimeError('Unexpected archive entry: '+member.name)
                    destination = (root/member.name).resolve()
                    if not destination.is_relative_to(root):
                        raise RuntimeError('Unsafe archive path: '+member.name)
                    entry = expected[member.name]
                    if destination.exists() and sha256(destination) != entry['sha256'] and not args.overwrite:
                        raise RuntimeError('Destination differs; review before using --overwrite: '+member.name)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    temporary = destination.with_name(destination.name+'.recovering')
                    digest = hashlib.sha256()
                    with archive.extractfile(member) as source, temporary.open('wb') as output:
                        while chunk := source.read(4*1024**2):
                            output.write(chunk)
                            digest.update(chunk)
                    if digest.hexdigest() != entry['sha256']:
                        raise RuntimeError('Restored file SHA-256 mismatch: '+member.name)
                    temporary.replace(destination)
                    restored.add(member.name)
        if restored != set(expected):
            raise RuntimeError('Archive file set does not match manifest: '+name)
        print(f'Restored and verified {name}: {len(restored)} files', flush=True)
    print('Selected file groups restored. Restore Beads separately using the documented native restore command.')

if __name__ == '__main__':
    main()
