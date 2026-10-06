"""Preserve dependency notices in the portable distribution."""
from importlib.metadata import distribution
from pathlib import Path
import shutil
import sys


def collect(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    names = ['scipy', 'numpy', 'pywebview', 'pythonnet', 'clr_loader', 'cffi',
             'pycparser', 'bottle', 'proxy_tools', 'typing_extensions']
    for name in names:
        package = distribution(name)
        folder = destination / name
        folder.mkdir(exist_ok=True)
        metadata = package.read_text('METADATA') or package.read_text('PKG-INFO') or ''
        (folder / 'METADATA.txt').write_text(metadata, encoding='utf-8')
        for file in package.files or []:
            if any(word in str(file).lower() for word in ['license', 'copying', 'notice']):
                source = Path(package.locate_file(file))
                if source.is_file():
                    target = folder.joinpath(*[part for part in file.parts if part not in ['..', '.']])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.exists():
        shutil.copyfile(python_license, destination / 'Python-LICENSE.txt')


if __name__ == '__main__':
    collect(sys.argv[1])
