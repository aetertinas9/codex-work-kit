# 작업 폴더 설정

이 파일이 있는 폴더를 키트 폴더, Codex를 연 현재 폴더를 작업 폴더라 한다. 사용자가 이 파일대로 설정하라고 하면 아래 순서만 수행한다. 과제는 풀지 않는다.

1. 키트 폴더의 AGENTS.md, PROMPTS.md, TASK.md, DECISIONS.md, check.py, profile.py, LUNA.md, luna.sh 여덟 개를 작업 폴더에 복사한다. 복사할 파일은 열어 읽지 않고 복사만 한다. 작업 폴더에 같은 이름의 파일이 있으면 덮어쓰지 않고 건너뛴다. 작업 폴더에 AGENTS.md가 이미 있으면 과제가 준 규칙이므로 그대로 두고 키트의 AGENTS.md를 RULES.md로 복사한다.
2. 사용자가 지난 작업의 lessons.md 경로를 주었고 작업 폴더에 lessons.md가 없으면 그 파일을 lessons.md로 복사한다.
3. `mkdir -p .handoff/todo .handoff/done .handoff/failed`와 `chmod +x luna.sh`를 실행한다.
4. `command -v git`, `command -v python3`, `command -v codex`로 명령이 있는지 본다. git이 없으면 커밋, python3가 없으면 check.py와 profile.py, codex가 없으면 기록 모델 호출이 안 된다고 보고한다. `date +%z`가 `+0000`이면 기록 시각이 UTC로 남는다고 알리고 두 창에서 `export TZ=<시간대>`를 친 뒤 codex와 luna.sh를 켜라고 보고한다.
5. 키트 폴더, `.git`, `.gitignore`는 고치지 않는다. 커밋하지 않고 luna.sh는 실행하지 않는다. 설정만으로는 카드를 만들지 않는다.
6. 복사가 끝나면 작업 폴더의 AGENTS.md(RULES.md로 넣었으면 RULES.md)와 PROMPTS.md를 읽고 그 규칙을 따른다. 과제가 준 AGENTS.md가 있으면 그쪽이 우선한다.
7. 같은 메시지에 `[시작]`이 있으면 PROMPTS.md의 `[시작]`을 이어서 수행하고 그 카드의 `한 일`에 넣은 파일과 건너뛴 파일을 적는다. `[시작]`이 없으면 파일마다 `넣음: 파일` 또는 `건너뜀: 파일 이미 있음` 한 줄과 4번 결과만 보고하고 멈춘다.
