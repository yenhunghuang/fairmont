"""In-memory store for documents, tasks, quotations, and images."""

import logging
from typing import Dict, List, Optional
from cachetools import TTLCache

from .models import (
    SourceDocument,
    BOQItem,
    Quotation,
    ProcessingTask,
    ExtractedImage,
)
from .utils import ErrorCode, raise_error


logger = logging.getLogger(__name__)


class InMemoryStore:
    """In-memory storage for all application data."""

    def __init__(self, cache_ttl: int = 3600):
        """
        Initialize InMemoryStore.

        Args:
            cache_ttl: Cache time-to-live in seconds (default 1 hour)
        """
        # Store documents with TTL cache (auto-cleanup after cache_ttl)
        self.documents: Dict[str, SourceDocument] = {}
        self.document_cache = TTLCache(maxsize=100, ttl=cache_ttl)

        # Store BOQ items
        self.boq_items: Dict[str, BOQItem] = {}

        # Store quotations with TTL cache
        self.quotations: Dict[str, Quotation] = {}
        self.quotation_cache = TTLCache(maxsize=50, ttl=cache_ttl)

        # Store processing tasks with TTL cache
        self.processing_tasks: Dict[str, ProcessingTask] = {}
        self.task_cache = TTLCache(maxsize=200, ttl=3600)  # Tasks live longer

        # Store extracted images with TTL cache
        self.extracted_images: Dict[str, ExtractedImage] = {}
        self.image_cache = TTLCache(maxsize=500, ttl=cache_ttl)

        logger.info("InMemoryStore initialized")

    # ===== Document Management =====

    def add_document(self, document: SourceDocument) -> None:
        """
        Add a source document.

        Args:
            document: SourceDocument to add
        """
        self.documents[document.id] = document
        self.document_cache[document.id] = document
        logger.info(f"Document added: {document.id}")

    def get_document(self, document_id: str) -> SourceDocument:
        """
        Get a document by ID.

        Args:
            document_id: Document ID

        Returns:
            SourceDocument

        Raises:
            APIError: If document not found
        """
        if document_id not in self.documents:
            raise_error(ErrorCode.DOCUMENT_NOT_FOUND, "文件不存在")
        return self.documents[document_id]

    def list_documents(self) -> List[SourceDocument]:
        """
        List all documents.

        Returns:
            List of SourceDocument objects
        """
        return list(self.documents.values())

    def update_document(self, document: SourceDocument) -> None:
        """
        Update a document.

        Args:
            document: Updated SourceDocument
        """
        if document.id not in self.documents:
            raise_error(ErrorCode.DOCUMENT_NOT_FOUND, "文件不存在")
        self.documents[document.id] = document
        self.document_cache[document.id] = document
        logger.info(f"Document updated: {document.id}")

    def delete_document(self, document_id: str) -> None:
        """
        Delete a document.

        Args:
            document_id: Document ID to delete
        """
        if document_id not in self.documents:
            raise_error(ErrorCode.DOCUMENT_NOT_FOUND, "文件不存在")
        del self.documents[document_id]
        self.document_cache.pop(document_id, None)
        logger.info(f"Document deleted: {document_id}")

    # ===== BOQ Item Management =====

    def add_boq_item(self, item: BOQItem) -> None:
        """
        Add a BOQ item.

        Args:
            item: BOQItem to add
        """
        self.boq_items[item.id] = item
        logger.info(f"BOQ item added: {item.id}")

    def get_boq_item(self, item_id: str) -> BOQItem:
        """
        Get a BOQ item by ID.

        Args:
            item_id: Item ID

        Returns:
            BOQItem

        Raises:
            APIError: If item not found
        """
        if item_id not in self.boq_items:
            raise_error(ErrorCode.RESOURCE_NOT_FOUND, "項目不存在")
        return self.boq_items[item_id]

    def get_items_by_document(self, document_id: str) -> List[BOQItem]:
        """
        Get all BOQ items from a specific document.

        Args:
            document_id: Source document ID

        Returns:
            List of BOQItem objects
        """
        return [item for item in self.boq_items.values()
                if item.source_document_id == document_id]

    def update_boq_item(self, item: BOQItem) -> None:
        """
        Update a BOQ item.

        Args:
            item: Updated BOQItem
        """
        if item.id not in self.boq_items:
            raise_error(ErrorCode.RESOURCE_NOT_FOUND, "項目不存在")
        self.boq_items[item.id] = item
        logger.info(f"BOQ item updated: {item.id}")

    # ===== Quotation Management =====

    def add_quotation(self, quotation: Quotation) -> None:
        """
        Add a quotation.

        Args:
            quotation: Quotation to add
        """
        self.quotations[quotation.id] = quotation
        self.quotation_cache[quotation.id] = quotation
        logger.info(f"Quotation added: {quotation.id}")

    def get_quotation(self, quotation_id: str) -> Quotation:
        """
        Get a quotation by ID.

        Args:
            quotation_id: Quotation ID

        Returns:
            Quotation

        Raises:
            APIError: If quotation not found
        """
        if quotation_id not in self.quotations:
            raise_error(ErrorCode.QUOTATION_NOT_FOUND, "報價單不存在")
        return self.quotations[quotation_id]

    def list_quotations(self) -> List[Quotation]:
        """
        List all quotations.

        Returns:
            List of Quotation objects
        """
        return list(self.quotations.values())

    def update_quotation(self, quotation: Quotation) -> None:
        """
        Update a quotation.

        Args:
            quotation: Updated Quotation
        """
        if quotation.id not in self.quotations:
            raise_error(ErrorCode.QUOTATION_NOT_FOUND, "報價單不存在")
        self.quotations[quotation.id] = quotation
        self.quotation_cache[quotation.id] = quotation
        logger.info(f"Quotation updated: {quotation.id}")

    def delete_quotation(self, quotation_id: str) -> None:
        """
        Delete a quotation.

        Args:
            quotation_id: Quotation ID to delete
        """
        if quotation_id not in self.quotations:
            raise_error(ErrorCode.QUOTATION_NOT_FOUND, "報價單不存在")
        del self.quotations[quotation_id]
        self.quotation_cache.pop(quotation_id, None)
        logger.info(f"Quotation deleted: {quotation_id}")

    # ===== Processing Task Management =====

    def add_task(self, task: ProcessingTask) -> None:
        """
        Add a processing task.

        Args:
            task: ProcessingTask to add
        """
        self.processing_tasks[task.task_id] = task
        self.task_cache[task.task_id] = task
        logger.info(f"Task added: {task.task_id}")

    def get_task(self, task_id: str) -> ProcessingTask:
        """
        Get a task by ID.

        Args:
            task_id: Task ID

        Returns:
            ProcessingTask

        Raises:
            APIError: If task not found
        """
        if task_id not in self.processing_tasks:
            raise_error(ErrorCode.TASK_NOT_FOUND, "任務不存在")
        return self.processing_tasks[task_id]

    def update_task(self, task: ProcessingTask) -> None:
        """
        Update a processing task.

        Args:
            task: Updated ProcessingTask
        """
        if task.task_id not in self.processing_tasks:
            raise_error(ErrorCode.TASK_NOT_FOUND, "任務不存在")
        self.processing_tasks[task.task_id] = task
        self.task_cache[task.task_id] = task
        logger.debug(f"Task updated: {task.task_id}")

    def get_tasks_by_document(self, document_id: str) -> List[ProcessingTask]:
        """
        Get all tasks for a specific document.

        Args:
            document_id: Document ID

        Returns:
            List of ProcessingTask objects
        """
        return [task for task in self.processing_tasks.values()
                if task.document_id == document_id]

    def list_tasks(self) -> List[ProcessingTask]:
        """
        List all processing tasks (sorted by created_at descending).

        Returns:
            List of ProcessingTask objects sorted by creation time (newest first)
        """
        tasks = list(self.processing_tasks.values())
        # Sort by created_at descending (newest first)
        from datetime import datetime as dt_class
        tasks.sort(key=lambda t: t.created_at or dt_class.min, reverse=True)
        return tasks

    # ===== Extracted Image Management =====

    def add_image(self, image: ExtractedImage) -> None:
        """
        Add an extracted image.

        Args:
            image: ExtractedImage to add
        """
        self.extracted_images[image.id] = image
        self.image_cache[image.id] = image
        logger.info(f"Image added: {image.id}")

    def get_image(self, image_id: str) -> ExtractedImage:
        """
        Get an image by ID.

        Args:
            image_id: Image ID

        Returns:
            ExtractedImage

        Raises:
            APIError: If image not found
        """
        if image_id not in self.extracted_images:
            raise_error(ErrorCode.RESOURCE_NOT_FOUND, "圖片不存在")
        return self.extracted_images[image_id]

    def get_images_by_document(self, document_id: str) -> List[ExtractedImage]:
        """
        Get all images from a specific document.

        Args:
            document_id: Source document ID

        Returns:
            List of ExtractedImage objects
        """
        return [image for image in self.extracted_images.values()
                if image.source_document_id == document_id]

    def get_images_by_item(self, item_id: str) -> List[ExtractedImage]:
        """
        Get all images associated with a BOQ item.

        Args:
            item_id: BOQ item ID

        Returns:
            List of ExtractedImage objects
        """
        return [image for image in self.extracted_images.values()
                if image.boq_item_id == item_id]

    # ===== Utility Methods =====

    def clear_expired(self) -> None:
        """Clear expired items from caches."""
        # TTLCache handles expiration automatically
        logger.info("Cache cleanup performed")

    def get_stats(self) -> Dict[str, int]:
        """
        Get store statistics.

        Returns:
            Dictionary with counts of stored items
        """
        return {
            "documents": len(self.documents),
            "boq_items": len(self.boq_items),
            "quotations": len(self.quotations),
            "processing_tasks": len(self.processing_tasks),
            "extracted_images": len(self.extracted_images),
        }


# Global store instance (singleton pattern)
_store: Optional[InMemoryStore] = None


def get_store(cache_ttl: int = 3600) -> InMemoryStore:
    """
    Get or create global store instance.

    Args:
        cache_ttl: Cache time-to-live in seconds

    Returns:
        InMemoryStore instance
    """
    global _store
    if _store is None:
        _store = InMemoryStore(cache_ttl=cache_ttl)
    return _store
