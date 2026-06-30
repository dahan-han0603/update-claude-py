#!/usr/bin/env python3
import argparse
import json
import logging
import re
import subprocess
import sys
from pathlib import Path

LOG_FILE = "claude_update.log"
NPM_PACKAGE = "@anthropic-ai/claude-code"
BREW_CASK = "claude-code"


class ColorFormatter(logging.Formatter):
    COLORS = {
        "INFO": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "RESET": "\033[0m",
    }

    def __init__(self):
        super().__init__(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def format(self, record):
        color = self.COLORS.get(record.levelname, "")
        record.msg = f"{color}{record.msg}{self.COLORS['RESET']}"
        return super().format(record)


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("ClaudeUpdater")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColorFormatter())
    logger.addHandler(console_handler)

    return logger


logger = setup_logger()


def run_command(command, capture_output=True):
    """쉘 명령어를 실행하고 (성공 여부, stdout)을 반환합니다."""
    try:
        result = subprocess.run(
            command,
            shell=isinstance(command, str),
            check=True,
            stdout=subprocess.PIPE if capture_output else None,
            stderr=subprocess.PIPE if capture_output else None,
            text=True,
        )
        return True, (result.stdout or "").strip()
    except subprocess.CalledProcessError as error:
        stderr = (error.stderr or "").strip()
        return False, stderr or str(error)


def parse_version(version_str):
    """버전 문자열에서 숫자 튜플을 추출합니다. (예: '2.1.197' -> (2, 1, 197))"""
    if not version_str:
        return None
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version_str)
    if match:
        return tuple(map(int, match.groups()))
    return None


def detect_install_method(executable_path: str) -> str:
    """실행 파일 경로로 설치 방식을 추정합니다."""
    path = executable_path.lower()
    if "caskroom/claude-code" in path or "/homebrew/" in path:
        return "homebrew"
    if ".nvm" in path or ".npm" in path or "/node_modules/" in path:
        return "npm"
    return "unknown"


def get_claude_executable() -> str | None:
    success, executable_path = run_command("which claude")
    return executable_path if success and executable_path else None


def get_version_from_claude_cli() -> str | None:
    success, output = run_command("claude --version")
    if not success or not output:
        return None
    match = re.search(r"(\d+\.\d+\.\d+)", output)
    return match.group(1) if match else None


def get_npm_installed_version() -> str | None:
    success, output = run_command(f"npm ls -g {NPM_PACKAGE} --json")
    if not success or not output:
        return None
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return None
    package = data.get("dependencies", {}).get(NPM_PACKAGE, {})
    return package.get("version")


def get_latest_npm_version() -> str | None:
    success, version = run_command(f"npm view {NPM_PACKAGE} version")
    return version if success and version else None


def get_latest_homebrew_version() -> str | None:
    success, output = run_command("brew info --json=v2 --cask claude-code")
    if not success or not output:
        return None
    try:
        data = json.loads(output)
        casks = data.get("casks", [])
        if not casks:
            return None
        return casks[0].get("version")
    except (json.JSONDecodeError, IndexError, KeyError):
        return None


def resolve_install_method(requested: str, executable_path: str) -> str:
    if requested != "auto":
        return requested
    return detect_install_method(executable_path)


def get_current_version(method: str) -> str | None:
    if method == "npm":
        return get_npm_installed_version() or get_version_from_claude_cli()
    return get_version_from_claude_cli()


def get_latest_version(method: str) -> str | None:
    if method == "npm":
        return get_latest_npm_version()
    if method == "homebrew":
        return get_latest_homebrew_version()
    return get_latest_npm_version() or get_latest_homebrew_version()


