import tempfile, os
from codegen.ast_parser import find_stubs
from codegen.engine import CodegenEngine

STUB_SAMPLE = """
def stub_pass():
    pass
"""

tmp = os.path.join(tempfile.mkdtemp(), 'stubs.py')
with open(tmp, 'w') as f:
    f.write(STUB_SAMPLE)

stubs = find_stubs(tmp)
pass_stub = stubs[0]
print(f"stubs[0]: {pass_stub}")
print(f"source_lines: {pass_stub.source_lines}")
print(f"len source_lines: {len(pass_stub.source_lines)}")

impl = "x = 1\n" * 100
print(f"impl lines: {len(impl.splitlines())}")
engine = CodegenEngine()
try:
    r = engine.generate_patch(pass_stub, implementation=impl)
    print(f"NO ERROR - got {len(r.splitlines())} lines rendered")
except ValueError as e:
    print(f"ValueError: {e}")
