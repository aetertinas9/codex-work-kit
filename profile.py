import csv
import io
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

TEXT_EXT = {".csv", ".tsv", ".txt"}
MAX_COLS, MAX_FINDINGS, MAX_EX, TOP, CUT = 40, 25, 3, 5, 20
BLANK_LIKE = {"na", "n/a", "null", "none", "nan", "-", "없음", "미정"}
KEY_NAME = re.compile(r"(?i)(id|번호|코드|key|키)")
NUM = re.compile(r"^(?P<pre>[$₩€¥£])?\s*(?P<num>[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
                 r"\s*(?P<suf>%|[A-Za-z가-힣]{1,6})?$")
YMD = re.compile(r"^(\d{4})([-/.])(\d{1,2})\2(\d{1,2})([ T]\d{1,2}:\d{2}(?::\d{2})?)?$")
DMY = re.compile(r"^(\d{1,2})([-/.])(\d{1,2})\2(\d{4})$")
COMPACT = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
KO = re.compile(r"^(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일$")


def mkdate(y, m, d):
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def as_date(s):
    m = YMD.match(s)
    if m:
        y, sep, mo, d, t = m.groups()
        dt = mkdate(y, mo, d)
        return ("YMD", sep, bool(t)), dt, len(mo) == 2 and len(d) == 2, dt is not None
    m = KO.match(s)
    if m:
        dt = mkdate(*m.groups())
        return ("KO", "", False), dt, True, dt is not None
    m = COMPACT.match(s)
    if m:
        dt = mkdate(*m.groups())
        return (("COMPACT", "", False), dt, True, True) if dt else None
    m = DMY.match(s)
    if m:
        a, sep, b, y = m.groups()
        ok = mkdate(y, b, a) is not None or mkdate(y, a, b) is not None
        return ("DMY", sep, False), None, True, ok
    return None


def date_label(key, padded):
    kind, sep, timed = key
    if kind == "YMD":
        label = "YYYY{0}{1}{0}{2}".format(sep, "MM" if padded else "M", "DD" if padded else "D")
        return label + (" 시각" if timed else "")
    if kind == "KO":
        return "YYYY년 M월 D일"
    if kind == "COMPACT":
        return "YYYYMMDD"
    return "D{0}M{0}YYYY 또는 M{0}D{0}YYYY".format(sep)


def ex(lines):
    lines = list(lines)
    text = "·".join(str(n) for n in lines[:MAX_EX])
    return "줄 " + text + (" 외" if len(lines) > MAX_EX else "")


def q(v):
    v = v.replace("\n", " ").replace("|", "\\|")
    return '"' + (v if len(v) <= CUT else v[:CUT] + "…") + '"'


def fmt(x):
    return ("%.4f" % x).rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


