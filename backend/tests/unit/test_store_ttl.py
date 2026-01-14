"""Tests for InMemoryStore TTL cleanup mechanism."""

import time
import pytest
from datetime import datetime, timedelta

from app.store import InMemoryStore
from app.models import SourceDocument, BOQItem, ProcessingTask


class TestInMemoryStoreTTL:
    """Test TTL-based cleanup functionality."""

    def test_store_initialization_with_ttl(self):
        """Test store initializes with TTL and cleanup interval."""
        store = InMemoryStore(cache_ttl=60, cleanup_interval=10)
        assert store.cache_ttl == 60
        assert store._cleanup_interval == 10
        store.shutdown()

    def test_record_access_updates_timestamp(self):
        """Test that adding items records access timestamp."""
        store = InMemoryStore(cache_ttl=3600)

        doc = SourceDocument(
            id="doc-1",
            filename="test.pdf",
            file_path="/tmp/test.pdf",
            file_size=1000,
            mime_type="application/pdf",
        )
        store.add_document(doc)

        assert "doc-1" in store._timestamps
        assert isinstance(store._timestamps["doc-1"], datetime)
        store.shutdown()

    def test_cleanup_removes_expired_entries(self):
        """Test that expired entries are removed during cleanup."""
        # Create store with very short TTL
        store = InMemoryStore(cache_ttl=1, cleanup_interval=999)  # Manual cleanup

        # Add a document
        doc = SourceDocument(
            id="doc-expired",
            filename="test.pdf",
            file_path="/tmp/test.pdf",
            file_size=1000,
            mime_type="application/pdf",
        )
        store.add_document(doc)

        # Verify document exists
        assert "doc-expired" in store.documents
        assert "doc-expired" in store._timestamps

        # Manually set timestamp to past (simulate expiration)
        store._timestamps["doc-expired"] = datetime.now() - timedelta(seconds=10)

        # Trigger cleanup
        store._cleanup_expired()

        # Verify document is removed
        assert "doc-expired" not in store.documents
        assert "doc-expired" not in store._timestamps
        store.shutdown()

    def test_cleanup_preserves_fresh_entries(self):
        """Test that fresh entries are not removed during cleanup."""
        store = InMemoryStore(cache_ttl=3600, cleanup_interval=999)

        doc = SourceDocument(
            id="doc-fresh",
            filename="test.pdf",
            file_path="/tmp/test.pdf",
            file_size=1000,
            mime_type="application/pdf",
        )
        store.add_document(doc)

        # Trigger cleanup (should not remove fresh document)
        store._cleanup_expired()

        # Verify document still exists
        assert "doc-fresh" in store.documents
        store.shutdown()

    def test_multiple_collection_cleanup(self):
        """Test cleanup works across all collections."""
        store = InMemoryStore(cache_ttl=1, cleanup_interval=999)

        # Add items to different collections with same ID
        doc = SourceDocument(
            id="item-1",
            filename="test.pdf",
            file_path="/tmp/test.pdf",
            file_size=1000,
            mime_type="application/pdf",
        )
        store.add_document(doc)

        task = ProcessingTask(
            task_id="item-1",
            document_id="doc-1",
            task_type="parse_pdf",
            status="pending",
        )
        store.add_task(task)

        # Set both to expired
        store._timestamps["item-1"] = datetime.now() - timedelta(seconds=10)

        # Trigger cleanup
        store._cleanup_expired()

        # Both should be removed
        assert "item-1" not in store.documents
        assert "item-1" not in store.processing_tasks
        store.shutdown()

    def test_shutdown_stops_cleanup_thread(self):
        """Test that shutdown properly stops the cleanup thread."""
        store = InMemoryStore(cache_ttl=3600, cleanup_interval=1)

        # Give thread time to start
        time.sleep(0.1)

        # Verify thread is running
        assert store._cleanup_thread.is_alive()

        # Shutdown
        store.shutdown()

        # Give thread time to stop
        time.sleep(0.2)

        # Verify thread has stopped
        assert not store._cleanup_thread.is_alive()

    def test_stats_include_ttl(self):
        """Test that stats include TTL information."""
        store = InMemoryStore(cache_ttl=7200)
        stats = store.get_stats()

        assert "cache_ttl" in stats
        assert stats["cache_ttl"] == 7200
        store.shutdown()

    def test_thread_safe_access(self):
        """Test that concurrent access is thread-safe."""
        import threading

        store = InMemoryStore(cache_ttl=3600, cleanup_interval=999)
        errors = []

        def add_documents(start_id: int):
            try:
                for i in range(10):
                    doc = SourceDocument(
                        id=f"doc-{start_id}-{i}",
                        filename=f"test-{i}.pdf",
                        file_path=f"/tmp/test-{i}.pdf",
                        file_size=1000,
                        mime_type="application/pdf",
                    )
                    store.add_document(doc)
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = [
            threading.Thread(target=add_documents, args=(i * 100,))
            for i in range(5)
        ]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # No errors should have occurred
        assert len(errors) == 0

        # All documents should be added
        assert len(store.documents) == 50
        store.shutdown()


class TestInMemoryStoreCleanupLoop:
    """Test the background cleanup loop."""

    def test_cleanup_loop_runs_periodically(self):
        """Test that cleanup loop runs at configured interval."""
        # Very short interval for testing
        store = InMemoryStore(cache_ttl=1, cleanup_interval=1)

        # Add expired document
        doc = SourceDocument(
            id="doc-auto-cleanup",
            filename="test.pdf",
            file_path="/tmp/test.pdf",
            file_size=1000,
            mime_type="application/pdf",
        )
        store.add_document(doc)

        # Make it expired
        store._timestamps["doc-auto-cleanup"] = datetime.now() - timedelta(seconds=10)

        # Wait for cleanup to run
        time.sleep(1.5)

        # Document should be auto-cleaned
        assert "doc-auto-cleanup" not in store.documents
        store.shutdown()
