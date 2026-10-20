"""Chapter 3 · Remember What Matters — four places a fact can live.

Students find session state, user: state, an artifact and a memory file, and
predict which survives. These tests hold the wiring in place so the exercise
still has four different answers — and so compaction is really on, with a model
of its own, or there is nothing to look at.
"""
from harness import FakeToolContext, drive, load_step, needs_model, tool_names


def test_memory_is_a_real_memory_service():
    load_step("step3_remember")
    from concert import memory
    from google.adk.memory import BaseMemoryService
    assert isinstance(memory.memory_service, BaseMemoryService), \
        "the chapter teaches BaseMemoryService — it has to actually be one"


def test_recall_is_async():
    """It awaits search_memory. A sync recall() raises 'asyncio.run() cannot be
    called from a running event loop' the first time a student uses it."""
    import inspect
    load_step("step3_remember")
    from concert import memory
    assert inspect.iscoroutinefunction(memory.recall)


def test_the_agent_can_write_to_all_four_places():
    m = load_step("step3_remember")
    names = tool_names(m.root_agent)
    assert "note_companion" in names   # user: state
    assert "remember" in names          # the memory file
    assert "recall" in names
    assert "get_seatmap" in names       # temp: state + an artifact
    assert "purchase" not in names, "still nothing that spends money"


def test_get_seatmap_writes_temp_state_and_an_artifact():
    import inspect
    load_step("step3_remember")
    from concert import tools
    src = inspect.getsource(tools.get_seatmap)
    assert "temp:seatmap" in src, "the temp: trap is the point of the chapter"
    assert "save_artifact" in src


def test_note_companion_writes_user_scoped_state():
    load_step("step3_remember")
    from concert import tools
    ctx = FakeToolContext()
    out = tools.note_companion("Sam", "cannot do weeknights", ctx)
    assert ctx.state["user:prefs"] == {"Sam": "cannot do weeknights"}
    assert out["companions"]["Sam"]
    assert not any(k for k in ctx.state if not k.startswith("user:")), \
        "a companion is a fact about the person, so it is user: state only"


def test_compaction_is_on_with_its_own_model():
    m = load_step("step3_remember")
    cfg = m.app.events_compaction_config
    assert cfg is not None, "no compaction means the chapter has nothing to show"
    assert cfg.compaction_interval > 0
    assert cfg.overlap_size > 0, "overlap_size has no default — ADK requires it"
    assert cfg.summarizer is not None, \
        "name the summariser's model now; the root becomes a Workflow later and has none"


def test_remember_appends_one_line_under_preferences(tmp_path, monkeypatch):
    load_step("step3_remember")
    from concert import memory
    monkeypatch.setattr(memory, "memory_service", memory.MarkdownMemoryService(tmp_path))
    memory.remember("Sam bails on weeknights.")
    text = (tmp_path / f"{memory.MEMORY_USER}.md").read_text()
    assert "## Preferences" in text
    assert "- Sam bails on weeknights." in text


@needs_model
def test_seatmap_produces_an_artifact(venue):
    m = load_step("step3_remember")
    t = drive(m.root_agent, ["Show me the seat map for the Amsterdam Saturday show."])
    assert t.called("get_seatmap")


class _FakeBlob:
    def __init__(self, store, name):
        self.store, self.name = store, name

    def exists(self):
        return self.name in self.store

    def download_as_text(self):
        return self.store[self.name]

    def upload_from_string(self, text, content_type=None):
        self.store[self.name] = text


class _FakeBucket:
    def __init__(self, store, name):
        self.store, self.name = store, name

    def blob(self, name):
        return _FakeBlob(self.store, f"{self.name}/{name}")


class _FakeStorage:
    """Just enough of google.cloud.storage for the two methods the seam uses."""
    store: dict = {}

    class Client:
        def bucket(self, name):
            return _FakeBucket(_FakeStorage.store, name)


def test_memory_moves_to_a_bucket_with_a_path_change(monkeypatch):
    """On Cloud Run MEMORY_DIR is gs://<bucket>/memory. The same two-method
    service must read and write a blob there, not a local 'gs:/' directory."""
    import sys, types
    load_step("step3_remember")
    from concert import memory

    _FakeStorage.store = {}
    fake_pkg = types.ModuleType("google.cloud")
    fake_pkg.storage = _FakeStorage
    monkeypatch.setitem(sys.modules, "google.cloud", fake_pkg)
    monkeypatch.setitem(sys.modules, "google.cloud.storage", _FakeStorage)

    svc = memory.MarkdownMemoryService("gs://my-bucket/memory")
    assert svc.is_bucket
    assert svc._read("userx") is None, "a read miss is empty, not an error"
    assert svc.location("userx") == "gs://my-bucket/memory/userx.md"

    monkeypatch.setattr(memory, "memory_service", svc)
    out = memory.remember("Sam bails on weeknights.")
    assert out["file"] == "gs://my-bucket/memory/userx.md"
    assert "my-bucket/memory/userx.md" in _FakeStorage.store
    assert "- Sam bails on weeknights." in svc._read("userx")

    import asyncio
    got = asyncio.run(memory.recall())
    assert "Sam bails on weeknights." in got["memory"]
    assert got["source"] == "gs://my-bucket/memory/userx.md"
    import os
    assert not os.path.exists("gs:"), "nothing may be written to a local gs:/ directory"


def test_recall_on_an_empty_local_root_says_where_it_looked(tmp_path, monkeypatch):
    import asyncio
    load_step("step3_remember")
    from concert import memory
    monkeypatch.setattr(memory, "memory_service", memory.MarkdownMemoryService(tmp_path / "none"))
    got = asyncio.run(memory.recall())
    assert got["memory"] == ""
    assert got["looked_at"].endswith(f"none/{memory.MEMORY_USER}.md")
