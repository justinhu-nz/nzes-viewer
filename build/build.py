#!/usr/bin/env python3
"""Build the NZES 2023 viewer.

Reads the Stata release file + questionnaire PDF and writes a single self-contained
HTML file (template + embedded data). Free-text fields, IDs and fine geography are
NOT embedded.

Usage:  python3 build.py <path/to/2_NZES23Release_100227.dta> <questionnaire.pdf> <template.html> <out.html>
"""
import json, re, subprocess, sys
import numpy as np
import pandas as pd

DTA, QPDF, TEMPLATE, OUT = sys.argv[1:5]

r = pd.io.stata.StataReader(DTA)
raw = r.read(convert_categoricals=False).copy()
VL = r.value_labels()
LBL = dict(zip(r._varlist, r._lbllist))
VLAB = r.variable_labels()

# ---------------------------------------------------------------- questionnaire text
qtxt = subprocess.run(["pdftotext", QPDF, "-"], capture_output=True, text=True).stdout
qlines = [l.rstrip() for l in qtxt.splitlines()]
QRE = re.compile(r"^([A-I]\d{1,2})\.\s+(.*)")
IRE = re.compile(r"^([a-z])\)\s+(.*)")
STOP = re.compile(r"^(Please|To respond|BFVV|or$)")
stems, items, cur = {}, {}, None
i = 0
while i < len(qlines):
    l = qlines[i].strip()
    m = QRE.match(l)
    if m:
        cur = m.group(1)
        parts = [m.group(2)]
        j = i + 1
        while j < len(qlines):
            n = qlines[j].strip()
            if not n or STOP.match(n) or QRE.match(n) or IRE.match(n):
                break
            parts.append(n)
            j += 1
        stems[cur] = re.split(r"\s*Please (?:cross|shade|write|tick|go)", " ".join(parts))[0].strip()
        i = j
        continue
    m = IRE.match(l)
    if m and cur:
        parts = [m.group(2)]
        j = i + 1
        while j < len(qlines):
            n = qlines[j].strip()
            if not n or STOP.match(n) or QRE.match(n) or IRE.match(n):
                break
            parts.append(n)
            j += 1
        items[(cur, m.group(1))] = " ".join(parts)
        i = j
        continue
    i += 1

SECTIONS = {
    "A": "A · Politics, the election & you",
    "B": "B · Parties & leaders",
    "C": "C · Opinions & issues",
    "D": "D · Māori descent",
    "E": "E · Party preferences & voting",
    "F": "F · Parties, politicians & funding",
    "G": "G · Government & participation",
    "H": "H · About you",
    "I": "I · Spouse or partner",
}

EXCLUDE = set("""amcase mjackid date newdate ljacknum bwgt vwgt mwgt H3a H3b H3c H6 H33 H34
ISCO_08_n ISCO_08_np mindisco malehisco mnewparty nngenagemao emplrel nemplno emplrelp nemplnop
agehigh agelow local23w regcoun23w electorate20f electorate23f ngender23""".split())

# derived-variable groupings (non-questionnaire vars)
DERIVED_GROUPS = [
    ("Vote (validated & recoded)", "mdidvote mvalid23 mpartyvote mvpartyvote mleftorright melecvote mvelecvote mvotetype23 mppartyvote".split()),
    ("Demographics (recoded)", "ageband mage mgender meducate mreldom protestant catholic methnic maordes23 mmaori".split()),
    ("Sample, mode & geography", "medium msample push murbrur mauckland maoriel_23w".split()),
    ("Most important issue — LLM coding", "mllcat missuen".split()),
    ("Most important issue — text search", "minflation menvironment mwages mclimate mhealth meconomy meducation mequality mcrime mtax mtiriti mpeople mcovid mhousing mdebt mwelfare mchange mtransport mimmigration mabortion mtrust mfreedom mstable mfarming mpension mwomen mrights mforeign".split()),
    ("Class, occupation & assets", "oesch5_moesch5 oesch8_moesch8 oesch16_moesch16 isco1 isco2 malfordind malfordhh mnewocc mempstat mfarmer mfarmerb massets oesch5_moesch5p oesch8_moesch8p oesch16_moesch16p isco1p isco2p mfarmerp miisco1 miisco2 hmisco1 hmisco2".split()),
    ("Campaign contact (recoded)", "mhomcon mstreetcon mlettcon mphoncon memailcon mtextcon mfacecon m1homcon m1streetcon m1lettcon m1phoncon m1emailcon m1textcon m1facecon".split()),
    ("Attitude scales", "mpoleff mhousetot".split()),
]
DGROUP = {v: g for g, vs in DERIVED_GROUPS for v in vs}

