#!/usr/bin/env python3
"""
模型比較測試腳本

比較不同 Gemini 模型在相同 Skills 配置下的效能差異。

使用方式：
    cd backend
    python scripts/compare_models.py --pdf path/to/test.pdf
    python scripts/compare_models.py --mock  # 使用 mock 資料測試

環境變數：
    GEMINI_API_KEY: Gemini API 金鑰（必要）
"""

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# 加入 backend 到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

import google.generativeai as genai


@dataclass
class ModelResult:
    """單一模型測試結果."""

    model_name: str
    success: bool
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    items_count: int = 0
    error: Optional[str] = None
    raw_response: Optional[str] = None
    parsed_items: list = field(default_factory=list)


@dataclass
class ComparisonReport:
    """模型比較報告."""

    skill_version: str
    test_content_length: int
    results: list[ModelResult] = field(default_factory=list)

    def print_report(self):
        """輸出比較報告."""
        print("\n" + "=" * 70)
        print("📊 模型比較報告")
        print("=" * 70)
        print(f"Skills 版本: {self.skill_version}")
        print(f"測試內容長度: {self.test_content_length} 字元")
        print("-" * 70)

        # 表頭
        print(f"{'模型':<30} {'狀態':<8} {'延遲':<10} {'Token':<12} {'項目數':<8}")
        print("-" * 70)

        for r in self.results:
            status = "✅ 成功" if r.success else "❌ 失敗"
            latency = f"{r.latency_ms:.0f}ms"
            tokens = f"{r.total_tokens:,}" if r.total_tokens else "N/A"
            items = str(r.items_count) if r.success else "-"

            print(f"{r.model_name:<30} {status:<8} {latency:<10} {tokens:<12} {items:<8}")

        print("-" * 70)

        # 成功的結果比較
        successful = [r for r in self.results if r.success]
        if len(successful) >= 2:
            print("\n📈 效能分析:")

            # 延遲比較
            fastest = min(successful, key=lambda x: x.latency_ms)
            slowest = max(successful, key=lambda x: x.latency_ms)
            print(f"  最快: {fastest.model_name} ({fastest.latency_ms:.0f}ms)")
            print(f"  最慢: {slowest.model_name} ({slowest.latency_ms:.0f}ms)")
            print(f"  差異: {slowest.latency_ms / fastest.latency_ms:.1f}x")

            # Token 比較
            if all(r.total_tokens > 0 for r in successful):
                min_token = min(successful, key=lambda x: x.total_tokens)
                max_token = max(successful, key=lambda x: x.total_tokens)
                print(f"\n  最少 Token: {min_token.model_name} ({min_token.total_tokens:,})")
                print(f"  最多 Token: {max_token.model_name} ({max_token.total_tokens:,})")

            # 項目數比較
            item_counts = set(r.items_count for r in successful)
            if len(item_counts) == 1:
                print(f"\n  ✅ 所有模型提取相同數量項目: {successful[0].items_count}")
            else:
                print(f"\n  ⚠️ 模型提取項目數不一致:")
                for r in successful:
                    print(f"     {r.model_name}: {r.items_count} 項")

        print("\n" + "=" * 70)

        # 詳細項目比較（如果項目數不同）
        if len(successful) >= 2:
            self._compare_items(successful)

    def _compare_items(self, results: list[ModelResult]):
        """比較各模型提取的項目."""
        if not all(r.parsed_items for r in results):
            return

        print("\n📋 項目比較（前 3 項）:")
        print("-" * 70)

        for i in range(min(3, max(len(r.parsed_items) for r in results))):
            print(f"\n項目 #{i + 1}:")
            for r in results:
                if i < len(r.parsed_items):
                    item = r.parsed_items[i]
                    item_no = item.get("item_no", "N/A")
                    desc = item.get("description", "N/A")[:40]
                    print(f"  [{r.model_name[:20]:<20}] {item_no}: {desc}")


# 要比較的模型列表
MODELS_TO_COMPARE = [
    "gemini-2.0-flash",           # 穩定版 Flash
    "gemini-2.0-flash-lite",      # 輕量版
    "gemini-1.5-flash",           # 舊版 Flash
    "gemini-1.5-pro",             # Pro 版（較強但較貴）
    # "gemini-2.5-flash-preview-05-20",  # 預覽版（如有權限）
]


# Mock PDF 內容（用於無實際 PDF 時測試）
MOCK_PDF_CONTENT = """
--- Page 1 ---

HABITUS Design Group
FF&E SPECIFICATION BOOK
Project: SOLAIRE BAY TOWER

--- Page 2 ---

ITEM NO.: DLX-100
DESCRIPTION: King Bed
TYPE: Casegoods

Overall Dimensions:
W 2000 x D 2100 x H 1200 mm

QTY: 239 ea

Index:
@ King Deluxe Room Type A
@ King Deluxe Room Type B

--- Page 3 ---

ITEM NO.: DLX-101
DESCRIPTION: Bedside Table
TYPE: Casegoods

Overall Dimensions:
W 600 x D 450 x H 550 mm

QTY: 478 ea

Index:
@ King Deluxe Room Type A
@ King Deluxe Room Type B
@ Queen Standard Room

--- Page 4 ---

ITEM NO.: DLX-102
DESCRIPTION: Round Coffee Table
TYPE: Casegoods

Overall Dimensions:
Dia. 800 x H 450 mm

QTY: 120 ea

Index:
@ Lobby Lounge
@ Executive Lounge

--- Page 5 ---

ITEM NO.: FAB-001 @ DLX-100 King Bed
DESCRIPTION: Fabric for Headboard
TYPE: Fabric

Vendor: Morbern Europe
Pattern: Prodigy PRO 682
Color: Lt Neutral
Width: 137cm
Style: plain

QTY: 500 m
"""


