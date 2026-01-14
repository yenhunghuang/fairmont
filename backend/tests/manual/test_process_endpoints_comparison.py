"""手動測試：比較 /process 和 /process/stream 端點的輸出一致性."""

import asyncio
import json
import httpx
import os
from pathlib import Path

# 配置
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")
TEST_PDF = Path(__file__).parent.parent.parent / "temp_files" / "Casegoods & Seatings-1-2-18-34.pdf"


async def test_process_endpoint(pdf_path: Path) -> dict:
    """測試同步 /process 端點."""
    async with httpx.AsyncClient(timeout=600) as client:
        with open(pdf_path, "rb") as f:
            files = {"files": (pdf_path.name, f.read(), "application/pdf")}
            response = await client.post(
                f"{BASE_URL}/api/v1/process",
                files=files,
                params={"extract_images": False},
                headers={"Authorization": f"Bearer {API_KEY}"},
            )
            response.raise_for_status()
            return response.json()


async def test_stream_endpoint(pdf_path: Path) -> dict:
    """測試串流 /process/stream 端點."""
    async with httpx.AsyncClient(timeout=600) as client:
        with open(pdf_path, "rb") as f:
            files = {"files": (pdf_path.name, f.read(), "application/pdf")}

            async with client.stream(
                "POST",
                f"{BASE_URL}/api/v1/process/stream",
                files=files,
                params={"extract_images": False},
                headers={"Authorization": f"Bearer {API_KEY}"},
            ) as response:
                response.raise_for_status()

                result = None
                async for line in response.aiter_lines():
                    if line.startswith("event: result"):
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        result = json.loads(data_str)
                        break

                return result


def compare_results(sync_result: dict, stream_result: dict) -> None:
    """比較兩個端點的輸出."""
    print("\n" + "=" * 60)
    print("比較結果")
    print("=" * 60)

    # 比較 project_name
    sync_project = sync_result.get("project_name")
    stream_project = stream_result.get("project_name")
    print(f"\nproject_name:")
    print(f"  同步版本: {sync_project}")
    print(f"  串流版本: {stream_project}")
    print(f"  一致: {'✓' if sync_project == stream_project else '✗'}")

    # 比較 items 數量
    sync_items = sync_result.get("items", [])
    stream_items = stream_result.get("items", [])
    print(f"\nitems 數量:")
    print(f"  同步版本: {len(sync_items)}")
    print(f"  串流版本: {len(stream_items)}")
    print(f"  一致: {'✓' if len(sync_items) == len(stream_items) else '✗'}")

    # 比較 item_no 列表
    sync_item_nos = [item.get("item_no") for item in sync_items]
    stream_item_nos = [item.get("item_no") for item in stream_items]

    print(f"\n同步版本 item_no:")
    for no in sync_item_nos:
        print(f"  - {no}")

    print(f"\n串流版本 item_no:")
    for no in stream_item_nos:
        print(f"  - {no}")

    # 找出差異
    sync_set = set(sync_item_nos)
    stream_set = set(stream_item_nos)

    missing_in_stream = sync_set - stream_set
    extra_in_stream = stream_set - sync_set

    if missing_in_stream:
        print(f"\n❌ 串流版本遺失的 item_no:")
        for no in sorted(missing_in_stream):
            print(f"  - {no}")

    if extra_in_stream:
        print(f"\n❌ 串流版本多出的 item_no:")
        for no in sorted(extra_in_stream):
            print(f"  - {no}")

    if not missing_in_stream and not extra_in_stream:
        print(f"\n✓ 兩個端點的 item_no 完全一致！")

    # 詳細比較每個 item
    if len(sync_items) == len(stream_items):
        print("\n詳細比較每個 item...")
        for i, (sync_item, stream_item) in enumerate(zip(sync_items, stream_items)):
            if sync_item != stream_item:
                print(f"\n  Item {i+1} 不一致:")
                for key in set(sync_item.keys()) | set(stream_item.keys()):
                    if sync_item.get(key) != stream_item.get(key):
                        print(f"    {key}: {sync_item.get(key)} vs {stream_item.get(key)}")


async def main():
    """主函數."""
    if not TEST_PDF.exists():
        print(f"測試檔案不存在: {TEST_PDF}")
        return

    if not API_KEY:
        print("請設定 API_KEY 環境變數")
        return

    print(f"測試檔案: {TEST_PDF}")
    print(f"API URL: {BASE_URL}")

    print("\n" + "-" * 60)
    print("測試同步 /process 端點...")
    try:
        sync_result = await test_process_endpoint(TEST_PDF)
        print(f"同步版本返回 {len(sync_result.get('items', []))} 個項目")
    except Exception as e:
        print(f"同步版本失敗: {e}")
        return

    print("\n" + "-" * 60)
    print("測試串流 /process/stream 端點...")
    try:
        stream_result = await test_stream_endpoint(TEST_PDF)
        if stream_result:
            print(f"串流版本返回 {len(stream_result.get('items', []))} 個項目")
        else:
            print("串流版本未返回結果")
            return
    except Exception as e:
        print(f"串流版本失敗: {e}")
        return

    # 比較結果
    compare_results(sync_result, stream_result)


if __name__ == "__main__":
    asyncio.run(main())