NICE = {  # cleaner names for derived vars
    "mvpartyvote": "Party vote 2023 (validated against marked rolls)",
    "mpartyvote": "Party vote 2023 (self-reported, incl. non-vote)",
    "mvelecvote": "Electorate vote 2023 (validated)",
    "melecvote": "Electorate vote 2023 (self-reported)",
    "mppartyvote": "Party vote 2020 (recalled)",
    "mleftorright": "Bloc voted for, 2023 (validated)",
    "mvotetype23": "Vote type from master roll",
    "mvalid23": "Validated as having voted in 2023",
    "mdidvote": "Did or did not vote — how & why",
    "ageband": "Age group",
    "mage": "Age in years",
    "mgender": "Gender",
    "meducate": "Education (simplified)",
    "methnic": "Ethnicity (prioritised)",
    "mmaori": "Māori by descent or identification",
    "maordes23": "Māori descent (from electoral roll)",
    "mreldom": "Religion",
    "murbrur": "Urban / rural",
    "mauckland": "Lives in Auckland region",
    "maoriel_23w": "On the Māori electoral roll",
    "mllcat": "Most important issue (LLM-coded category)",
    "missuen": "Number of issues mentioned",
    "oesch5_moesch5": "Social class — Oesch 5 classes",
    "oesch8_moesch8": "Social class — Oesch 8 classes",
    "oesch16_moesch16": "Social class — Oesch 16 classes",
    "mpoleff": "External political efficacy (0–1 index)",
    "massets": "Asset ownership scale (0–1)",
    "medium": "Completed online or on paper",
    "msample": "Sample component",
    "push": "First invited by post or internet",
}
LABEL_FIX = {"mleftorright": {1: "Left bloc (Lab/Grn/TPM)", 2: "Right bloc (Nat/ACT/NZF)", 3: "Did not vote"}}

MISSING_RE = re.compile(r"don.?t know|^dk$|^missing$|refused|not asked|unclass|^unknown$|not applicable|don.?t wish", re.I)

def clean_label(s):
    s = re.sub(r"^-?\d+\.\s*", "", str(s)).strip()
    s = {"act": "ACT", "Maori": "Te Pāti Māori", "Another": "Another party", "DK": "Don’t know",
         "Nonvote": "Did not vote", "Monmanual": "Non-manual", "Didnt manage": "Didn’t manage"}.get(s, s)
    s = re.sub(r"\s*\(\d+\)$", "", s)
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    return s

def short_text(name):
    lab = VLAB.get(name, name)
    lab = re.sub(r"^[A-I]\d+[a-z]*\d*[:.]\s*", "", lab)
    lab = re.sub(r"^OPINION:\s*", "", lab)
    return lab.strip()

# derived age band
age = raw["mage"]
bands = [(18, 29, "18–29"), (30, 44, "30–44"), (45, 59, "45–59"), (60, 74, "60–74"), (75, 120, "75+")]
ab = pd.Series(np.nan, index=raw.index)
for k, (lo, hi, _) in enumerate(bands, 1):
    ab[(age >= lo) & (age <= hi)] = k
raw["ageband"] = ab
VL["__ageband"] = {k: f"{k}. {b[2]}" for k, b in enumerate(bands, 1)}
LBL["ageband"] = "__ageband"
VLAB["ageband"] = "Age group"

vars_out, cols = [], {}
order = [c for c in raw.columns if c != "ageband"]
order.insert(order.index("mage"), "ageband")

