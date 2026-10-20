"""Chapter 6 · Run It While You Sleep — the same code, deployed.

The agent package is byte-for-byte the chapter 5 package. Anything that
differs here is a bug: the cloud run has to behave exactly like the local one.
The deployable files (main.py, Dockerfile, requirements.txt, monstertix/) are
checked by their own tests.
"""
import filecmp

from harness import SOLUTIONS, load_step


def test_the_agent_package_is_identical_to_chapter_five():
    a = SOLUTIONS / "step5_buy" / "concert"
    b = SOLUTIONS / "step6_cloud" / "concert"
    assert b.is_dir()
    names = sorted(p.name for p in a.glob("*.py"))
    assert names == sorted(p.name for p in b.glob("*.py"))
    same, different, funny = filecmp.cmpfiles(a, b, names, shallow=False)
    assert not different and not funny, f"chapter 6 drifted from chapter 5: {different or funny}"


def test_it_still_loads_as_the_graph():
    from google.adk.workflow import Workflow
    m = load_step("step6_cloud")
    assert isinstance(m.root_agent, Workflow)
    assert m.app.name == "concert"
    assert m.app.resumability_config.is_resumable
