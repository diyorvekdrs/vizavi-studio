# Looks

Ten signature looks the user can pick in **New project → Look**. Each has a recipe (`<id>.md`, which goes into
the package as `LOOK.md`), three reference frames (`stills/`, which go in as `look/`) and the fonts it needs
(`fonts/`, which are copied into the project's `assets/`). The cards and moving thumbnails are in `../../ui/looks/`.

The looks are adapted from **Shaan Johari's** style cards,
[“Animation styles you can build with Claude (or Codex)”](https://ruby-cotija-fb5.notion.site/Animation-styles-you-can-build-with-Claude-or-Codex-3fa28691eca3814ebb34c73a7cc261bf)
(new styles appear on his Instagram first: @viashaan). The recipes here are rewritten for Vizavi Studio's HTML engine and
any frame size. The thumbnails are our own renders.

Fonts: all SIL Open Font License 1.1 (licence next to each family in `fonts/OFL-*.txt`), from Google Fonts via Fontsource.

To change a look or add one: edit `dev/looks/make_looks.py` (recipes) and `dev/looks/thumb/scenes.js` (thumbnails), then
see `dev/README.md`.
