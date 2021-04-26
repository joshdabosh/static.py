# static.py: docker episode

## What does it do?

You give it a running Docker container and a dynamically linked binary inside that container.

It will make a directory locally that has all the dependencies (recursively).  It also fixes the ld interpreter and libc paths so it will not segfault.

## How does it work?

It recursively calls ldd and copies all the required .so files. Then, it also needs to patch up the ld interpreter so it will not try to use the system ld rather than the one copied from the source host.

## How do I use it

For example, making a redistributable `/usr/bin/ls` in running container `bbb`:

`./static.py bbb:/usr/bin/ls`

If you want to use this for simplifying binary exploitation the actual binary is the `<binary>.1` in `out/`. Remember to set `LD_LIBRARY_PATH=.` in your environment vars when running.

## Should I use this in production?

Yes and please email me so I can short your company stock. (Not financial advice btw)
