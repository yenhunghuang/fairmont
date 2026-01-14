#!/usr/bin/env python3
"""
APMIC PrivAI QA & Prompts API 測試腳本

測試新發現的 API 端點:
- /v1/qa/generate - 從文件產生 Q&A 對
- /v1/prompts/* - Prompt 管理 API
"""

import asyncio
import os
import httpx
import json

# 配置
API_KEY = os.getenv("OPENAI_API_KEY", "a7d54e9171b5d1095f9fb59e")
BASE_URL = "https://api.apmic-ai.com/v1"

# 停用 SSL 警告
import warnings
warnings.filterwarnings("ignore", message="Unverified HTTPS request")


async def test_qa_generate(fileset_id: str = None):
    """測試 /v1/qa/generate - 從文件產生 Q&A

    發現: fileset_id 是 query parameter，不是 body
    """
    print("\n" + "=" * 60)
    print("測試: QA Generate (/v1/qa/generate)")
    print("=" * 60)

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        # fileset_id 作為 query parameter
        if fileset_id:
            url = f"{BASE_URL}/qa/generate?fileset_id={fileset_id}"
            print(f"請求 URL: {url}")
            try:
                response = await client.post(url, headers=headers, json={})
                print(f"HTTP 狀態碼: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ 成功!")
                    print(f"回應: {json.dumps(data, indent=2, ensure_ascii=False)[:800]}")
                    return data
                else:
                    print(f"回應: {response.text[:300]}")
            except Exception as e:
                print(f"❌ 錯誤: {e}")
        else:
            print("⚠️ 需要 fileset_id 才能測試 QA Generate")
            print("此 API 從已上傳的 Fileset 文件中產生 Q&A 對")

    return None


async def test_prompts_list():
    """測試 /v1/prompts - 列出所有 Prompts"""
    print("\n" + "=" * 60)
    print("測試: List Prompts (/v1/prompts)")
    print("=" * 60)

    url = f"{BASE_URL}/prompts"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        print(f"請求 URL: {url}")
        try:
            response = await client.get(url, headers=headers)
            print(f"HTTP 狀態碼: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"✅ 成功!")
                print(f"Prompts 數量: {len(data) if isinstance(data, list) else 'N/A'}")
                print(f"回應: {json.dumps(data, indent=2, ensure_ascii=False)[:800]}")
                return data
            else:
                print(f"回應: {response.text[:300]}")
        except Exception as e:
            print(f"❌ 錯誤: {e}")

    return None


async def test_prompts_create():
    """測試 /v1/prompts - 建立 Prompt"""
    print("\n" + "=" * 60)
    print("測試: Create Prompt (/v1/prompts)")
    print("=" * 60)

    url = f"{BASE_URL}/prompts"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    # 嘗試建立一個測試 Prompt
    payloads_to_try = [
        # 格式 1: 基本
        {
            "name": "fairmont-boq-parser-test",
            "content": "你是一個專業的家具報價單解析助手。請從以下 PDF 內容中提取所有家具項目。",
        },
        # 格式 2: 帶 template
        {
            "name": "fairmont-boq-parser-test",
            "template": "你是一個專業的家具報價單解析助手。\n\n{pdf_content}",
            "variables": ["pdf_content"],
        },
        # 格式 3: 帶 description
        {
            "name": "fairmont-boq-parser-test",
            "description": "Fairmont BOQ 解析 Prompt",
            "prompt": "你是一個專業的家具報價單解析助手。",
        },
    ]

    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        print(f"請求 URL: {url}")

        for i, payload in enumerate(payloads_to_try, 1):
            print(f"\n--- 嘗試格式 {i}: {list(payload.keys())} ---")
            try:
                response = await client.post(url, headers=headers, json=payload)
                print(f"HTTP 狀態碼: {response.status_code}")

                if response.status_code in [200, 201]:
                    data = response.json()
                    print(f"✅ 成功!")
                    print(f"回應: {json.dumps(data, indent=2, ensure_ascii=False)}")
                    return data
                elif response.status_code == 422:
                    print(f"⚠️ 參數驗證失敗: {response.text[:300]}")
                else:
                    print(f"回應: {response.text[:300]}")
            except Exception as e:
                print(f"❌ 錯誤: {e}")

    return None


async def test_prompts_optimize(prompt_id: str):
    """測試 /v1/prompts/{id}/optimize/auto - 自動優化 Prompt"""
    print("\n" + "=" * 60)
    print(f"測試: Auto Optimize Prompt (/v1/prompts/{prompt_id}/optimize/auto)")
    print("=" * 60)

    url = f"{BASE_URL}/prompts/{prompt_id}/optimize/auto"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        print(f"請求 URL: {url}")
        try:
            response = await client.post(url, headers=headers, json={})
            print(f"HTTP 狀態碼: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"✅ 成功!")
                print(f"優化後的 Prompt: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
                return data
            else:
                print(f"回應: {response.text[:300]}")
        except Exception as e:
            print(f"❌ 錯誤: {e}")

    return None


async def test_prompts_delete(prompt_id: str):
    """測試 /v1/prompts/{id} - 刪除 Prompt"""
    print("\n" + "=" * 60)
    print(f"測試: Delete Prompt (/v1/prompts/{prompt_id})")
    print("=" * 60)

    url = f"{BASE_URL}/prompts/{prompt_id}"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        print(f"請求 URL: {url}")
        try:
            response = await client.delete(url, headers=headers)
            print(f"HTTP 狀態碼: {response.status_code}")

            if response.status_code in [200, 204]:
                print(f"✅ 刪除成功!")
                return True
            else:
                print(f"回應: {response.text[:200]}")
        except Exception as e:
            print(f"❌ 錯誤: {e}")

    return False


async def main():
    """執行所有測試"""
    print("=" * 60)
    print("APMIC PrivAI QA & Prompts API 測試")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"API Key: {'已設定' if API_KEY else '未設定'}")

    # 測試 QA Generate
    await test_qa_generate()

    # 測試 Prompts API
    prompts = await test_prompts_list()

    # 嘗試建立 Prompt
    created_prompt = await test_prompts_create()

    # 如果建立成功，測試優化和刪除
    if created_prompt and "id" in created_prompt:
        prompt_id = created_prompt["id"]
        await test_prompts_optimize(prompt_id)
        await test_prompts_delete(prompt_id)

    print("\n" + "=" * 60)
    print("測試完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
