#!/usr/bin/env python3
"""
APMIC PrivAI Fileset 完整工作流程測試

工作流程:
1. 建立 Fileset
2. 上傳檔案
3. 將檔案加入 Fileset
4. Commit Fileset
5. 使用 fileset_id 呼叫 Chat Completions
"""

import asyncio
import os
import httpx
import json
from pathlib import Path
from datetime import datetime

# 配置
API_KEY = os.getenv("OPENAI_API_KEY", "a7d54e9171b5d1095f9fb59e")
BASE_URL = "https://api.apmic-ai.com/v1"

# 停用 SSL 警告
import warnings
warnings.filterwarnings("ignore", message="Unverified HTTPS request")


async def create_fileset(name: str = None):
    """Step 1: 建立 Fileset"""
    print("\n" + "=" * 60)
    print("Step 1: 建立 Fileset")
    print("=" * 60)

    if name is None:
        name = f"fairmont_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    url = f"{BASE_URL}/filesets"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    # 嘗試不同的 payload 格式
    payloads = [
        {"name": name},
        {"name": name, "metadata": {"source": "fairmont_boq_test"}},
    ]

    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        for payload in payloads:
            print(f"嘗試 payload: {payload}")
            try:
                response = await client.post(url, headers=headers, json=payload)
                print(f"HTTP 狀態碼: {response.status_code}")

                if response.status_code in [200, 201]:
                    data = response.json()
                    print(f"✅ Fileset 建立成功!")
                    print(f"Fileset ID: {data.get('id')}")
                    print(f"State: {data.get('state')}")
                    return data
                else:
                    print(f"回應: {response.text[:300]}")
            except Exception as e:
                print(f"❌ 錯誤: {e}")

    return None


async def upload_file_to_fileset(fileset_id: str, content: str, filename: str):
    """Step 2: 上傳檔案到 Fileset"""
    print("\n" + "=" * 60)
    print("Step 2: 上傳檔案到 Fileset")
    print("=" * 60)

    # 嘗試不同的上傳端點
    endpoints = [
        f"{BASE_URL}/filesets/{fileset_id}/files",
        f"{BASE_URL}/files",
    ]

    headers = {"Authorization": f"Bearer {API_KEY}"}

    # 建立臨時檔案
    temp_file = Path(filename)
    temp_file.write_text(content, encoding="utf-8")

    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        for url in endpoints:
            print(f"\n嘗試上傳到: {url}")
            try:
                with open(filename, "rb") as f:
                    files = {"file": (filename, f, "text/plain")}
                    data = {"fileset_id": fileset_id} if "files" not in url else {}

                    response = await client.post(url, headers=headers, files=files, data=data)
                    print(f"HTTP 狀態碼: {response.status_code}")

                    if response.status_code in [200, 201]:
                        result = response.json()
                        print(f"✅ 檔案上傳成功!")
                        print(f"File ID: {result.get('id')}")
                        print(f"State: {result.get('state')}")
                        temp_file.unlink()  # 清理
                        return result
                    else:
                        print(f"回應: {response.text[:300]}")
            except Exception as e:
                print(f"❌ 錯誤: {e}")

    if temp_file.exists():
        temp_file.unlink()

    return None


async def add_file_to_fileset(fileset_id: str, file_id: str):
    """Step 3: 將檔案加入 Fileset (如果上傳沒有自動加入)"""
    print("\n" + "=" * 60)
    print("Step 3: 將檔案加入 Fileset")
    print("=" * 60)

    url = f"{BASE_URL}/filesets/{fileset_id}/files"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payloads = [
        {"file_id": file_id},
        {"file_ids": [file_id]},
        [file_id],
    ]

    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        for payload in payloads:
            print(f"嘗試 payload: {payload}")
            try:
                response = await client.post(url, headers=headers, json=payload)
                print(f"HTTP 狀態碼: {response.status_code}")

                if response.status_code in [200, 201]:
                    data = response.json()
                    print(f"✅ 檔案加入成功!")
                    return data
                elif response.status_code == 409:
                    print(f"⚠️ 檔案已存在於 Fileset")
                    return True
                else:
                    print(f"回應: {response.text[:200]}")
            except Exception as e:
                print(f"❌ 錯誤: {e}")

    return None


async def commit_fileset(fileset_id: str):
    """Step 4: Commit Fileset"""
    print("\n" + "=" * 60)
    print("Step 4: Commit Fileset")
    print("=" * 60)

    # 嘗試不同的 commit 端點
    endpoints = [
        (f"{BASE_URL}/filesets/{fileset_id}/commit", "POST"),
        (f"{BASE_URL}/filesets/{fileset_id}", "PATCH"),
    ]

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        for url, method in endpoints:
            print(f"\n嘗試: {method} {url}")
            try:
                if method == "POST":
                    response = await client.post(url, headers=headers, json={})
                else:
                    response = await client.patch(url, headers=headers, json={"state": "committed"})

                print(f"HTTP 狀態碼: {response.status_code}")

                if response.status_code in [200, 201, 204]:
                    if response.text:
                        data = response.json()
                        print(f"✅ Fileset Commit 成功!")
                        print(f"State: {data.get('state', 'N/A')}")
                        return data
                    else:
                        print(f"✅ Fileset Commit 成功! (無回應內容)")
                        return True
                else:
                    print(f"回應: {response.text[:200]}")
            except Exception as e:
                print(f"❌ 錯誤: {e}")

    return None


