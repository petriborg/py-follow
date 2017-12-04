# Py-Follow

Tail (or search) local (or remote) file(s) and colorize the result.

```
usage: follow.py [-h] [--version] [--debug] [--config CFG] [-f] [-n N] [-z Z]
                 [-e PTRN] [-v PTRN] [-r PTRN] [-y PTRN] [-b PTRN] [-g PTRN]
                 [[USER@]HOST:]FILE ...

Tail (or search) local (or remote) file(s) and colorize the result.

positional arguments:
  [[USER@]HOST:]FILE    input files from local or remote hosts

optional arguments:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  --debug               enable debug
  --config CFG, -c CFG  configuration file, default ~/.py-follow
  -f                    follow FILE(s)
  -n N                  output the last N lines, instead of last 10
  -z Z                  Load Z group(s) from CFG file
  -e PTRN               match
  -v PTRN               invert match
  -r PTRN, -R PTRN      match/highlight PTRN with red
  -y PTRN, -Y PTRN      match/highlight PTRN with yellow
  -b PTRN, -B PTRN      match/highlight PTRN with blue
  -g PTRN, -G PTRN      match/highlight PTRN with green
```

## Config file YAML format
```YAML
---
group-name:
  - !color [my-color, '#000000']  # defines new color, my-color
  - !match [FOO]                  # selects lines for display matching pattern FOO
  - !match [FOO, my-color]        # same as above, but also highlights with my-color
  - !highlight [FOO, my-color]    # highlights with my-color
  - !nmatch [FOO]                 # inverted match - lines matching will not be selected
```

## Config file REPR format
```python
{
'group-name': [
    Match('FOO', 'red'),
    ]
}
```
