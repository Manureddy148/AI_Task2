#!/usr/bin/env python3
"""A1: build the eval corpus from FLORES-200 devtest.

Languages: English + the six languages in scope for the product (Part C): Hindi,
Kannada, Tamil, Telugu, Bengali, Marathi — three Dravidian and three Indo-Aryan
languages across five scripts (Devanagari x2, Bengali, Kannada, Tamil, Telugu).
FLORES-200 is n-way parallel at sentence level, which is the property this audit
needs: the SAME content in every language (see results.md on denominators).

Deterministic: downloads the public tarball (24 MB), extracts the 7 devtest files
verbatim (no filtering, no reordering), writes them as UTF-8 .txt plus a stats
table. Re-running reproduces byte-identical data/.

Source: https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz (CC-BY-SA 4.0,
NLLB team / Meta AI). Attribution in corpus_card.md.
"""

import argparse
import hashlib
import tarfile
import unicodedata
import urllib.request
from pathlib import Path

import regex  # \X = extended grapheme cluster

HERE = Path(__file__).resolve().parent
URL = "https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz"
LANGS = {"eng": "eng_Latn", "hin": "hin_Deva", "kan": "kan_Knda",
         "tam": "tam_Taml", "tel": "tel_Telu", "ben": "ben_Beng",
         "mar": "mar_Deva"}
SPLIT = "devtest"


def get_tarball(path: Path) -> Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {URL} ...")
        urllib.request.urlretrieve(URL, path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tarball", type=Path, default=HERE / ".cache" / "flores200_dataset.tar.gz")
    args = ap.parse_args()

    tb = get_tarball(args.tarball)
    data = HERE / "data"
    data.mkdir(exist_ok=True)

    stats = []
    with tarfile.open(tb, "r:gz") as tar:
        for short, flores in LANGS.items():
            member = f"./flores200_dataset/{SPLIT}/{flores}.{SPLIT}"
            raw = tar.extractfile(member).read().decode("utf-8")
            lines = [l for l in raw.split("\n") if l.strip()]
            nfc_changed = sum(1 for l in lines if unicodedata.normalize("NFC", l) != l)
            out = data / f"{short}.txt"
            out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
            stats.append(dict(
                lang=short, flores=flores, sents=len(lines),
                words=sum(len(l.split()) for l in lines),
                cps=sum(len(l) for l in lines),
                graphemes=sum(len(regex.findall(r"\X", l)) for l in lines),
                bytes=sum(len(l.encode("utf-8")) for l in lines),
                nfc_changed=nfc_changed,
                sha256=hashlib.sha256(out.read_bytes()).hexdigest()[:12],
            ))

    n0 = stats[0]["sents"]
    assert all(s["sents"] == n0 for s in stats), "line counts differ -> not parallel!"

    lines_md = ["| lang | FLORES code | sentences | words | graphemes | code points | UTF-8 bytes | NFC-changed lines | sha256/12 |",
                "|---|---|---|---|---|---|---|---|---|"]
    for s in stats:
        lines_md.append(f"| {s['lang']} | {s['flores']} | {s['sents']} | {s['words']:,} | "
                        f"{s['graphemes']:,} | {s['cps']:,} | {s['bytes']:,} | {s['nfc_changed']} | `{s['sha256']}` |")
    md = "\n".join(lines_md) + "\n"
    (HERE / "corpus_stats.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"[data in {data}, stats in corpus_stats.md]")


if __name__ == "__main__":
    main()
