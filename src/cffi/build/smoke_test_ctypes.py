import os, ctypes
lib_path = os.environ["YGO_LIB_PATH"]
lib = ctypes.CDLL(lib_path)
create_duel = getattr(lib, "create_duel", None)
end_duel = getattr(lib, "end_duel", None)
if create_duel is None or end_duel is None:
    raise SystemExit("Missing create_duel/end_duel exports (check nm + extern \"C\")")
create_duel.argtypes = [ctypes.c_uint32]
create_duel.restype = ctypes.c_void_p
end_duel.argtypes = [ctypes.c_void_p]
end_duel.restype = None
p = create_duel(1337)
if not p:
    raise SystemExit("create_duel returned NULL")
end_duel(p)
print("OK: dlopen + create_duel/end_duel smoke test passed")