async def get_fileset_status(fileset_id: str):
    """檢查 Fileset 狀態"""
    print("\n" + "-" * 40)
    print(f"檢查 Fileset 狀態: {fileset_id}")
    print("-" * 40)

    url = f"{BASE_URL}/filesets/{fileset_id}"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        try:
            response = await client.get(url, headers=headers)
            print(f"HTTP 狀態碼: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"State: {data.get('state')}")
                print(f"Committed at: {data.get('committed_at', 'N/A')}")
                return data
            else:
                print(f"回應: {response.text[:200]}")
        except Exception as e:
            print(f"❌ 錯誤: {e}")

    return None


async def test_chat_with_fileset(fileset_id: str):
    """Step 5: 使用 fileset_id 呼叫 Chat Completions"""
    print("\n" + "=" * 60)
    print("Step 5: 使用 fileset_id 呼叫 Chat Completions")
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
                "content": "你是 BOQ 解析助手。從 Fileset 中的文件提取家具項目，輸出 JSON 陣列。"
            },
            {
                "role": "user",
                "content": "請解析文件內容，提取所有家具項目，輸出 JSON 格式。"
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
                usage = data.get("usage", {})
                print(f"\n✅ 回應成功!")
                print(f"Token 使用: {usage}")
                print(f"回應內容:\n{content[:1500]}")
                return content
            else:
                print(f"回應: {response.text[:500]}")
        except Exception as e:
            print(f"❌ 錯誤: {e}")

    return None


async def use_existing_fileset():
    """使用現有的 Fileset 測試"""
    print("\n" + "=" * 60)
    print("嘗試使用現有的 Fileset")
    print("=" * 60)

    url = f"{BASE_URL}/filesets"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                filesets = data.get("data", data) if isinstance(data, dict) else data

                # 找到狀態為 completed 的 fileset
                for fs in filesets:
                    if fs.get("state") == "completed":
                        print(f"找到已完成的 Fileset:")
                        print(f"  ID: {fs.get('id')}")
                        print(f"  Name: {fs.get('name')}")
                        print(f"  Created: {fs.get('created_at')}")
                        return fs.get("id")

                print("沒有找到已完成的 Fileset")
        except Exception as e:
            print(f"❌ 錯誤: {e}")

    return None


async def main():
    """執行完整工作流程測試"""
    print("=" * 60)
    print("APMIC PrivAI Fileset 完整工作流程測試")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"API Key: {'已設定' if API_KEY else '未設定'}")

    # 測試用的 BOQ 內容
    test_boq_content = """
HABITUS FURNITURE SPECIFICATION
Project: Fairmont Hotel Renovation
Date: 2025-12-31

=== FURNITURE ITEMS ===

Item No: FRM-001
Description: Executive Desk
Dimension: W1800 x D900 x H750 mm
Quantity: 25
UOM: SET
Material: Solid Walnut Wood with Leather Top
Brand: Habitus Executive
Location: Executive Suites

Item No: FRM-002
Description: Ergonomic Office Chair
Dimension: W650 x D650 x H1100-1250 mm
Quantity: 50
UOM: PCS
Material: Mesh Back with Leather Seat
Brand: Habitus Comfort
Location: All Offices

Item No: FRM-003
Description: Meeting Room Table
Dimension: W3000 x D1500 x H750 mm
Quantity: 8
UOM: SET
Material: Tempered Glass Top with Steel Frame
Brand: Habitus Modern
Location: Conference Rooms

=== FABRIC ITEMS ===

Item No: FAB-001
Description: Curtain Fabric
Specification: Pattern: Elegance, Color: Navy Blue, Width: 280cm
Material: 100% Polyester Blackout
Brand: TextilePro
Location: All Guest Rooms
Note: Fire retardant certified
"""

    # 方案 1: 使用現有的 Fileset
    existing_id = await use_existing_fileset()
    if existing_id:
        print(f"\n使用現有 Fileset: {existing_id}")
        await test_chat_with_fileset(existing_id)

    # 方案 2: 建立新的 Fileset 工作流程
    print("\n" + "=" * 60)
    print("建立新的 Fileset 工作流程")
    print("=" * 60)

    # Step 1: 建立 Fileset
    fileset = await create_fileset()

    if fileset and "id" in fileset:
        fileset_id = fileset["id"]

        # Step 2: 上傳檔案
        file_result = await upload_file_to_fileset(
            fileset_id,
            test_boq_content,
            "test_boq_spec.txt"
        )

        if file_result:
            file_id = file_result.get("id")

            # Step 3: 如果需要，將檔案加入 Fileset
            if file_id and fileset.get("state") == "draft":
                await add_file_to_fileset(fileset_id, file_id)

            # Step 4: Commit Fileset
            await commit_fileset(fileset_id)

            # 等待處理
            print("\n等待 Fileset 處理...")
            await asyncio.sleep(3)

            # 檢查狀態
            await get_fileset_status(fileset_id)

            # Step 5: 使用 fileset_id 呼叫 Chat
            await test_chat_with_fileset(fileset_id)

    print("\n" + "=" * 60)
    print("測試完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
