# update-claude

Claude Code CLI가 npm으로 깔렸는지, Homebrew로 깔렸는지, 지금 몇 버전인지 — 업데이트할 때마다 헷갈려서 만든 스크립트.

## 요구 사항

- Python 3.10+
- `npm` (버전 조회용)
- `claude` CLI가 PATH에 있어야 함

## 사용법

```bash
# 기본 — 설치 방식 자동 감지 후 업데이트
python3 update_claude.py

# 비교만 하고 설치는 안 함
python3 update_claude.py --dry-run

# 설치 방식 지정
python3 update_claude.py --method homebrew
python3 update_claude.py --method npm
```

## 뭘 해 주나

1. `claude` 실행 파일 위치 확인
2. npm / Homebrew 중 어떤 방식인지 추정
3. 현재 버전 vs 최신 버전 비교
4. 구버전이면 자동 업데이트
   - npm → `npm install -g @anthropic-ai/claude-code@latest`
   - Homebrew → `brew upgrade --cask claude-code`