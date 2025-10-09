import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def bump(ver: str, kind: str) -> str:
    major, minor, patch = [int(x) for x in ver.split('.')]
    if kind == 'major':
        return f"{major+1}.0.0"
    if kind == 'minor':
        return f"{major}.{minor+1}.0"
    return f"{major}.{minor}.{patch+1}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--component', choices=['app', 'website', 'all'], default='all')
    p.add_argument('--type', choices=['major', 'minor', 'patch'], default='patch')
    p.add_argument('--file', default='version.json')
    args = p.parse_args()

    path = Path(args.file)
    data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {"app":"0.0.0","website":"0.0.0"}

    ts = datetime.now(timezone.utc).isoformat()
    if args.component in ('app', 'all'):
        data['app'] = bump(data.get('app', '0.0.0'), args.type)
    if args.component in ('website', 'all'):
        data['website'] = bump(data.get('website', '0.0.0'), args.type)
    data['updated_at'] = ts
    path.write_text(json.dumps(data, indent=2) + "\n", encoding='utf-8')
    print(json.dumps(data))


if __name__ == '__main__':
    main()