def column(name, cells, findings):
    nonblank = [(ln, v) for ln, v in cells if v.strip()]
    blanks = [ln for ln, v in cells if not v.strip()]
    vals = [(ln, v.strip()) for ln, v in nonblank]
    n = len(vals)
    dates, nums, other = [], [], []
    for ln, s in vals:
        d = as_date(s)
        if d:
            dates.append((ln, s, d))
            continue
        m = NUM.match(s)
        if m:
            nums.append((ln, s, m))
        else:
            other.append((ln, s))
    kind = "글자"
    if n and len(dates) >= 0.8 * n:
        kind = "날짜"
    elif n and len(nums) >= 0.8 * n:
        kind = "숫자"
    c = "`%s`" % name
    if blanks:
        findings.append("%s 빈칸 %d건 (%s)" % (c, len(blanks), ex(blanks)))
    like = [(ln, s) for ln, s in vals if s.casefold() in BLANK_LIKE]
    if like:
        shown = "·".join(q(s) for s in sorted({s for _, s in like}))
        findings.append("%s 빈칸으로 읽힐 수 있는 값 %s %d건. 실제 값일 수 있다 (%s)"
                        % (c, shown, len(like), ex(ln for ln, _ in like)))
    spaced = [ln for ln, v in nonblank if v != v.strip()]
    if spaced:
        findings.append("%s 앞뒤 공백 %d건 (%s)" % (c, len(spaced), ex(spaced)))
    span, mixed = "-", False
    if kind == "글자":
        groups = defaultdict(Counter)
        for ln, v in nonblank:
            groups[" ".join(v.split()).casefold()][v] += 1
        varied = [g for g in groups.values() if len(g) > 1]
        if varied:
            parts = [" · ".join(q(v) for v, _ in g.most_common(3)) for g in varied[:3]]
            minor = sorted(ln for ln, v in nonblank
                           for g in varied if v in g and v != g.most_common(1)[0][0])
            findings.append("%s 같은 값의 표기 차이 %d묶음: %s (%s)"
                            % (c, len(varied), " / ".join(parts), ex(minor)))
    elif kind == "숫자":
        forms = Counter()
        odd = []
        for ln, s, m in nums:
            tag = m.group("pre") or m.group("suf")
            form = "기호·단위 붙음(%s)" % tag if tag else ("천 단위 쉼표" if "," in m.group("num") else "일반")
            forms[form] += 1
            if form != "일반":
                odd.append(ln)
        if odd:
            findings.append("%s 숫자 표기 섞임: %s (%s)" % (
                c, ", ".join("%s %d" % kv for kv in forms.most_common()), ex(sorted(odd))))
        rest = sorted([(ln, s) for ln, s in other] + [(ln, s) for ln, s, _ in dates])
        if rest:
            mixed = True
            findings.append("%s 숫자로 읽히지 않는 값 %d건: %s (%s)" % (
                c, len(rest), ", ".join(q(s) for s in sorted({s for _, s in rest})[:3]),
                ex(ln for ln, _ in rest)))
        xs = [(float(m.group("num").replace(",", "")), ln) for ln, _, m in nums]
        neg = [ln for x, ln in xs if x < 0]
        if neg:
            findings.append("%s 음수 %d건 (%s)" % (c, len(neg), ex(neg)))
        values = sorted(x for x, _ in xs)
        if len(values) >= 20:
            q1, _, q3 = statistics.quantiles(values, n=4)
            lo, hi = q1 - 3 * (q3 - q1), q3 + 3 * (q3 - q1)
            far = [ln for x, ln in xs if x < lo or x > hi]
            if far and q3 > q1:
                findings.append("%s 극단값 %d건(사분위 범위 3배 밖, %s~%s 밖) (%s)"
                                % (c, len(far), fmt(lo), fmt(hi), ex(sorted(far))))
        if values:
            span = "%s ~ %s, 0: %d" % (fmt(values[0]), fmt(values[-1]), values.count(0.0))
    else:
        labels, padded = Counter(), defaultdict(lambda: True)
        first, bad, unsure, days = {}, [], [], []
        for ln, s, (key, dt, pad, ok) in dates:
            labels[key] += 1
            padded[key] = padded[key] and pad
            first.setdefault(key, ln)
            if not ok:
                bad.append(ln)
            if key[0] == "DMY":
                unsure.append(ln)
            if dt:
                days.append(dt)
        if len(labels) > 1:
            text = ", ".join("%s %d" % (date_label(k, padded[k]), v) for k, v in labels.most_common())
            findings.append("%s 날짜 형식 %d종: %s (%s)" % (
                c, len(labels), text, ex(sorted(first[k] for k, _ in labels.most_common()[1:]))))
        if bad:
            findings.append("%s 있을 수 없는 날짜 %d건 (%s)" % (c, len(bad), ex(bad)))
        if unsure:
            findings.append("%s 일·월 순서를 알 수 없는 형식 %d건 (%s)" % (c, len(unsure), ex(unsure)))
        rest = sorted(other + [(ln, s) for ln, s, _ in nums])
        if rest:
            mixed = True
            findings.append("%s 날짜로 읽히지 않는 값 %d건: %s (%s)" % (
                c, len(rest), ", ".join(q(s) for s in sorted({s for _, s in rest})[:3]),
                ex(ln for ln, _ in rest)))
        if days:
            span = "%s ~ %s" % (min(days).isoformat(), max(days).isoformat())
    counts = Counter(s for _, s in vals)
    if n > TOP and len(counts) == n:
        top = "모두 다름"
    else:
        top = ", ".join("%s %d" % (q(v), k) for v, k in counts.most_common(TOP))
    return kind, len(counts), {"형식": kind + (" (섞임)" if mixed else ""), "빈칸": len(blanks),
                               "고유": len(counts), "범위": span, "상위 값": top or "-"}


