"""
작성자  : 신유진
작성일  : 2026-07-06
작성 목적: CLI 진입점 — --mode report|ask 로 Supervisor 실행
변경 이력:
  - 2026-07-06: 단계 0.5 스캐폴딩 — 스텁 생성 (구현은 단계 6)
  - 2026-07-06: 단계 5 report 실행 검증을 위한 최소 CLI 파싱과 리포트 출력 구현
  - 2026-07-06: 단계 6 EventBus 콘솔 로거 구독 연결
"""

from __future__ import annotations

import argparse

from src.events import ConsoleEventLogger, EventBus
from src.supervisor import Supervisor


DEFAULT_ASOF = "2026-04-15 14:00"


def _parser() -> argparse.ArgumentParser:
    """Supervisor 실행용 CLI 인자를 정의한다."""
    parser = argparse.ArgumentParser(description="Manufacturing Supervisor PoC")
    parser.add_argument("--mode", choices=["report", "ask"], default="report")
    parser.add_argument("--asof", default=DEFAULT_ASOF)
    parser.add_argument("--q", "--query", dest="query", default=None)
    parser.add_argument(
        "--llm-provider",
        choices=["auto", "qwen", "openai"],
        default=None,
        help="LLM provider for routing in ask mode",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI 진입점."""
    args = _parser().parse_args(argv)
    event_bus = EventBus()
    event_bus.subscribe(ConsoleEventLogger())
    report = Supervisor(event_bus=event_bus).run(
        mode=args.mode,
        asof=args.asof,
        query=args.query,
        llm_provider=args.llm_provider,
    )
    print(report.report_markdown)


if __name__ == "__main__":
    main()
