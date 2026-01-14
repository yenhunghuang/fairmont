#!/usr/bin/env python3
"""
APMIC PrivAI API 測試腳本

用法:
    設定環境變數後執行：
    OPENAI_API_KEY=your-token python test_apmic_api.py

或直接修改下方的 API_KEY 變數。
"""

import asyncio
import os
import ssl
import httpx
from typing import Optional

# 停用 SSL 警告（開發環境）
import warnings
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# ============ 配置區 ============
API_KEY = os.getenv("OPENAI_API_KEY", "")  # 從環境變數讀取或在此填入
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.apmic-ai.com/v1")
MODEL = os.getenv("OPENAI_MODEL", "gemma-3-12b")

# 可用模型 (2025-12-31 驗證):
# - gemma-3-12b: 快速模型，一般 Q&A
# - ace-1-24b-reasoning-v1: 深度推理模型
# - apmic-embedding-v1: Embedding 模型 (2048維)
# ================================


def check_config():
    """檢查 API 配置"""
    if not API_KEY:
        print("=" * 60)
        print("錯誤: 未設定 APMIC API Key")
        print()
        print("請使用以下方式之一設定 API Key:")
        print("1. 設定環境變數: export OPENAI_API_KEY=your-token")
        print("2. 直接修改此檔案中的 API_KEY 變數")
        print("=" * 60)
        return False
    return True


