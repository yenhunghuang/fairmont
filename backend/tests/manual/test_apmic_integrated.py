#!/usr/bin/env python3
"""
APMIC PrivAI 整合式 API 測試

測試 Chat Completions 與 Prompts/Fileset 整合：
- prompt_id: 引用雲端儲存的 Prompt
- fileset_id: 引用已上傳的文件集
- stream: 串流回應

分析與 Skills 架構的相容性
"""

import asyncio
import os
import httpx
import json
from typing import Optional

# 配置
API_KEY = os.getenv("OPENAI_API_KEY", "a7d54e9171b5d1095f9fb59e")
BASE_URL = "https://api.apmic-ai.com/v1"

# 停用 SSL 警告
import warnings
warnings.filterwarnings("ignore", message="Unverified HTTPS request")


async def test_create_prompt_for_boq():
    """建立 BOQ 解析用的 Prompt，模擬 Skills 內容"""
    print("\n" + "=" * 60)
    print("Step 1: 建立 BOQ 解析 Prompt (模擬 Skills)")
    print("=" * 60)

    url = f"{BASE_URL}/prompts"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    # 從 Skills 架構轉換的 Prompt 內容
    # 原本在 skills/vendors/habitus.yaml 的 system_prompt
    payload = {
        "name": "fairmont-boq-parser-v1",
        "value": """你是一個專業的家具報價單解析助手。

## 任務
從 PDF 內容中提取所有家具項目，輸出 JSON 陣列。

## 輸出格式
每個項目必須包含以下欄位：
- item_no: 項目編號
- description: 品名描述
- dimension: 尺寸 (W x D x H mm)
- qty: 數量
- uom: 單位
- materials_specs: 材料規格
- brand: 品牌
- location: 位置
- note: 備註

## 規則
1. 只輸出有效的 JSON 陣列
2. 不要包含任何額外說明文字
3. 數量必須是數字類型
4. 空值使用 null""",
        "metadata": {
            "vendor": "habitus",
            "version": "1.0",
            "source": "skills/vendors/habitus.yaml",
            "type": "boq_parser"
        }
    }

    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        print(f"請求 URL: {url}")
        try:
            response = await client.post(url, headers=headers, json=payload)
            print(f"HTTP 狀態碼: {response.status_code}")

            if response.status_code in [200, 201]:
                data = response.json()
                print(f"✅ Prompt 建立成功!")
                print(f"Prompt ID: {data.get('id', 'N/A')}")
                print(f"Name: {data.get('name', 'N/A')}")
                return data
            elif response.status_code == 422:
                print(f"⚠️ 參數驗證失敗")
                print(f"回應: {response.text[:500]}")
            else:
                print(f"回應: {response.text[:500]}")
        except Exception as e:
            print(f"❌ 錯誤: {e}")

    return None


