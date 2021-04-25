#!/usr/bin/env python3

import re
import os
import sys
import glob
import stat
import shutil
import subprocess

regexp = re.compile(r'(.+ => )?(.+) \(0x[0-9a-f]{16}\)')


def run(cmd):
    return subprocess.run(
        cmd.split(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )


def run_in_container(container, cmd):
    return run(f'docker exec {container} {cmd}')


def check_exists(container, binary):
    output = run_in_container(container, f'test -f {binary}')
    
    if output.returncode != 0:
        print(f"File not found: {container}:{binary}")
        exit(1)


def visit(container, binary, outdir, visited, level=0):
    if binary in visited:
        return
    
    visited.add(binary)

    indent = '    '*level
    filename = os.path.basename(binary)
    
    src = container+":"+binary
    dst = os.path.join(outdir, filename)
    
    assert not dst.startswith('/')    
    
    check_exists(container, binary)
    
    if not os.path.exists(dst) or level == 0:
        run(f'docker cp -L {src} {dst}')
        print (indent + f'{src} => {dst}')
        
    ldd_output = run_in_container(container, f'ldd {binary}')

    libs = list(map(str.strip, ldd_output.stdout.decode('ascii').strip().split('\n')))
    
    for l in libs:
        if l == 'statically linked' or l.startswith('linux-vdso.so'):
            continue
        else:
            m = regexp.match(l)
            assert m is not None
            libfile = m.group(2)
            assert libfile.startswith('/')
            check_exists(container, libfile)
            visit(container, libfile, outdir, visited, level+1)

    return dst


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print (f'Usage: {sys.argv[0]} <container>:<path to binary>')
        exit(1)
        
    if len(sys.argv[1].split(":")) < 2:
        print (f'Usage: {sys.argv[0]} <container>:<path to binary>')
        exit(1)

    patchelf = shutil.which('patchelf')
    if not patchelf:
        print ('patchelf is not installed. Please install it.')
        exit(1)
        
    container, path = sys.argv[1].split(":")
    
    outdir = 'out'
    if not os.path.exists(outdir):
        os.mkdir(outdir)
    
    res = run_in_container(container, 'which ldd')
    
    if res.returncode != 0:
        print(res.stderr.decode('ascii').strip())
        exit(1)

    outfile = visit(container, path, outdir, set())

    # Fix interpreter so it will use the correct ld and not segfault
    print (f'Patching {outfile} interpreter and libc paths')
    ld_so = glob.glob(os.path.join(outdir, 'ld-linux-*.so*'))
    print ('Found ld:', ld_so)
    assert len(ld_so) == 1
    ld_so = os.path.basename(ld_so[0])
    interpreter = './' + ld_so
    print (f'New interpreter path: {interpreter}')

    subprocess.check_output([patchelf, '--set-interpreter', interpreter, '--set-rpath', '.', outfile])

    print ('Create wrapper script')
    real_bin = outfile + '.1'
    shutil.move(outfile, real_bin)
    with open (outfile, 'w') as f:
        f.write(f"#!/bin/sh\nLD_LIBRARY_PATH=. ./{os.path.basename(real_bin)} $*\n")

    # chmod everything +x lol
    for f in glob.glob(os.path.join(outdir, '*')):
        st = os.stat(f)
        os.chmod(f, st.st_mode | stat.S_IEXEC)
    
    print ('Done')
