"""In-memory store for documents, tasks, quotations, and images."""

import logging
from typing import Any, Dict, List, Optional

from .models import (
    SourceDocument,
    BOQItem,
    Quotation,
    ProcessingTask,
    ExtractedImage,
    MergeReport,
)
from .utils import ErrorCode, raise_error


logger = logging.getLogger(__name__)


class InMemoryStore:
    """In-memory storage for all application data."""

    def __init__(self, cache_ttl: int = 3600):
        self.cache_ttl = cache_ttl

        self.documents: Dict[str, SourceDocument] = {}
        self.boq_items: Dict[str, BOQItem] = {}
        self.quotations: Dict[str, Quotation] = {}
        self.processing_tasks: Dict[str, ProcessingTask] = {}
        self.extracted_images: Dict[str, ExtractedImage] = {}
        self.merge_reports: Dict[str, MergeReport] = {}

        logger.info(f"InMemoryStore initialized (ttl={cache_ttl}s)")

    # ===== Document Management =====

    def add_document(self, document: SourceDocument) -> None:
        self.documents[document.id] = document
        logger.info(f"Document added: {document.id}")

    def get_document(self, document_id: str) -> SourceDocument:
        if document_id not in self.documents:
            raise_error(ErrorCode.DOCUMENT_NOT_FOUND, "文件不存在", status_code=404)
        return self.documents[document_id]

    def list_documents(self) -> List[SourceDocument]:
        return list(self.documents.values())

    def update_document(self, document: SourceDocument) -> None:
        if document.id not in self.documents:
            raise_error(ErrorCode.DOCUMENT_NOT_FOUND, "文件不存在", status_code=404)
        self.documents[document.id] = document
        logger.info(f"Document updated: {document.id}")

    def delete_document(self, document_id: str) -> None:
        if document_id not in self.documents:
            raise_error(ErrorCode.DOCUMENT_NOT_FOUND, "文件不存在", status_code=404)
        del self.documents[document_id]
        logger.info(f"Document deleted: {document_id}")

    # ===== BOQ Item Management =====

    def add_boq_item(self, item: BOQItem) -> None:
        self.boq_items[item.id] = item
        logger.info(f"BOQ item added: {item.id}")

    def get_boq_item(self, item_id: str) -> BOQItem:
        if item_id not in self.boq_items:
            raise_error(ErrorCode.RESOURCE_NOT_FOUND, "項目不存在", status_code=404)
        return self.boq_items[item_id]

    def get_items_by_document(self, document_id: str) -> List[BOQItem]:
        return [item for item in self.boq_items.values()
                if item.source_document_id == document_id]

    def update_boq_item(self, item: BOQItem) -> None:
        if item.id not in self.boq_items:
            raise_error(ErrorCode.RESOURCE_NOT_FOUND, "項目不存在", status_code=404)
        self.boq_items[item.id] = item
        logger.info(f"BOQ item updated: {item.id}")

    # ===== Quotation Management =====

    def add_quotation(self, quotation: Quotation) -> None:
        self.quotations[quotation.id] = quotation
        logger.info(f"Quotation added: {quotation.id}")

    def get_quotation(self, quotation_id: str) -> Quotation:
        if quotation_id not in self.quotations:
            raise_error(ErrorCode.QUOTATION_NOT_FOUND, "報價單不存在", status_code=404)
        return self.quotations[quotation_id]

    def list_quotations(self) -> List[Quotation]:
        return list(self.quotations.values())

    def update_quotation(self, quotation: Quotation) -> None:
        if quotation.id not in self.quotations:
            raise_error(ErrorCode.QUOTATION_NOT_FOUND, "報價單不存在", status_code=404)
        self.quotations[quotation.id] = quotation
        logger.info(f"Quotation updated: {quotation.id}")

    def delete_quotation(self, quotation_id: str) -> None:
        if quotation_id not in self.quotations:
            raise_error(ErrorCode.QUOTATION_NOT_FOUND, "報價單不存在", status_code=404)
        del self.quotations[quotation_id]
        logger.info(f"Quotation deleted: {quotation_id}")

    # ===== Processing Task Management =====

    def add_task(self, task: ProcessingTask) -> None:
        self.processing_tasks[task.task_id] = task
        logger.info(f"Task added: {task.task_id}")

    def get_task(self, task_id: str) -> ProcessingTask:
        if task_id not in self.processing_tasks:
            raise_error(ErrorCode.TASK_NOT_FOUND, "任務不存在", status_code=404)
        return self.processing_tasks[task_id]

    def update_task(self, task: ProcessingTask) -> None:
        if task.task_id not in self.processing_tasks:
            raise_error(ErrorCode.TASK_NOT_FOUND, "任務不存在", status_code=404)
        self.processing_tasks[task.task_id] = task
        logger.debug(f"Task updated: {task.task_id}")

    def get_tasks_by_document(self, document_id: str) -> List[ProcessingTask]:
        return [task for task in self.processing_tasks.values()
                if task.document_id == document_id]

    def list_tasks(self) -> List[ProcessingTask]:
        from datetime import datetime as dt_class
        tasks = list(self.processing_tasks.values())
        tasks.sort(key=lambda t: t.created_at or dt_class.min, reverse=True)
        return tasks

    # ===== Extracted Image Management =====

    def add_image(self, image: ExtractedImage) -> None:
        self.extracted_images[image.id] = image
        logger.info(f"Image added: {image.id}")

    def get_image(self, image_id: str) -> ExtractedImage:
        if image_id not in self.extracted_images:
            raise_error(ErrorCode.RESOURCE_NOT_FOUND, "圖片不存在", status_code=404)
        return self.extracted_images[image_id]

    def get_images_by_document(self, document_id: str) -> List[ExtractedImage]:
        return [image for image in self.extracted_images.values()
                if image.source_document_id == document_id]

    def get_images_by_item(self, item_id: str) -> List[ExtractedImage]:
        return [image for image in self.extracted_images.values()
                if image.boq_item_id == item_id]

    # ===== Merge Report Management =====

    def add_merge_report(self, report: MergeReport) -> None:
        self.merge_reports[report.id] = report
        logger.info(f"Merge report added: {report.id}")

    def get_merge_report(self, report_id: str) -> MergeReport:
        if report_id not in self.merge_reports:
            raise_error(ErrorCode.RESOURCE_NOT_FOUND, "合併報告不存在", status_code=404)
        return self.merge_reports[report_id]

    def get_merge_report_by_quotation(self, quotation_id: str) -> Optional[MergeReport]:
        for report in self.merge_reports.values():
            if report.quotation_id == quotation_id:
                return report
        return None

    # ===== Utility Methods =====

    def get_stats(self) -> Dict[str, Any]:
        return {
            "documents": len(self.documents),
            "boq_items": len(self.boq_items),
            "quotations": len(self.quotations),
            "processing_tasks": len(self.processing_tasks),
            "extracted_images": len(self.extracted_images),
            "merge_reports": len(self.merge_reports),
            "cache_ttl": self.cache_ttl,
        }


_store: Optional[InMemoryStore] = None


def get_store() -> InMemoryStore:
    from .config import settings

    global _store
    if _store is None:
        _store = InMemoryStore(cache_ttl=settings.store_cache_ttl)
    return _store
