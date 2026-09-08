"""Load open literature NER/RE sets: NCBI Disease and BC5CDR.

Sources (no DUA):
- NCBI Disease CoNLL: https://github.com/spyysalo/ncbi-disease
- NCBI Disease original: https://www.ncbi.nlm.nih.gov/CBBresearch/Dogan/DISEASE/NCBI_corpus.zip
- HuggingFace: ncbi/ncbi_disease
- BC5CDR BioC/PubTator-style files from BioCreative / NCBI FTP mirrors
"""

from __future__ import annotations

import io
import json
import re
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

CACHE = Path(__file__).resolve().parents[3] / "data" / "cache"

NCBI_CONLL = {
    "train": "https://raw.githubusercontent.com/spyysalo/ncbi-disease/master/conll/train.tsv",
    "dev": "https://raw.githubusercontent.com/spyysalo/ncbi-disease/master/conll/devel.tsv",
    "test": "https://raw.githubusercontent.com/spyysalo/ncbi-disease/master/conll/test.tsv",
}

# Public-domain BioCreative V CDR corpus (NCBI FTP mirror).
BC5CDR_ZIP = "https://ftp.ncbi.nlm.nih.gov/pub/lu/BC5CDR/CDR_Data.zip"


def _download(url: str, dest: Path, timeout: int = 60) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": "clinical-gliner-kg/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        dest.write_bytes(resp.read())
    return dest


