"""Allow source files into build contexts; exclude private runtime artifacts."""
from pathlib import PurePath

PRIVATE_NAMES={"runtime-options.json","account.json","owned-session.json","owned-signing.json","identity.json","machine.json","active-provider.json","signer.lock","store.lock","native-consent.json",".env"}
PRIVATE_SUFFIXES={".apk",".bin",".enc",".key",".plist",".sqlite",".sqlite3",".dmg",".x86_64"}
EXCLUDED_PARTS={".git","__pycache__",".venv",".pytest_cache","node_modules","data"}

def allowed_path(relative):
    path=PurePath(relative)
    return not (set(path.parts)&EXCLUDED_PARTS or path.name in PRIVATE_NAMES or path.suffix in PRIVATE_SUFFIXES or path.suffix==".pyc")
