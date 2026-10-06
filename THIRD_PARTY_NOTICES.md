# Third-party materials

The MIT license applies to this project's original code and original SVG icons.
It does not grant rights to Captain of Industry / MaFi Games artwork, game
materials, or third-party material referenced or downloaded by the application.

## Captain of Industry Wiki images

Image file-page URLs and their license notices are recorded in
`web/icons/wiki-manifest.json` and `web/icons/WIKI-LICENSES.md`.
Those file pages currently state:

> This work is copyrighted. The copyright holder has given permission for its use.

This statement is retained as a source notice; it is not an MIT license or a
claim that this project owns the artwork. See each source page for its notice.

Downloaded Wiki PNGs, original page snapshots, and the local preview screenshot
are excluded from Git. The local application keeps existing downloaded files.
A fresh checkout falls back to original SVG icons until images are supplied
locally. `fetch_wiki_icons.py` is an explicit, optional downloader and preserves
the original notices; startup does not download images automatically.

## Recipe information

The nuclear catalog records publicly described recipe quantities and mechanisms,
with source URLs and a pending in-game verification status. Referenced Wiki and
game materials retain their original rights. Original HTML page snapshots are
local research artifacts and are not distributed in the repository.

## Dependencies

SciPy and its NumPy dependency retain their own licenses. They are installed
separately through pip and are not vendored in this repository.

The optional desktop distribution bundles Python, SciPy, NumPy, pywebview,
pythonnet and their runtime dependencies. Their metadata and license files are
preserved in the portable package's `licenses` directory. The project's MIT
license does not replace those licenses. Microsoft Edge WebView2 Runtime is a
system prerequisite and is not bundled in the portable package.
