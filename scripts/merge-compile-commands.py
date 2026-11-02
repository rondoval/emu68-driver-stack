#!/usr/bin/env python3
"""Merge the components' compile_commands.json into one, for the editor.

Each component is its own CMake project, so each build directory has its own
compile_commands.json, with the container's /work in every path.  This writes
<build dir>/compile_commands.json with /work replaced by the host's stack root.
The toolchain path (/opt/m68k-amigaos) is the same on the host.

  merge-compile-commands.py <stack root> <build dir, relative to it>
"""
import glob
import json
import os
import sys

CONTAINER_ROOT = '/work'


def main():
    root, build = sys.argv[1], sys.argv[2]
    build_dir = os.path.join(root, build)

    def host(text):
        return text.replace(CONTAINER_ROOT + '/', root + '/')

    merged = []
    for path in sorted(glob.glob(os.path.join(build_dir, '*', 'compile_commands.json'))):
        with open(path) as f:
            for entry in json.load(f):
                for key in ('directory', 'file', 'command', 'output'):
                    if key in entry:
                        entry[key] = host(entry[key])
                if 'arguments' in entry:
                    entry['arguments'] = [host(a) for a in entry['arguments']]
                merged.append(entry)

    with open(os.path.join(build_dir, 'compile_commands.json'), 'w') as f:
        json.dump(merged, f, indent=1)
    print('compile_commands.json: %d entries' % len(merged))


if __name__ == '__main__':
    main()
