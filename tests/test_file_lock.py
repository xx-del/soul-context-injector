import json
import threading
import pytest
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from enforcer import file_lock

def test_file_lock_prevents_concurrent_write(tmp_path):
    """Test that file_lock prevents race conditions in concurrent writes."""
    test_file = tmp_path / "test.json"
    test_file.write_text('{}')

    results = []

    def write_with_lock(value):
        with file_lock(test_file, 'w') as f:
            f.write(json.dumps({"value": value}))
        results.append(value)

    t1 = threading.Thread(target=write_with_lock, args=("first",))
    t2 = threading.Thread(target=write_with_lock, args=("second",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(results) == 2  # Both writes completed
    data = json.loads(test_file.read_text())
    assert data["value"] in ["first", "second"]  # One of them won

def test_file_lock_read_mode(tmp_path):
    """Test that file_lock works in read mode."""
    test_file = tmp_path / "test.json"
    test_file.write_text('{"test": "data"}')

    with file_lock(test_file, 'r') as f:
        content = f.read()

    assert content == '{"test": "data"}'
