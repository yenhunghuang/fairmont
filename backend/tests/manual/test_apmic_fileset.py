#!/usr/bin/env python3
"""
APMIC PrivAI Fileset API 測試

測試檔案上傳與 Chat Completions 整合:
1. 探索 Fileset 相關 API 端點
2. 上傳 PDF 建立 Fileset
3. 使用 fileset_id 呼叫 Chat Completions
"""

import asyncio
import os
import httpx
import json
from pathlib import Path

# 配置
API_KEY = os.getenv("OPENAI_API_KEY", "a7d54e9171b5d1095f9fb59e")
BASE_URL = "https://api.apmic-ai.com/v1"
NATIVE_BASE_URL = "https://api.apmic-ai.com"

# 停用 SSL 警告
import warnings
warnings.filterwarnings("ignore", message="Unverified HTTPS request")


async def explore_fileset_endpoints():
    """探索可能的 Fileset 端點"""
    print("\n" + "=" * 60)
    print("Step 1: 探索 Fileset API 端點")
    print("=" * 60)

    headers = {"Authorization": f"Bearer {API_KEY}"}

    # 可能的端點清單
    endpoints_to_try = [
        # OpenAI Compatible style
        ("GET", f"{BASE_URL}/filesets", "列出 Filesets"),
        ("GET", f"{BASE_URL}/files", "列出 Files (OpenAI style)"),
        # Native API style
        ("GET", f"{NATIVE_BASE_URL}/api/llm/ot/filesets", "Native Filesets"),
        ("GET", f"{NATIVE_BASE_URL}/api/filesets", "Native Filesets v2"),
        ("GET", f"{NATIVE_BASE_URL}/api/v1/filesets", "Native Filesets v3"),
    ]

    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        for method, url, description in endpoints_to_try:
            print(f"\n嘗試: {description}")
            print(f"  {method} {url}")
            try:
                if method == "GET":
                    response = await client.get(url, headers=headers)
                else:
                    response = await client.post(url, headers=headers)

                print(f"  HTTP 狀態碼: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    print(f"  ✅ 端點存在!")
                    print(f"  回應: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
                    return url, data
                elif response.status_code == 404:
                    print(f"  ❌ 端點不存在")
                elif response.status_code == 405:
                    print(f"  ⚠️ 方法不允許，端點可能存在")
                else:
                    print(f"  回應: {response.text[:200]}")
            except Exception as e:
                print(f"  ❌ 錯誤: {e}")

    return None, None


async def try_upload_file(file_path: str = None):
    """嘗試上傳檔案"""
    print("\n" + "=" * 60)
    print("Step 2: 嘗試上傳檔案")
    print("=" * 60)

    # 如果沒有指定檔案，建立一個測試用的文字檔
    if file_path is None or not Path(file_path).exists():
        test_content = """
        HABITUS FURNITURE SPECIFICATION

        Item: TEST-001
        Description: Test Chair
        Dimension: W500 x D500 x H900 mm
        Quantity: 10 PCS
        Material: Fabric
        Brand: Habitus
        Location: Living Room
        """
        test_file = Path("test_upload.txt")
        test_file.write_text(test_content, encoding="utf-8")
        file_path = str(test_file)
        print(f"建立測試檔案: {file_path}")

    headers_auth = {"Authorization": f"Bearer {API_KEY}"}
    headers_native = {"auth": API_KEY}

    # 可能的上傳端點
    upload_endpoints = [
        # OpenAI Compatible style
        (f"{BASE_URL}/files", headers_auth, "purpose"),
        (f"{BASE_URL}/filesets", headers_auth, "purpose"),
        # Native API style
        (f"{NATIVE_BASE_URL}/api/llm/ot/filesets", headers_native, None),
        (f"{NATIVE_BASE_URL}/api/filesets/upload", headers_native, None),
    ]

    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        for url, headers, purpose_field in upload_endpoints:
            print(f"\n嘗試上傳到: {url}")
            try:
                with open(file_path, "rb") as f:
                    files = {"file": (Path(file_path).name, f, "text/plain")}
                    data = {}
                    if purpose_field:
                        data[purpose_field] = "assistants"

                    response = await client.post(
                        url,
                        headers=headers,
                        files=files,
                        data=data if data else None
                    )

                print(f"  HTTP 狀態碼: {response.status_code}")

                if response.status_code in [200, 201]:
                    result = response.json()
                    print(f"  ✅ 上傳成功!")
                    print(f"  回應: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}")
                    return result
                elif response.status_code == 404:
                    print(f"  ❌ 端點不存在")
                elif response.status_code == 422:
                    print(f"  ⚠️ 參數錯誤: {response.text[:300]}")
                else:
                    print(f"  回應: {response.text[:300]}")
            except Exception as e:
                print(f"  ❌ 錯誤: {e}")

    # 清理測試檔案
    if Path("test_upload.txt").exists():
        Path("test_upload.txt").unlink()

    return None


async def test_chat_with_fileset(fileset_id: str):
    """使用 fileset_id 呼叫 Chat Completions"""
    print("\n" + "=" * 60)
    print("Step 3: 使用 fileset_id 呼叫 Chat Completions")
    print("=" * 60)

    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "gemma-3-12b",
        "fileset_id": fileset_id,
        "messages": [
            {
                "role": "system",
                "content": "你是 BOQ 解析助手。從提供的文件中提取家具項目，輸出 JSON 陣列。"
            },
            {
                "role": "user",
                "content": "請解析 Fileset 中的文件內容，提取所有家具項目。"
            }
        ],
        "temperature": 0.1,
    }

    async with httpx.AsyncClient(timeout=120.0, verify=False) as client:
        print(f"請求 URL: {url}")
        print(f"使用 fileset_id: {fileset_id}")
        try:
            response = await client.post(url, headers=headers, json=payload)
            print(f"HTTP 狀態碼: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                print(f"\n✅ 回應成功!")
                print(f"回應內容:\n{content[:1000]}")
                return True
            else:
                print(f"回應: {response.text[:500]}")
        except Exception as e:
            print(f"❌ 錯誤: {e}")

    return False


async def check_existing_filesets():
    """檢查是否有現有的 Filesets"""
    print("\n" + "=" * 60)
    print("檢查現有 Filesets")
    print("=" * 60)

    # 嘗試 GET /v1/filesets
    url = f"{BASE_URL}/filesets"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        try:
            response = await client.get(url, headers=headers)
            print(f"GET {url}")
            print(f"HTTP 狀態碼: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"✅ 找到 Filesets!")
                if isinstance(data, list) and len(data) > 0:
                    print(f"Filesets 數量: {len(data)}")
                    for fs in data[:3]:  # 只顯示前 3 個
                        print(f"  - ID: {fs.get('id', 'N/A')}, Name: {fs.get('name', 'N/A')}")
                    return data
                elif isinstance(data, dict) and "data" in data:
                    filesets = data["data"]
                    print(f"Filesets 數量: {len(filesets)}")
                    for fs in filesets[:3]:
                        print(f"  - ID: {fs.get('id', 'N/A')}, Name: {fs.get('name', 'N/A')}")
                    return filesets
                else:
                    print(f"回應格式: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
                    return data
            else:
                print(f"回應: {response.text[:300]}")
        except Exception as e:
            print(f"❌ 錯誤: {e}")

    return None


async def main():
    """執行 Fileset 測試"""
    print("=" * 60)
    print("APMIC PrivAI Fileset API 測試")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"API Key: {'已設定' if API_KEY else '未設定'}")

    # 檢查現有 Filesets
    existing = await check_existing_filesets()

    # 探索端點
    found_url, data = await explore_fileset_endpoints()

    # 嘗試上傳
    upload_result = await try_upload_file()

    # 如果有現有的 fileset，嘗試使用它
    if existing and isinstance(existing, list) and len(existing) > 0:
        fileset_id = existing[0].get("id")
        if fileset_id:
            await test_chat_with_fileset(fileset_id)
    elif upload_result and "id" in upload_result:
        await test_chat_with_fileset(upload_result["id"])

    print("\n" + "=" * 60)
    print("測試完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