async def test_chat_completion():
    """測試 /v1/chat/completions 端點 (OpenAI Compatible)"""
    print("\n" + "=" * 60)
    print("測試 1: Chat Completions (/v1/chat/completions)")
    print("=" * 60)

    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "你是一個有幫助的助手。請用繁體中文回答。"},
            {"role": "user", "content": "請用一句話介紹你自己"},
        ],
        "max_tokens": 256,
        "temperature": 0.7,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
            print(f"請求 URL: {url}")
            print(f"使用模型: {MODEL}")
            response = await client.post(url, headers=headers, json=payload)

            print(f"HTTP 狀態碼: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})

                print("\n✅ 測試成功!")
                print(f"回應內容: {content}")
                print(f"Token 使用: prompt={usage.get('prompt_tokens', 'N/A')}, "
                      f"completion={usage.get('completion_tokens', 'N/A')}, "
                      f"total={usage.get('total_tokens', 'N/A')}")
                return True
            else:
                print(f"\n❌ 測試失敗!")
                print(f"錯誤回應: {response.text}")
                return False
    except httpx.TimeoutException:
        print("\n❌ 請求超時 (60 秒)")
        return False
    except Exception as e:
        print(f"\n❌ 請求錯誤: {e}")
        return False


async def test_models_endpoint():
    """測試 /v1/models 端點"""
    print("\n" + "=" * 60)
    print("測試 2: Models 端點 (/v1/models)")
    print("=" * 60)

    url = f"{BASE_URL}/models"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    try:
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            print(f"請求 URL: {url}")
            response = await client.get(url, headers=headers)

            print(f"HTTP 狀態碼: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print("\n✅ 端點可用!")
                print(f"可用模型: {data}")
                return True
            elif response.status_code == 404:
                print("\n⚠️ 端點未實作 (預期行為)")
                print("文件說明此端點 NOT IMPL，需硬編碼模型名稱")
                return True  # 預期結果
            else:
                print(f"\n❌ 未預期的回應: {response.text}")
                return False
    except Exception as e:
        print(f"\n❌ 請求錯誤: {e}")
        return False


async def test_embedding_native():
    """測試 /api/llm/ot/embedding 端點 (Native API)"""
    print("\n" + "=" * 60)
    print("測試 3: Embedding 端點 (/api/llm/ot/embedding)")
    print("=" * 60)

    # Native API 使用不同的 base URL
    native_base = BASE_URL.replace("/v1", "")
    url = f"{native_base}/api/llm/ot/embedding"
    params = {"embedding_name": "apmic-embedding-v1", "env": "dev"}
    headers = {
        "auth": API_KEY,  # Native API 使用小寫 auth header
        "Content-Type": "application/json",
    }
    payload = {"text": "測試文字"}

    try:
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            print(f"請求 URL: {url}")
            print(f"注意: Native API 使用 'auth' header (非 Authorization)")
            response = await client.post(url, headers=headers, params=params, json=payload)

            print(f"HTTP 狀態碼: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                embedding = data.get("embedding", [])
                print(f"\n✅ 測試成功!")
                print(f"Embedding 維度: {len(embedding)}")
                if embedding:
                    print(f"前 5 個值: {embedding[:5]}")
                return True
            else:
                print(f"\n❌ 測試失敗: {response.text}")
                return False
    except Exception as e:
        print(f"\n❌ 請求錯誤: {e}")
        return False


async def test_json_mode():
    """測試 JSON 格式輸出 (重要：BOQ 系統需要此功能)"""
    print("\n" + "=" * 60)
    print("測試 4: JSON 格式輸出測試")
    print("=" * 60)

    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    # 測試透過 prompt engineering 強制 JSON 輸出
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是一個 JSON 產生器。只輸出有效的 JSON 陣列，不要有任何其他文字。"
            },
            {
                "role": "user",
                "content": """請將以下資訊轉換為 JSON 陣列格式:
- 項目 A-001，數量 5，單位 SET
- 項目 B-002，數量 10，單位 PCS

輸出格式:
[{"item_no": "...", "qty": ..., "uom": "..."}]"""
            },
        ],
        "temperature": 0.1,  # 低溫度增加一致性
    }

    try:
        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
            print(f"請求 URL: {url}")
            response = await client.post(url, headers=headers, json=payload)

            print(f"HTTP 狀態碼: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]

                print(f"\n回應內容:\n{content}")

                # 嘗試解析 JSON
                import json
                try:
                    # 嘗試找出 JSON 陣列
                    json_start = content.find("[")
                    json_end = content.rfind("]") + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = content[json_start:json_end]
                        parsed = json.loads(json_str)
                        print(f"\n✅ JSON 解析成功!")
                        print(f"解析結果: {parsed}")
                        return True
                    else:
                        print(f"\n⚠️ 回應中未找到 JSON 陣列")
                        return False
                except json.JSONDecodeError as e:
                    print(f"\n⚠️ JSON 解析失敗: {e}")
                    return False
            else:
                print(f"\n❌ 測試失敗: {response.text}")
                return False
    except Exception as e:
        print(f"\n❌ 請求錯誤: {e}")
        return False


async def test_with_openai_sdk():
    """使用 OpenAI Python SDK 測試"""
    print("\n" + "=" * 60)
    print("測試 5: OpenAI Python SDK 整合測試")
    print("=" * 60)

    try:
        import httpx as httpx_lib
        from openai import OpenAI

        # 建立停用 SSL 驗證的 HTTP client
        http_client = httpx_lib.Client(verify=False)

        client = OpenAI(
            api_key=API_KEY,
            base_url=BASE_URL,
            http_client=http_client,
        )

        print(f"Base URL: {BASE_URL}")
        print(f"Model: {MODEL}")
        print("正在呼叫 API...")

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "user", "content": "Hello, say 'APMIC test successful' in Chinese"},
            ],
            max_tokens=100,
        )

        content = response.choices[0].message.content
        usage = response.usage

        print(f"\n✅ SDK 測試成功!")
        print(f"回應: {content}")
        print(f"Token 使用: prompt={usage.prompt_tokens}, "
              f"completion={usage.completion_tokens}, "
              f"total={usage.total_tokens}")
        return True

    except ImportError:
        print("\n⚠️ openai 套件未安裝")
        print("請執行: pip install openai")
        return False
    except Exception as e:
        print(f"\n❌ SDK 錯誤: {e}")
        return False


async def main():
    """執行所有測試"""
    print("=" * 60)
    print("APMIC PrivAI API 測試")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Model: {MODEL}")
    print(f"API Key: {'已設定' if API_KEY else '未設定'}")

    if not check_config():
        return

    results = {}

    # 執行測試
    results["chat_completion"] = await test_chat_completion()
    results["models"] = await test_models_endpoint()
    results["embedding"] = await test_embedding_native()
    results["json_mode"] = await test_json_mode()
    results["openai_sdk"] = await test_with_openai_sdk()

    # 總結
    print("\n" + "=" * 60)
    print("測試總結")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "✅ 通過" if passed else "❌ 失敗"
        print(f"  {test_name}: {status}")

    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    print(f"\n總計: {passed_count}/{total_count} 通過")

    if passed_count == total_count:
        print("\n🎉 所有測試通過! APMIC API 可正常使用")
    elif results["chat_completion"] and results["json_mode"]:
        print("\n✅ 核心功能測試通過，可用於 Fairmont BOQ 系統")
    else:
        print("\n⚠️ 部分測試失敗，請檢查 API 配置")


if __name__ == "__main__":
    asyncio.run(main())
