import argparse
import gzip
import json
import pathlib
import sys

from kmock._internal import fetching


# Too early to introduce Click for one command, but design the CLI in a forwards-compatible way.
def main(args: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog='kmock')
    subparsers = parser.add_subparsers(dest='command')

    fetch_parser = subparsers.add_parser('fetch')
    fetch_subparsers = fetch_parser.add_subparsers(dest='subcommand')

    resources_parser = fetch_subparsers.add_parser('resources')
    resources_parser.add_argument('--output', '-o', default=None)
    resources_parser.add_argument('--include', '-i', dest='filters', action='append',
                                  type=fetching.Include, default=[], metavar='GROUP_OR_GV')
    resources_parser.add_argument('--exclude', '-x', dest='filters', action='append',
                                  type=fetching.Exclude, default=[], metavar='GROUP_OR_GV')

    parsed = parser.parse_args(args)

    if parsed.command == 'fetch' and parsed.subcommand == 'resources':
        _fetch_resources(output=parsed.output, filters=parsed.filters)
    else:
        parser.print_help()
        sys.exit(1)


def _fetch_resources(
        *,
        output: str | pathlib.Path | None,
        filters: list[fetching.Include | fetching.Exclude],
) -> None:
    documents = fetching.fetch_resources(filters=filters)
    path = pathlib.Path(output) if output is not None else None
    text: str = json.dumps(documents, sort_keys=False)

    if path is None:
        sys.stdout.write(text)
    elif path.suffix == '.gz':
        with gzip.open(path, 'wt', compresslevel=9, encoding='utf-8') as f:
            f.write(text)
    elif path.suffix == '.bz2':
        import bz2
        with bz2.open(path, 'wt', compresslevel=9, encoding='utf-8') as f:
            f.write(text)
    elif path.suffix == '.zst':
        from compression import zstd  # python 3.14+
        with zstd.open(path, 'wt', level=20, encoding='utf-8') as f:
            f.write(text)
    else:
        with open(path, 'wt', encoding='utf-8') as f:
            f.write(text)