def get_skill_prompt_template() -> tuple[str, str]:
    """載入 Skills prompt 模板."""
    from app.services.skill_loader import get_skill_loader

    loader = get_skill_loader()
    skill = loader.load_vendor_or_default("habitus")

    if skill:
        version = skill.version
        template = skill.prompts.parse_specification.user_template
        return version, template
    else:
        # Fallback
        return "default", """
請分析 PDF 內容，提取 BOQ 項目。

輸出 JSON 陣列，每項包含：
- item_no: 項目編號
- description: 品名描述
- dimension: 尺寸
- qty: 數量
- uom: 單位

<document>
{pdf_content}
</document>

請只返回 JSON 數組。
"""


async def test_model(
    model_name: str,
    prompt: str,
    api_key: str,
) -> ModelResult:
    """測試單一模型."""

    print(f"  測試 {model_name}...", end=" ", flush=True)

    start_time = time.time()

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)

        response = await asyncio.wait_for(
            asyncio.to_thread(model.generate_content, prompt),
            timeout=120,
        )

        latency_ms = (time.time() - start_time) * 1000

        # 解析 token 使用量
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0)
            output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0)

        # 解析 JSON 結果
        raw_text = response.text.strip()

        # 清理 markdown code block
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            raw_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        try:
            parsed_items = json.loads(raw_text)
            if not isinstance(parsed_items, list):
                parsed_items = []
        except json.JSONDecodeError:
            parsed_items = []

        print(f"✅ {latency_ms:.0f}ms, {len(parsed_items)} 項目")

        return ModelResult(
            model_name=model_name,
            success=True,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            items_count=len(parsed_items),
            raw_response=raw_text[:500],
            parsed_items=parsed_items,
        )

    except asyncio.TimeoutError:
        latency_ms = (time.time() - start_time) * 1000
        print(f"❌ 超時")
        return ModelResult(
            model_name=model_name,
            success=False,
            latency_ms=latency_ms,
            error="Timeout after 120s",
        )

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        print(f"❌ {str(e)[:50]}")
        return ModelResult(
            model_name=model_name,
            success=False,
            latency_ms=latency_ms,
            error=str(e),
        )


async def run_comparison(
    pdf_content: str,
    models: list[str],
    api_key: str,
) -> ComparisonReport:
    """執行模型比較."""

    # 載入 Skills
    skill_version, prompt_template = get_skill_prompt_template()

    # 建立完整 prompt
    prompt = prompt_template.format(
        pdf_content=pdf_content,
        categories_instruction="",
    )

    print(f"\n📋 使用 Skills 版本: {skill_version}")
    print(f"📝 Prompt 長度: {len(prompt)} 字元")
    print(f"🔄 測試 {len(models)} 個模型...\n")

    report = ComparisonReport(
        skill_version=skill_version,
        test_content_length=len(pdf_content),
    )

    # 依序測試各模型（避免 rate limit）
    for model_name in models:
        result = await test_model(model_name, prompt, api_key)
        report.results.append(result)

        # 間隔避免 rate limit
        if model_name != models[-1]:
            await asyncio.sleep(1)

    return report


def main():
    parser = argparse.ArgumentParser(
        description="比較不同 Gemini 模型在相同 Skills 下的效能",
    )
    parser.add_argument(
        "--pdf",
        type=str,
        help="測試用 PDF 檔案路徑",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="使用內建 mock 資料測試",
    )
    parser.add_argument(
        "--models",
        type=str,
        nargs="+",
        default=MODELS_TO_COMPARE,
        help="要比較的模型列表",
    )

    args = parser.parse_args()

    # 檢查 API Key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ 錯誤: 請設定 GEMINI_API_KEY 環境變數")
        sys.exit(1)

    # 取得測試內容
    if args.pdf:
        # 從 PDF 提取文字
        import fitz  # PyMuPDF

        pdf_path = Path(args.pdf)
        if not pdf_path.exists():
            print(f"❌ 錯誤: 找不到檔案 {pdf_path}")
            sys.exit(1)

        doc = fitz.open(str(pdf_path))
        pdf_content = ""
        for i, page in enumerate(doc):
            pdf_content += f"\n--- Page {i + 1} ---\n"
            pdf_content += page.get_text()
        doc.close()

        print(f"📄 載入 PDF: {pdf_path.name} ({len(pdf_content)} 字元)")

    elif args.mock:
        pdf_content = MOCK_PDF_CONTENT
        print("📄 使用 Mock 資料測試")

    else:
        print("❌ 錯誤: 請指定 --pdf 或 --mock")
        parser.print_help()
        sys.exit(1)

    # 執行比較
    report = asyncio.run(run_comparison(
        pdf_content=pdf_content,
        models=args.models,
        api_key=api_key,
    ))

    # 輸出報告
    report.print_report()


if __name__ == "__main__":
    main()
