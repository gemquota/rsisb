"""Tests for the codegen module (AST parser + engine)."""

import tempfile
import os

import pytest

from codegen.ast_parser import find_stubs, StubCoordinate, validate_patch_is_surgical
from codegen.engine import CodegenEngine


STUB_SAMPLE = """
def stub_pass():
    pass

def stub_ellipsis():
    ...

def stub_raise():
    raise NotImplementedError

def stub_return():
    return

def real_function():
    return 42

class MyClass:
    def method_stub(self):
        pass

    def real_method(self):
        return "hello"
"""


@pytest.fixture
def stub_file():
    tmp = os.path.join(tempfile.mkdtemp(), "stubs.py")
    with open(tmp, "w") as f:
        f.write(STUB_SAMPLE)
    return tmp


@pytest.fixture
def engine():
    return CodegenEngine()


class TestAstParser:
    def test_finds_all_stubs(self, stub_file):
        stubs = find_stubs(stub_file)
        assert len(stubs) == 5

    def test_stub_types(self, stub_file):
        stubs = find_stubs(stub_file)
        types = {s.name: s.stub_type for s in stubs}
        assert types["stub_pass"] == "pass"
        assert types["stub_ellipsis"] == "ellipsis"
        assert types["stub_raise"] == "raise_not_implemented"
        assert types["stub_return"] == "empty_return"

    def test_stub_coordinate_has_lines(self, stub_file):
        stubs = find_stubs(stub_file)
        for s in stubs:
            assert s.start_line >= 1
            assert s.end_line >= s.start_line
            assert len(s.source_lines) > 0

    def test_real_function_not_stub(self, stub_file):
        stubs = find_stubs(stub_file)
        names = [s.name for s in stubs]
        assert "real_function" not in names
        assert "real_method" not in names

    def test_sorted_by_line(self, stub_file):
        stubs = find_stubs(stub_file)
        for i in range(len(stubs) - 1):
            assert stubs[i].start_line <= stubs[i + 1].start_line

    def test_to_dict(self):
        coord = StubCoordinate(name="test", stub_type="pass", start_line=1, end_line=2, indent="    ")
        d = coord.to_dict()
        assert d["name"] == "test"
        assert d["stub_type"] == "pass"
        assert d["start_line"] == 1
        assert d["end_line"] == 2

    def test_validate_surgical_accepts_small_patch(self):
        coord = StubCoordinate(name="test", stub_type="pass", start_line=1, end_line=2,
                               source_lines=["def test():\n", "    pass\n"])
        assert validate_patch_is_surgical(coord, ["def test():", "    return 42"]) is True

    def test_validate_surgical_rejects_bloated_patch(self):
        coord = StubCoordinate(name="test", stub_type="pass", start_line=1, end_line=2,
                               source_lines=["def test():\n", "    pass\n"])
        assert validate_patch_is_surgical(coord, ["x"] * 20) is False


class TestCodegenEngine:
    def test_list_templates(self, engine):
        templates = engine.list_templates()
        assert "fix_stub.j2" in templates

    def test_render_unknown_template(self, engine):
        with pytest.raises(Exception):
            engine.render("nonexistent.j2", {})

    def test_generate_patch_pass(self, engine, stub_file):
        stubs = find_stubs(stub_file)
        pass_stub = [s for s in stubs if s.name == "stub_pass"][0]
        patch = engine.generate_patch(pass_stub, implementation="    return 100")
        assert "def stub_pass():" in patch
        assert "    return 100" in patch
        # Verify the 'pass' keyword body was removed (not the name 'stub_pass')
        assert "    pass" not in patch

    def test_generate_patch_ellipsis(self, engine, stub_file):
        stubs = find_stubs(stub_file)
        ellipsis_stub = [s for s in stubs if s.name == "stub_ellipsis"][0]
        patch = engine.generate_patch(ellipsis_stub, implementation="    return 200")
        assert "    return 200" in patch

    def test_generate_patch_raise(self, engine, stub_file):
        stubs = find_stubs(stub_file)
        raise_stub = [s for s in stubs if s.name == "stub_raise"][0]
        patch = engine.generate_patch(raise_stub, implementation="    return 300")
        assert "    return 300" in patch

    def test_generate_patch_method(self, engine, stub_file):
        stubs = find_stubs(stub_file)
        method_stub = [s for s in stubs if s.name == "method_stub"][0]
        patch = engine.generate_patch(method_stub, implementation="        return 42")
        assert "        return 42" in patch

    def test_surgical_validation_blocks_bloat(self, stub_file):
        stubs = find_stubs(stub_file)
        pass_stub = stubs[0]
        engine = CodegenEngine()
        impl = "x = 1\n" * 100
        with pytest.raises(ValueError, match="surgical"):
            engine.generate_patch(pass_stub, implementation=impl)