async def test_chat_with_prompt_id(prompt_id: str):
    """使用 prompt_id 呼叫 Chat Completions"""
    print("\n" + "=" * 60)
    print("Step 2: 使用 prompt_id 呼叫 Chat Completions")
    print("=" * 60)

    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    # 測試資料：模擬 PDF 提取的文字
    test_pdf_content = """
    HABITUS FURNITURE SPECIFICATION

    Item: DLX-001
    Description: Deluxe King Bed
    Dimension: W2000 x D2100 x H1200 mm
    Quantity: 5 SET
    Material: Solid Oak Wood with Fabric Headboard
    Brand: Habitus Premium
    Location: Master Bedroom

    Item: DLX-002
    Description: Bedside Table
    Dimension: W500 x D450 x H600 mm
    Quantity: 10 PCS
    Material: Solid Oak Wood
    Brand: Habitus Premium
    Location: Master Bedroom
    """

    payload = {
        "model": "gemma-3-12b",
        "prompt_id": prompt_id,  # 使用雲端存儲的 Prompt
        "messages": [
            {
                "role": "user",
                "content": f"請解析以下 PDF 內容：\n\n{test_pdf_content}"
            }
        ],
        "temperature": 0.1,
        "max_tokens": 2000,
    }

    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        print(f"請求 URL: {url}")
        print(f"使用 prompt_id: {prompt_id}")
        try:
            response = await client.post(url, headers=headers, json=payload)
            print(f"HTTP 狀態碼: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                print(f"\n✅ 回應成功!")
                print(f"回應內容:\n{content[:1000]}")

                # 嘗試解析 JSON
                try:
                    json_start = content.find("[")
                    json_end = content.rfind("]") + 1
                    if json_start >= 0 and json_end > json_start:
                        parsed = json.loads(content[json_start:json_end])
                        print(f"\n✅ JSON 解析成功! 共 {len(parsed)} 個項目")
                        return True
                except json.JSONDecodeError:
                    print(f"\n⚠️ JSON 解析失敗")
            else:
                print(f"回應: {response.text[:500]}")
        except Exception as e:
            print(f"❌ 錯誤: {e}")

    return False


async def test_chat_without_prompt_id():
    """不使用 prompt_id，直接在 messages 中包含 system prompt"""
    print("\n" + "=" * 60)
    print("對照組: 不使用 prompt_id (傳統方式)")
    print("=" * 60)

    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    test_pdf_content = """
    Item: DLX-001
    Description: Deluxe King Bed
    Dimension: W2000 x D2100 x H1200 mm
    Quantity: 5 SET
    """

    payload = {
        "model": "gemma-3-12b",
        "messages": [
            {
                "role": "system",
                "content": "你是 BOQ 解析助手。輸出 JSON 陣列格式。"
            },
            {
                "role": "user",
                "content": f"解析：\n{test_pdf_content}"
            }
        ],
        "temperature": 0.1,
    }

    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        print(f"請求 URL: {url}")
        try:
            response = await client.post(url, headers=headers, json=payload)
            print(f"HTTP 狀態碼: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                print(f"✅ 回應成功!")
                print(f"回應內容:\n{content[:500]}")
                return True
            else:
                print(f"回應: {response.text[:300]}")
        except Exception as e:
            print(f"❌ 錯誤: {e}")

    return False


async def test_optimize_prompt(prompt_id: str):
    """測試 Prompt 自動優化"""
    print("\n" + "=" * 60)
    print("Step 3: 自動優化 Prompt")
    print("=" * 60)

    url = f"{BASE_URL}/prompts/{prompt_id}/optimize/auto"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120.0, verify=False) as client:
        print(f"請求 URL: {url}")
        print("正在優化 Prompt（可能需要較長時間）...")
        try:
            response = await client.post(url, headers=headers, json={})
            print(f"HTTP 狀態碼: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"✅ 優化成功!")
                print(f"優化結果: {json.dumps(data, indent=2, ensure_ascii=False)[:800]}")
                return data
            else:
                print(f"回應: {response.text[:300]}")
        except Exception as e:
            print(f"❌ 錯誤: {e}")

    return None


async def cleanup_prompt(prompt_id: str):
    """清理測試 Prompt"""
    print("\n" + "=" * 60)
    print("清理: 刪除測試 Prompt")
    print("=" * 60)

    url = f"{BASE_URL}/prompts/{prompt_id}"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        try:
            response = await client.delete(url, headers=headers)
            if response.status_code in [200, 204]:
                print(f"✅ 已刪除 Prompt: {prompt_id}")
                return True
            else:
                print(f"刪除失敗: {response.status_code}")
        except Exception as e:
            print(f"❌ 錯誤: {e}")

    return False


def analyze_skills_compatibility():
    """分析與 Skills 架構的相容性"""
    print("\n" + "=" * 60)
    print("Skills 架構相容性分析")
    print("=" * 60)

    analysis = """
┌─────────────────────────────────────────────────────────────┐
│                    整合架構分析                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  目前 Skills 架構:                                          │
│  ┌─────────────────┐                                        │
│  │ skills/         │                                        │
│  │ ├── vendors/    │ ──→ system_prompt, rules              │
│  │ ├── output-formats/ ──→ Excel 格式定義                  │
│  │ └── core/       │ ──→ merge rules                       │
│  └─────────────────┘                                        │
│           ↓                                                 │
│  ┌─────────────────┐                                        │
│  │ SkillLoader     │ ──→ 載入 YAML → 注入到服務            │
│  └─────────────────┘                                        │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  APMIC Prompts API 整合方案:                                │
│                                                             │
│  方案 A: 混合模式（建議）                                    │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │ Skills YAML     │ ←→ │ APMIC Prompts   │                │
│  │ (本地/離線)     │    │ (雲端/優化)     │                │
│  └─────────────────┘    └─────────────────┘                │
│           ↓ 開發時            ↓ 生產時                     │
│  ┌─────────────────────────────────────────┐               │
│  │           SkillLoader (擴展)            │               │
│  │  - load_from_yaml() (現有)              │               │
│  │  - sync_to_apmic() (新增)               │               │
│  │  - load_from_apmic() (新增)             │               │
│  └─────────────────────────────────────────┘               │
│                                                             │
│  方案 B: prompt_id 直接引用                                 │
│  ┌─────────────────┐                                        │
│  │ Chat Completions │                                       │
│  │ + prompt_id      │ ──→ 直接使用 APMIC Prompt            │
│  │ + fileset_id     │ ──→ 直接引用上傳文件                  │
│  └─────────────────┘                                        │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  相容性評估:                                                │
│  ✅ system_prompt     → 可完全遷移到 APMIC Prompts          │
│  ✅ prompt templates  → 可使用 prompt_id 引用               │
│  ⚠️ vendor rules      → 需保留在 YAML (非 prompt 內容)      │
│  ⚠️ output-formats    → 與 LLM 無關，保留 YAML              │
│  ⚠️ merge-rules       → 與 LLM 無關，保留 YAML              │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  建議實作步驟:                                              │
│  1. 保持 Skills YAML 為主要配置來源                         │
│  2. 新增 sync 功能將 prompt 同步到 APMIC                    │
│  3. 使用 APMIC 的自動優化改進 prompt                        │
│  4. 優化後的 prompt 可回寫到 YAML 或保留在 APMIC            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
"""
    print(analysis)


async def main():
    """執行整合測試"""
    print("=" * 60)
    print("APMIC PrivAI 整合式 API 測試")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"API Key: {'已設定' if API_KEY else '未設定'}")

    # 分析相容性
    analyze_skills_compatibility()

    # 測試對照組（傳統方式）
    await test_chat_without_prompt_id()

    # 測試 prompt_id 整合方式
    created_prompt = await test_create_prompt_for_boq()

    if created_prompt and "id" in created_prompt:
        prompt_id = created_prompt["id"]

        # 使用 prompt_id 呼叫
        await test_chat_with_prompt_id(prompt_id)

        # 測試優化（可選，較耗時）
        # await test_optimize_prompt(prompt_id)

        # 清理
        await cleanup_prompt(prompt_id)

    print("\n" + "=" * 60)
    print("測試完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
