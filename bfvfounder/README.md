# Black Flag founders edition

An eight-chapter founder-facing version of the Black Flag thesis, at `/bfvfounder/`. It is separate from the enterprise-facing `/bfv/` page.

The opening paragraph is verbatim from the supplied October 22 paper. The story leads with the manufacturing-to-ownership architecture, then develops the two engines, the IBM production thought experiment, the two clocks, commercial economics, the conditional capital bridge, QGV, enduring assets, and the founders' next decisions.

## Files

- `index.html`, `style.css`, `main.js`: story, chapter navigation, interactive IBM stages, and original-image dialogs.
- `assets/`: five unchanged supplied illustrations and the BF favicon.
- `paper.html`, `paper.txt`: complete supplied paper.
- `notes.html`: founder discussion questions and source notes.

## Local preview

From the repository root:

```sh
python3 -m http.server 8891 --bind 127.0.0.1
```

Open http://127.0.0.1:8891/bfvfounder/.

No dependencies, external fonts, tracking, analytics, or form submission. All paths are relative. Hosting this directory does not restrict access; discussion/prototype labels and noindex metadata are not access controls.

The earlier local source and its verification screenshots remain preserved outside this repository. The founder edition was added to this repository on October 23, 2026. No changes to `/bfv/` are required.