def _bio_tags_to_spans(tokens: list[str], tags: list[str]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    i = 0
    cursor = 0
    while i < len(tokens):
        tag = tags[i]
        token = tokens[i]
        if tag.startswith("B-") or (tag.startswith("I-") and (i == 0 or not tags[i - 1].endswith(tag[2:]))):
            label = tag.split("-", 1)[1]
            start = cursor
            pieces = [token]
            i += 1
            cursor += len(token)
            while i < len(tokens) and tags[i].startswith("I-"):
                cursor += 1  # space
                pieces.append(tokens[i])
                cursor += len(tokens[i])
                i += 1
            spans.append({"text": " ".join(pieces), "label": label, "start": start, "end": cursor})
            cursor += 1
            continue
        cursor += len(token) + 1
        i += 1
    return spans


def _read_conll_sentences(text: str) -> list[dict[str, Any]]:
    sentences: list[dict[str, Any]] = []
    tokens: list[str] = []
    tags: list[str] = []
    sent_id = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if tokens:
                sentences.append(_pack_sentence(f"s{sent_id}", tokens, tags))
                sent_id += 1
                tokens, tags = [], []
            continue
        parts = re.split(r"\s+", line)
        if len(parts) < 2:
            continue
        tokens.append(parts[0])
        tags.append(parts[-1])
    if tokens:
        sentences.append(_pack_sentence(f"s{sent_id}", tokens, tags))
    return sentences


def _pack_sentence(doc_id: str, tokens: list[str], tags: list[str]) -> dict[str, Any]:
    text = " ".join(tokens)
    return {
        "id": doc_id,
        "text": text,
        "entities": _bio_tags_to_spans(tokens, tags),
        "relations": [],
        "source": "conll",
    }


def load_ncbi_disease(split: str = "test", limit: int | None = None) -> list[dict[str, Any]]:
    split = "dev" if split in {"validation", "devel", "dev"} else split
    try:
        from datasets import load_dataset

        ds = load_dataset("ncbi/ncbi_disease", split="validation" if split == "dev" else split)
        rows = []
        for i, ex in enumerate(ds):
            tags = ex["ner_tags"]
            # HF class labels may be ints
            names = ds.features["ner_tags"].feature.names if hasattr(ds.features["ner_tags"], "feature") else None
            if names:
                tags = [names[t] if isinstance(t, int) else t for t in tags]
            packed = _pack_sentence(str(ex.get("id", i)), list(ex["tokens"]), list(tags))
            packed["source"] = "ncbi_disease"
            rows.append(packed)
            if limit and len(rows) >= limit:
                break
        return rows
    except Exception:
        url = NCBI_CONLL[split]
        path = _download(url, CACHE / f"ncbi_disease_{split}.tsv")
        rows = _read_conll_sentences(path.read_text(encoding="utf-8", errors="ignore"))
        for row in rows:
            row["source"] = "ncbi_disease"
        return rows[:limit] if limit else rows


def load_bc5cdr(split: str = "test", limit: int | None = None) -> list[dict[str, Any]]:
    """Load BC5CDR abstracts with chemical/disease spans and CID relations when present."""
    try:
        from datasets import load_dataset

        ds = load_dataset("bigbio/bc5cdr", "bc5cdr_bigbio_kb", split="validation" if split == "dev" else split, trust_remote_code=True)
        rows = []
        for i, ex in enumerate(ds):
            passages = ex.get("passages") or []
            text = " ".join(" ".join(p.get("text") or []) if isinstance(p.get("text"), list) else str(p.get("text") or "") for p in passages)
            entities = []
            for ent in ex.get("entities") or []:
                surface = " ".join(ent.get("text") or []) if isinstance(ent.get("text"), list) else str(ent.get("text") or "")
                offsets = ent.get("offsets") or [[0, 0]]
                start, end = offsets[0]
                entities.append(
                    {
                        "text": surface,
                        "label": str(ent.get("type") or "Entity"),
                        "start": int(start),
                        "end": int(end),
                    }
                )
            relations = []
            id_to_text = {}
            for ent in ex.get("entities") or []:
                surface = " ".join(ent.get("text") or []) if isinstance(ent.get("text"), list) else str(ent.get("text") or "")
                id_to_text[str(ent.get("id"))] = surface
            for rel in ex.get("relations") or []:
                relations.append(
                    {
                        "subject": id_to_text.get(str(rel.get("arg1_id") or rel.get("head", {}).get("id")), ""),
                        "relation": str(rel.get("type") or "CID"),
                        "object": id_to_text.get(str(rel.get("arg2_id") or rel.get("tail", {}).get("id")), ""),
                    }
                )
            rows.append({"id": str(ex.get("id", i)), "text": text, "entities": entities, "relations": relations, "source": "bc5cdr"})
            if limit and len(rows) >= limit:
                break
        return rows
    except Exception:
        return _load_bc5cdr_from_zip(split, limit)


def _load_bc5cdr_from_zip(split: str, limit: int | None) -> list[dict[str, Any]]:
    zpath = _download(BC5CDR_ZIP, CACHE / "CDR_Data.zip", timeout=120)
    split_key = {"train": "CDR_TrainingSet", "dev": "CDR_DevelopmentSet", "test": "CDR_TestSet"}.get(split, "CDR_TestSet")
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(zpath) as zf:
        names = [n for n in zf.namelist() if split_key in n and n.endswith(".txt")]
        if not names:
            # Some distributions use PubTator .PubTator.txt
            names = [n for n in zf.namelist() if split_key.lower() in n.lower()]
        for name in names:
            payload = zf.read(name).decode("utf-8", errors="ignore")
            rows.extend(_parse_pubtator(payload, source="bc5cdr"))
            if limit and len(rows) >= limit:
                return rows[:limit]
    return rows[:limit] if limit else rows


def _parse_pubtator(text: str, source: str) -> list[dict[str, Any]]:
    """Minimal PubTator parser: title|t|, abstract|a|, then TSV mention / CID lines."""
    docs: dict[str, dict[str, Any]] = {}
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if not line:
            continue
        if "|t|" in line or "|a|" in line:
            pmid, kind, body = line.split("|", 2)
            doc = docs.setdefault(pmid, {"id": pmid, "title": "", "abstract": "", "entities": [], "relations": [], "source": source})
            if kind == "t":
                doc["title"] = body
            else:
                doc["abstract"] = body
            continue
        parts = line.split("\t")
        pmid = parts[0]
        doc = docs.setdefault(pmid, {"id": pmid, "title": "", "abstract": "", "entities": [], "relations": [], "source": source})
        if len(parts) >= 6 and parts[1].isdigit():
            doc["entities"].append(
                {
                    "text": parts[3],
                    "label": parts[4],
                    "start": int(parts[1]),
                    "end": int(parts[2]),
                    "id": parts[5] if len(parts) > 5 else parts[3],
                }
            )
        elif len(parts) >= 5 and parts[1] in {"CID", "Chemical-Disease"}:
            doc["relations"].append({"subject_id": parts[2], "object_id": parts[3], "relation": "CID"})
    out = []
    for doc in docs.values():
        doc["text"] = (doc.get("title") or "") + " " + (doc.get("abstract") or "")
        id_to_text = {}
        for ent in doc["entities"]:
            if ent.get("id"):
                id_to_text[str(ent["id"])] = ent["text"]
        resolved = []
        for rel in doc["relations"]:
            if "subject" in rel and "object" in rel:
                resolved.append(rel)
                continue
            subj = id_to_text.get(str(rel.get("subject_id", "")))
            obj = id_to_text.get(str(rel.get("object_id", "")))
            if subj and obj:
                resolved.append({"subject": subj, "relation": rel.get("relation", "CID"), "object": obj})
        doc["relations"] = resolved
        out.append(doc)
    return out


def cache_jsonl(rows: list[dict[str, Any]], name: str) -> Path:
    path = CACHE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    return path