def keys(header, rows, kinds, distinct, findings):
    total, found = len(rows), 0
    for i, name in enumerate(header):
        filled = [(ln, r) for ln, r in rows if r[i].strip()]
        if found >= 2 or total < 2 or len(filled) < 0.9 * total or kinds[i] == "날짜":
            continue
        if kinds[i] == "숫자" and not KEY_NAME.search(name):
            continue
        if distinct[i] < 0.9 * len(filled) or distinct[i] == len(filled):
            continue
        groups = defaultdict(list)
        for ln, r in filled:
            groups[r[i].strip()].append((ln, tuple(r)))
        dup = {k: g for k, g in groups.items() if len(g) > 1}
        same = [k for k, g in dup.items() if len({r for _, r in g}) == 1]
        clash = [k for k in dup if k not in same]
        cols = Counter(header[j] for k in clash for j in range(len(header))
                       if len({r[j] for _, r in dup[k]}) > 1)
        detail = ", ".join("`%s` %s" % (k, ex(ln for ln, _ in dup[k])) for k in (clash + same)[:MAX_EX])
        findings.append("키 후보 `%s`: 여러 줄에 나온 값 %d개. 줄 전체가 같은 것 %d개, 다른 칸이 있는 충돌 %d개%s (예: %s)"
                        % (name, len(dup), len(same), len(clash),
                           "(다른 칸: %s)" % ", ".join(cols) if cols else "", detail))
        found += 1