for c in order:
    if c in EXCLUDE or not pd.api.types.is_numeric_dtype(raw[c]):
        continue
    s = raw[c]
    vals = sorted(set(s.dropna().unique().tolist()))
    if not vals:
        continue
    L = VL.get(LBL.get(c)) if LBL.get(c) else None
    labels, missing, kind = {}, [], None
    if L:
        L = {int(k): clean_label(v) for k, v in L.items()}
        if set(vals) <= {0, 1} and list(L) == [1]:
            kind = "multi"; labels = {0: "Not selected", 1: L[1]}
        else:
            labels = dict(L)
            for v in vals:
                if int(v) not in labels:
                    labels[int(v)] = f"Code {int(v)} (unlabelled)"; missing.append(int(v))
            missing += [k for k, t in L.items() if MISSING_RE.search(t)]
            subs = [k for k in labels if k not in missing]
            kind = "scale" if (0 in subs and 10 in subs and len(subs) == 11) else "cat"
    else:
        if set(vals) <= {0, 1}:
            kind = "multi" if c.startswith(("m", "protestant", "catholic", "maor")) else "multi"
            labels = {0: "No", 1: "Yes"}
        else:
            kind = "num"
            if c == "mhousetot":
                missing = [99]
    if c in LABEL_FIX:
        kind = "cat"; labels = dict(LABEL_FIX[c])
    if all(float(v).is_integer() for v in vals) or kind != "num":
        arr = [None if pd.isna(x) else int(x) for x in s.tolist()]
    else:
        arr = [None if pd.isna(x) else round(float(x), 4) for x in s.tolist()]

    m = re.match(r"^([A-I])(\d+)([a-z]?)(\d*)$", c)
    qnum = f"{m.group(1)}{m.group(2)}" if m else None
    if m:
        section = SECTIONS[m.group(1)]
        battery = qnum if (m.group(3) or m.group(4)) else None
        if c.startswith("A6"):
            battery = "A6" + c[3]  # contact grid: one battery per channel
        if c.startswith("C4"):
            battery = c[:3]
    else:
        section = "Derived & coded"
        battery = None
    stem = stems.get(qnum, "") if qnum else ""
    item = items.get((qnum, m.group(3))) if (m and m.group(3) and not m.group(4) and not c.startswith("A6")) else None
    short = NICE.get(c) or short_text(c)
    if item:
        # PDF item text is the untruncated version; keep it if it plausibly matches
        a = re.sub(r"\W", "", item.lower())[:12]
        b = re.sub(r"\W", "", short.lower())
        if kind != "multi" and ((a and a in b) or len(VLAB.get(c, "")) >= 78):
            short_item = item
        else:
            short_item = None
    else:
        short_item = None
    subs_n = len([k for k in labels if k not in missing]) if labels else 0
    v = {
        "n": c,
        "q": qnum or "",
        "t": short,  # short label (from dataset)
        "it": short_item or "",
        "tr": 1 if len(VLAB.get(c, "")) >= 78 else 0,  # dataset label was cut off at 80 chars  # full item wording from questionnaire
        "st": stem,  # question stem from questionnaire
        "sec": section,
        "grp": DGROUP.get(c, ""),
        "bat": battery or "",
        "k": kind,
        "lab": {str(k): t for k, t in labels.items()},
        "miss": sorted(set(missing)),
        "bk": kind in ("cat", "multi") and 2 <= subs_n <= 16 and not c.startswith("A6"),
    }
    vars_out.append(v)
    cols[c] = arr

W = {k: [round(float(x), 5) if not pd.isna(x) else 0 for x in raw[k].tolist()] for k in ("vwgt", "bwgt", "mwgt")}

payload = {
    "meta": {
        "title": "New Zealand Election Study 2023",
        "n": int(len(raw)),
        "source": "NZES 2023 release 100227 (doi:10.26193/HHMEUZ)",
        "official": {  # 2023 general election, final party-vote result (Electoral Commission)
            "Labour": 26.91, "National": 38.06, "Green": 11.60, "ACT": 8.64,
            "NZ First": 6.08, "Maori": 3.08, "Another": 5.63, "turnout": 78.2,
        },
    },
    "vars": vars_out,
    "cols": cols,
    "w": W,
}
js = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
tpl = open(TEMPLATE, encoding="utf-8").read()
out = tpl.replace("/*__DATA__*/null", js)
open(OUT, "w", encoding="utf-8").write(out)
print(f"wrote {OUT}: {len(vars_out)} variables, {len(out)/1e6:.2f} MB")
