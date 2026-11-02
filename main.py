import argparse
import json
import logging
from app.settings import Settings
from app.readiness import check

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run",action="store_true")
    args=parser.parse_args()
    settings=Settings.load()
    if args.run:
        from app.runtime import run
        run(settings)
    else:
        print(json.dumps(check(settings),ensure_ascii=False,indent=2))

if __name__=="__main__":
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    try:
        main()
    except Exception as exc:
        print(json.dumps({"error_type":type(exc).__name__,"code":getattr(exc,"code",None)}))
        raise SystemExit(1)
