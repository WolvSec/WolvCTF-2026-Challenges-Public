# The Broken Time Capsule

## Build

From `Rev/Time Capsule/`, one directory above this `challenge/` folder, run:

```sh
./build.sh
```

The script uses Python 3 to generate `challenge/dist/backup.tc` and Docker to
compile the stripped, statically linked executable into
`challenge/dist/time_capsule`. It then creates `dis.tar.gz` at the challenge
root. That archive contains only the two player files, at its top level.

## Run locally

Extract `dis.tar.gz`, then run the executable with four decimal byte inputs and
the backup path:

```sh
./time_capsule <slot-1> <slot-2> <slot-3> <slot-4> backup.tc
```

The executable is built for Linux x86-64. The `src/` and `tools/` directories,
organizer flag, and `solution/` directory are not included in the player
archive.