def read_table(path):
    data = path.read_bytes()
    for enc in ("utf-8-sig", "cp949", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    note = {"utf-8-sig": "utf-8" + (" BOM" if data.startswith(b"\xef\xbb\xbf") else ""),
            "cp949": "cp949", "latin-1": "latin-1(글자가 깨졌을 수 있음)"}[enc]
    delim = "\t" if path.suffix.lower() == ".tsv" else ","
    if delim == ",":
        sample = "\n".join(text.splitlines()[:20])
        try:
            delim = csv.Sniffer().sniff(sample, delimiters=",\t;|").delimiter
        except csv.Error:
            delim = ","
        first = text.splitlines()[:1]
        if first and delim != "," and len(next(csv.reader(first, delimiter=delim))) < 2:
            delim = ","
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
    rows, end, empty = [], 0, 0
    for row in reader:
        start, end = end + 1, reader.line_num
        if not row:
            empty += 1
            continue
        rows.append((start, row))
    return note, delim, rows, empty


def profile(path):
    out = []
    note, delim, rows, empty = read_table(path)
    shown = {"\t": "탭", ",": "쉼표", ";": "세미콜론", "|": "세로선"}[delim]
    if not rows:
        return ["## %s" % path, "", "인코딩 %s. 빈 파일이다." % note, ""]
    header = [h.strip() for h in rows[0][1]]
    data = rows[1:]
    width = len(header)
    findings = []
    names = Counter(header)
    if any(not h for h in header):
        findings.append("머리글에 빈 열 이름 %d개" % sum(1 for h in header if not h))
    if any(k > 1 for h, k in names.items() if h):
        findings.append("머리글에 같은 열 이름: %s" % ", ".join("`%s`" % h for h, k in names.items() if h and k > 1))
    ragged = [ln for ln, r in data if len(r) != width]
    if ragged:
        findings.append("칸 수가 머리글(%d칸)과 다른 줄 %d줄 (%s)" % (width, len(ragged), ex(ragged)))
    if empty:
        findings.append("빈 줄 %d줄" % empty)
    data = [(ln, (r + [""] * width)[:width]) for ln, r in data]
    seen, extra = defaultdict(list), 0
    for ln, r in data:
        seen[tuple(r)].append(ln)
    same = [g for g in seen.values() if len(g) > 1]
    if same:
        extra = sum(len(g) - 1 for g in same)
        findings.append("모든 칸이 같은 줄 %d줄(%d묶음) (예: %s)" % (
            extra, len(same), ", ".join("줄 " + "=".join(map(str, g[:3])) for g in same[:MAX_EX])))
    loose = defaultdict(set)
    for ln, r in data:
        loose[tuple(" ".join(v.split()).casefold() for v in r)].add(tuple(r))
    near = [k for k, g in loose.items() if len(g) > 1]
    if near:
        lines = sorted(ln for k in near for ln, r in data
                       if tuple(" ".join(v.split()).casefold() for v in r) == k)
        findings.append("공백·대소문자만 다른 같은 줄 %d묶음 (%s)" % (len(near), ex(lines)))
    table, kinds, distinct = [], [], []
    for i, name in enumerate(header):
        kind, k, row = column(name or "(빈 이름 %d)" % (i + 1), [(ln, r[i]) for ln, r in data], findings)
        kinds.append(kind)
        distinct.append(k)
        table.append((name or "(빈 이름 %d)" % (i + 1), row))
    keys(header, data, kinds, distinct, findings)
    out += ["## %s" % path, "",
            "인코딩 %s, 구분자 %s, 데이터 %d줄(머리글 제외), 열 %d개." % (note, shown, len(data), width), "",
            "### 확인할 것", ""]
    out += ["- " + f for f in findings[:MAX_FINDINGS]] or ["- 없음"]
    if len(findings) > MAX_FINDINGS:
        out.append("- 외 %d건" % (len(findings) - MAX_FINDINGS))
    out += ["", "### 열 요약", "", "| 열 | 형식 | 빈칸 | 고유 | 범위 | 상위 값 |", "|---|---|---|---|---|---|"]
    for name, row in table[:MAX_COLS]:
        out.append("| %s | %s | %d | %d | %s | %s |" % (
            name.replace("|", "\\|"), row["형식"], row["빈칸"], row["고유"], row["범위"], row["상위 값"]))
    if len(table) > MAX_COLS:
        out.append("| 외 %d열 | | | | | |" % (len(table) - MAX_COLS))
    return out + [""]


def main(argv):
    if not argv:
        print("사용: python3 profile.py <파일 또는 폴더> [...] > profile.md")
        return 2
    files, out, code = [], ["# 입력 프로파일", "", "`python3 profile.py %s` 결과. 줄 번호는 파일의 줄이고 머리글이 1이다."
                            % " ".join(argv), ""], 0
    for arg in argv:
        p = Path(arg)
        if p.is_dir():
            files += sorted(f for f in p.iterdir() if f.is_file() and f.suffix.lower() in (".csv", ".tsv"))
        else:
            files.append(p)
    for p in files:
        if not p.is_file():
            out += ["## %s" % p, "", "읽지 못함: 파일이 없다.", ""]
            code = 1
        elif p.suffix.lower() not in TEXT_EXT:
            out += ["## %s" % p, "", "건너뜀: CSV·TSV가 아니다(%s). 표로 바꿔 다시 넣는다." % p.suffix, ""]
        else:
            try:
                out += profile(p)
            except (OSError, csv.Error) as exc:
                out += ["## %s" % p, "", "읽지 못함: %s" % exc, ""]
                code = 1
    print("\n".join(out).rstrip())
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