def perform_update(method: str, dry_run: bool) -> tuple[bool, str]:
    if dry_run:
        return True, "dry-run 모드: 실제 업데이트는 수행하지 않습니다."

    if method == "npm":
        command = f"npm install -g {NPM_PACKAGE}@latest"
    elif method == "homebrew":
        command = f"brew upgrade --cask {BREW_CASK}"
    else:
        return False, (
            "설치 방식을 자동으로 판별하지 못했습니다. "
            "npm 또는 Homebrew로 수동 업데이트하세요."
        )

    return run_command(command, capture_output=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Claude Code CLI 버전을 점검하고 필요 시 자동 업데이트합니다."
    )
    parser.add_argument(
        "--method",
        choices=["auto", "npm", "homebrew"],
        default="auto",
        help="설치/업데이트 방식 (기본값: auto)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="버전 비교만 수행하고 실제 업데이트는 하지 않습니다.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger.info("=== Claude Code CLI 업데이트 점검 시작 ===")

    success, _ = run_command("npm -v")
    if not success:
        logger.error("npm이 설치되어 있지 않습니다. 버전 조회에 npm이 필요합니다.")
        return 1

    executable_path = get_claude_executable()
    if not executable_path:
        logger.error("Claude CLI(claude)가 시스템 경로에 존재하지 않습니다.")
        logger.info(
            "설치 권장: npm install -g @anthropic-ai/claude-code "
            "또는 brew install --cask claude-code"
        )
        return 1

    logger.info(f"실행 파일 위치 확인됨: {executable_path}")

    method = resolve_install_method(args.method, executable_path)
    if method == "unknown" and args.method == "auto":
        logger.warning(
            "설치 방식을 자동 판별하지 못했습니다. claude --version 기준으로 점검합니다."
        )
    else:
        label = {"npm": "npm", "homebrew": "Homebrew", "unknown": "알 수 없음"}[method]
        logger.info(f"설치 방식: {label}")

    current_version = get_current_version(method)
    if not current_version:
        logger.error("현재 Claude Code 버전을 확인할 수 없습니다.")
        return 1

    logger.info("최신 버전을 조회 중입니다...")
    latest_version = get_latest_version(method)
    if not latest_version:
        logger.error("최신 버전을 조회하는 데 실패했습니다. 네트워크 연결을 확인하세요.")
        return 1

    current_tuple = parse_version(current_version)
    latest_tuple = parse_version(latest_version)
    if current_tuple is None or latest_tuple is None:
        logger.error(
            f"버전 형식을 해석할 수 없습니다. (현재: {current_version}, 최신: {latest_version})"
        )
        return 1

    logger.info(f"현재 버전: v{current_version}")
    logger.info(f"최신 버전: v{latest_version}")

    if current_tuple >= latest_tuple:
        logger.info("이미 최신 버전을 사용 중입니다. 업데이트가 필요하지 않습니다.")
        logger.info("=== 점검 및 업데이트 프로세스 종료 ===")
        print(f"\n상세 로그는 '{Path(LOG_FILE).absolute()}' 파일에 저장되었습니다.")
        return 0

    if args.dry_run:
        logger.info(
            f"새 버전(v{latest_version})이 있습니다. --dry-run 이므로 업데이트를 건너뜁니다."
        )
        logger.info("=== 점검 및 업데이트 프로세스 종료 ===")
        print(f"\n상세 로그는 '{Path(LOG_FILE).absolute()}' 파일에 저장되었습니다.")
        return 0

    logger.info(f"새 버전(v{latest_version})이 발견되었습니다. 자동 업데이트를 시작합니다...")
    success, update_output = perform_update(method, dry_run=False)
    if not success:
        logger.error(f"업데이트 중 오류가 발생했습니다:\n{update_output}")
        return 1

    logger.info("업데이트가 성공적으로 완료되었습니다!")
    if update_output:
        logger.info(update_output)

    updated_version = get_version_from_claude_cli()
    if updated_version:
        logger.info(f"업데이트 후 버전 확인: {updated_version}")
        if parse_version(updated_version) and parse_version(updated_version) < latest_tuple:
            logger.warning(
                "업데이트 후에도 최신 버전보다 낮습니다. PATH 또는 설치 방식을 확인하세요."
            )
            return 1

    logger.info("=== 점검 및 업데이트 프로세스 종료 ===")
    print(f"\n상세 로그는 '{Path(LOG_FILE).absolute()}' 파일에 저장되었습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())