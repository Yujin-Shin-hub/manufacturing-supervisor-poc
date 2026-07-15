"""
작성자 : 신유진
작성일 : 2026-07-06
작성 목적: 표시 포맷 도구. DataFrame을 markdown으로 변환한다.
변경 이력:
  - 2026-07-06: 단계 0.5 스켈레톤 생성
  - 2026-07-06: 단계 1 markdown 변환 구현
"""

from __future__ import annotations


def df_to_markdown(df) -> str:
    """Convert a DataFrame to markdown text."""
    if df is None:
        raise ValueError("df is required")
    if df.empty:
        return "_No rows_"

    columns = [str(column) for column in df.columns]
    rows = df.astype(str).values.tolist()
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header, separator, *body])
