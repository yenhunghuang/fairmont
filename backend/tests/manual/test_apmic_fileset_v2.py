#!/usr/bin/env python3
"""
APMIC PrivAI Fileset 正確工作流程測試

正確工作流程:
1. 上傳檔案到 /v1/files → 取得 file_id
2. 建立 Fileset，傳入 file_ids 陣列
3. (等待 Fileset 處理完成)
4. 使用 fileset_id 呼叫 Chat Completions
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


async def upload_file(content: str, filename: str) -> dict:
    """Step 1: 上傳檔案到 /v1/files"""
    print("\n" + "=" * 60)
    print("Step 1: 上傳檔案到 /v1/files")
    print("=" * 60)

    url = f"{BASE_URL}/files"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    # 建立臨時檔案
    temp_file = Path(filename)
    temp_file.write_text(content, encoding="utf-8")

    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        try:
            with open(filename, "rb") as f:
                files = {"file": (filename, f, "text/plain")}
                response = await client.post(url, headers=headers, files=files)

            print(f"HTTP 狀態碼: {response.status_code}")

            if response.status_code in [200, 201]:
                result = response.json()
                print(f"✅ 檔案上傳成功!")
                print(f"File ID: {result.get('id')}")
                print(f"Filename: {result.get('filename')}")
                print(f"State: {result.get('state')}")
                print(f"Size: {result.get('bytes')} bytes")
                temp_file.unlink()
                return result
            else:
                print(f"❌ 上傳失敗: {response.text[:300]}")
        except Exception as e:
            print(f"❌ 錯誤: {e}")
        finally:
            if temp_file.exists():
                temp_file.unlink()

    return None


async def create_fileset_with_files(file_ids: list, name: str = None) -> dict:
    """Step 2: 建立 Fileset（傳入 file_ids）"""
    print("\n" + "=" * 60)
    print("Step 2: 建立 Fileset")
    print("=" * 60)

    if name is None:
        name = f"fairmont_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    url = f"{BASE_URL}/filesets"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "name": name,
        "file_ids": file_ids,
    }

    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        print(f"Payload: {json.dumps(payload, indent=2)}")
        try:
            response = await client.post(url, headers=headers, json=payload)
            print(f"HTTP 狀態碼: {response.status_code}")

            if response.status_code in [200, 201]:
                result = response.json()
                print(f"✅ Fileset 建立成功!")
                print(f"Fileset ID: {result.get('id')}")
                print(f"Name: {result.get('name')}")
                print(f"State: {result.get('state')}")
                return result
            else:
                print(f"❌ 建立失敗: {response.text[:500]}")
        except Exception as e:
            print(f"❌ 錯誤: {e}")

    return None


async def wait_for_fileset_ready(fileset_id: str, max_wait: int = 60) -> bool:
    """等待 Fileset 處理完成"""
    print("\n" + "-" * 40)
    print(f"等待 Fileset 處理完成...")
    print("-" * 40)

    url = f"{BASE_URL}/filesets/{fileset_id}"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        for i in range(max_wait // 3):
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    state = data.get("state")
                    print(f"  [{i*3}s] State: {state}")

                    if state == "completed":
                        print(f"✅ Fileset 處理完成!")
                        return True
                    elif state == "failed":
                        print(f"❌ Fileset 處理失敗!")
                        print(f"  Reason: {data.get('metadata', {}).get('fail_reason')}")
                        return False
            except Exception as e:
                print(f"  錯誤: {e}")

            await asyncio.sleep(3)

    print(f"⚠️ 等待超時 ({max_wait}s)")
    return False


async def test_chat_with_fileset(fileset_id: str) -> str:
    """Step 3: 使用 fileset_id 呼叫 Chat Completions"""
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
                "content": """你是 BOQ 解析助手。從 Fileset 文件中提取所有家具項目。

輸出 JSON 陣列，每個項目包含：
- item_no: 項目編號
- description: 品名
- dimension: 尺寸
- qty: 數量
- uom: 單位
- materials_specs: 材料規格
- brand: 品牌
- location: 位置
- note: 備註（無則 null）

只輸出 JSON，不要其他文字。"""
            },
            {
                "role": "user",
                "content": "請解析 Fileset 中的文件，提取所有家具項目並輸出 JSON 陣列。"
            }
        ],
        "temperature": 0.1,
        "max_tokens": 4000,
    }

    async with httpx.AsyncClient(timeout=180.0, verify=False) as client:
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
                print(f"Token 使用: prompt={usage.get('prompt_tokens')}, "
                      f"completion={usage.get('completion_tokens')}, "
                      f"total={usage.get('total_tokens')}")
                print(f"\n回應內容:\n{content}")

                # 嘗試解析 JSON
                try:
                    json_start = content.find("[")
                    json_end = content.rfind("]") + 1
                    if json_start >= 0 and json_end > json_start:
                        parsed = json.loads(content[json_start:json_end])
                        print(f"\n✅ JSON 解析成功! 共 {len(parsed)} 個項目")
                except:
                    pass

                return content
            else:
                print(f"❌ 回應失敗: {response.text[:500]}")
        except Exception as e:
            print(f"❌ 錯誤: {e}")

    return None


async def main():
    """執行完整工作流程"""
    print("=" * 60)
    print("APMIC PrivAI Fileset 正確工作流程測試")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")

    # 測試用的 BOQ 內容 (模擬 PDF 提取的文字)
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
Note: Include cable management

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

    # Step 1: 上傳檔案
    file_result = await upload_file(test_boq_content, "fairmont_boq_spec.txt")

    if not file_result or "id" not in file_result:
        print("\n❌ 檔案上傳失敗，無法繼續")
        return

    file_id = file_result["id"]

    # Step 2: 建立 Fileset
    fileset_result = await create_fileset_with_files([file_id])

    if not fileset_result or "id" not in fileset_result:
        print("\n❌ Fileset 建立失敗，無法繼續")
        return

    fileset_id = fileset_result["id"]

    # 等待 Fileset 處理完成
    ready = await wait_for_fileset_ready(fileset_id)

    if not ready:
        print("\n⚠️ Fileset 未完成，仍嘗試呼叫 Chat...")

    # Step 3: 使用 fileset_id 呼叫 Chat Completions
    result = await test_chat_with_fileset(fileset_id)

    print("\n" + "=" * 60)
    print("測試完成")
    print("=" * 60)

    if result:
        print("\n📋 總結:")
        print(f"  - File ID: {file_id}")
        print(f"  - Fileset ID: {fileset_id}")
        print(f"  - 此 Fileset 可用於後續的 Chat Completions 呼叫")


if __name__ == "__main__":
    asyncio.run(main())
