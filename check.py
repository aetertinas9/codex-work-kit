from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
SECTIONS = ("목표", "입력", "기준", "결과물", "완료 기준", "안 할 것")


def contract_checks(sections):
    return [("명세 검사", False, "[명세]에서 유형별 완료 기준 검사를 구현해야 함")]


def main():
    task = ROOT / "TASK.md"
    if not task.is_file():
        print("FAIL: TASK.md 없음")
        return 1
    text = task.read_text(encoding="utf-8")
    content = re.sub(r"(?m)^#{1,6} .*$", "", text).strip()
    if not content:
        print("SKIP: TASK.md 비어 있음 — 명세 전")
        return 0
    parts = re.split(r"(?m)^## ([^\n]+)\n?", text)
    sections = {parts[i].strip(): parts[i + 1].strip()
                for i in range(1, len(parts), 2)}
    failures = [f"빈 절: {name}" for name in SECTIONS if not sections.get(name)]
    outputs = re.findall(r"(?m)^- `([^`]+)`\s*$", sections.get("결과물", ""))
    if not outputs:
        failures.append("결과물 경로 없음: '- `상대경로`' 형식 필요")
    for name in outputs:
        path = (ROOT / name).resolve()
        inside = path == ROOT or ROOT in path.parents
        if not inside or not path.is_file() or path.stat().st_size == 0:
            failures.append(f"결과물 없음, 비어 있음, 경로 범위 밖: {name}")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    checks = contract_checks(sections)
    if not checks:
        print("FAIL: 완료 기준 검사 없음")
        return 1
    for criterion, passed, evidence in checks:
        print(f"{'PASS' if passed else 'FAIL'}: {criterion}: {evidence}")
    return 0 if all(passed for _, passed, _ in checks) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
