"""Record the local installation identity without running or copying game code."""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def inspect(root):
    root = Path(root)
    managed = root / 'Captain of Industry_Data' / 'Managed'
    if not (managed / 'Mafi.Core.dll').is_file():
        raise ValueError('此目录没有 Mafi.Core.dll，不能识别为目标游戏目录')
    changelog = root / 'changelog.txt'
    heading = changelog.read_text(encoding='utf-8-sig').splitlines()[0] if changelog.exists() else None
    match = re.match(r'v(\S+)', heading or '')
    files = {}
    for name in ['Mafi.dll', 'Mafi.Core.dll', 'Mafi.Base.dll']:
        path = managed / name
        if not path.is_file():
            raise ValueError(f'缺少 {name}')
        files[name] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size': path.stat().st_size}
    documentation = managed / 'Mafi.Core.xml'
    text = documentation.read_text(encoding='utf-8-sig') if documentation.exists() else ''
    members = [
        'T:Mafi.Core.Factory.Machines.MachineRecipeBinding',
        'F:Mafi.Core.Factory.Machines.MachineRecipeBinding.Duration',
        'F:Mafi.Core.Factory.Machines.MachineRecipeBinding.Multiplier',
        'F:Mafi.Core.Factory.Recipes.RecipeProto.AllInputs',
        'F:Mafi.Core.Factory.Recipes.RecipeProto.AllOutputs',
    ]
    return {
        'schemaVersion': 1,
        'inspectedAt': datetime.now(timezone.utc).isoformat(),
        'versionHint': match.group(1) if match else None,
        'versionHintSource': 'changelog.txt; not a runtime version confirmation',
        'assemblies': files,
        'documentedMembers': {member: f'name="{member}"' in text for member in members},
        'runtimeVerified': False,
        'recipesExported': False,
        'notes': ['DLL hashes identify this installation; they do not prove vanilla content or authenticity.',
                  'Export runtime version and loaded mod list before treating recipe data as vanilla.'],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game_directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.game_directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'安装信息已记录；日志版本提示 {result["versionHint"]}，尚未导出或验证运行时配方。')
