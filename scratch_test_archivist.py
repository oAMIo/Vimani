from app.archivist.impl_jsonl import JsonlArchivist
print(">>> scratch_test_archivist.py started")

arch = JsonlArchivist()
res = arch.store_run({"run_id": "run_test_1", "tool_key": "clickup", "status": "SUCCESS"})
print(res)
