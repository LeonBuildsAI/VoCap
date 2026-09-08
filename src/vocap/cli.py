"""
vocap CLI — 抖音视频文案提取工具
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from typing import NoReturn

from vocap.errors import VoCapError
from vocap.formatter import format_results
from vocap.models import Transcript, VideoInfo
from vocap.pipeline import extract
from vocap.url_resolver import extract_url_from_text


def main() -> None:
    signal.signal(signal.SIGINT, _handle_sigint)

    parser = argparse.ArgumentParser(
        description="vocap — 从抖音视频链接提取口播文案",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            '  vocap "https://v.douyin.com/iRNBho5/"\n'
            '  vocap "7.46 复制打开抖音...https://v.douyin.com/xxx/ ..."'
            "  # 直接粘贴分享文本\n"
            '  vocap "https://www.douyin.com/video/73801234" -f markdown\n'
            "  vocap url1 url2 url3  # 批量\n"
            '  vocap urls.txt --cookies-from-browser chrome\n'
        ),
    )
    parser.add_argument(
        "urls",
        nargs="+",
        help="抖音视频链接、分享文本、或包含链接的文本文件路径",
    )
    parser.add_argument(
        "-f",
        "--format",
        default="json",
        choices=["json", "markdown", "md", "srt", "txt"],
        help="输出格式 (默认: json)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="输出文件路径（不指定则打印到终端）",
    )
    parser.add_argument(
        "-m",
        "--model",
        default="",
        help="Whisper 模型 (默认: large-v3-turbo)",
    )
    parser.add_argument(
        "--cookies-from-browser",
        default="",
        metavar="BROWSER",
        help=(
            "从本机浏览器读取 cookie（chrome / safari / chrome:Default）。"
            "先打开抖音网页并退出浏览器"
        ),
    )
    parser.add_argument(
        "--cookies",
        default="",
        metavar="FILE",
        help="Netscape 格式的 cookies.txt 文件路径",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="下载遇 403/限流时的重试次数 (默认: 3)",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=3.0,
        help="批量提取时两条之间的间隔秒数 (默认: 3)",
    )
    args = parser.parse_args()

    if args.output:
        out_dir = os.path.dirname(args.output)
        if out_dir and not os.path.isdir(out_dir):
            parser.error(f"输出目录不存在: {out_dir}")

    if args.cookies and args.cookies_from_browser:
        parser.error("不能同时使用 --cookies 与 --cookies-from-browser")
    if args.cookies and not os.path.isfile(args.cookies):
        parser.error(f"cookie 文件不存在: {args.cookies}")
    if args.retries < 0:
        parser.error("--retries 不能为负数")
    if args.sleep < 0:
        parser.error("--sleep 不能为负数")

    urls = _collect_urls(args.urls)
    if not urls:
        parser.error("未找到有效的抖音视频链接")

    results: list[tuple[VideoInfo, Transcript, float]] = []
    failed = 0
    for i, url in enumerate(urls):
        if i > 0 and args.sleep > 0:
            print(f"\n  → 距上一条间隔 {args.sleep}s...", file=sys.stderr)
            time.sleep(args.sleep)

        label = f"[{i + 1}/{len(urls)}] " if len(urls) > 1 else ""
        print(f"\n{label}处理: {url}", file=sys.stderr)

        try:
            result = extract(
                url,
                model_size=args.model,
                cookies_from_browser=args.cookies_from_browser,
                cookiefile=args.cookies,
                download_retries=args.retries,
            )
            results.append(result)
        except Exception as e:
            tag = "失败" if isinstance(e, VoCapError) else "未知错误"
            print(f"  ✗ {tag}: {e}", file=sys.stderr)
            failed += 1
            if len(urls) == 1:
                sys.exit(1)

    if not results:
        print(f"\n所有 {failed} 个链接处理失败", file=sys.stderr)
        sys.exit(1)

    if failed > 0:
        print(f"\n完成: {len(results)} 成功, {failed} 失败", file=sys.stderr)

    output_text = format_results(results, args.format)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_text)
        print(f"\n已保存到 {args.output}", file=sys.stderr)
    else:
        print(output_text)

    if failed > 0:
        sys.exit(2)


def _collect_urls(inputs: list[str]) -> list[str]:
    """从命令行参数收集所有有效的抖音 URL。"""
    urls: list[str] = []
    for item in inputs:
        if os.path.isfile(item):
            with open(item, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    found = extract_url_from_text(line)
                    if found:
                        urls.append(found)
        else:
            found = extract_url_from_text(item)
            if found:
                urls.append(found)
    return urls


def _handle_sigint(sig: int, frame: object) -> NoReturn:
    print("\n\n中断，正在退出...", file=sys.stderr)
    sys.exit(130)
