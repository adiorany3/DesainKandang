# Project context

Latest update: user clarified wrong exhaust wall placement. Fans now locked to rear end wall spanning width, with rear three-quarter view; front equipment may be occluded. Removed fan inset and conflicting three-facade/all-equipment visibility requirement. Template changes refresh session prompts, replacing edits. Latest helper/UI tests: 99 passed; diff check clean. Fingerprints below predate this update and MUST NOT be trusted without recalculation. Latest source was inspected and tested; visual result remains unverified. Prior full-suite results below were not rerun this iteration.

Root: /Users/macbookpro/Documents/GitHub/DesainKandang. Branch main; inspected HEAD 1f61c448e4641b2b5da47b2f3209d455d249ba25. Python Streamlit concept-image generator; app.py owns UI and prompt construction, trust_client.py handles providers. No provider requests were made for this task.

Uncommitted changes: app.py, README.md, tests/test_app_helpers.py, tests/test_streamlit_ui.py. Added shared EXHAUST_FAN_INSTRUCTION to full prompt and Bynara automatic condensation. Specifies wall-relative scale, mounted frame, structural clearance, consistent module sizes, perspective and separate inset instead of oversized equipment. No invented engineering fan dimensions or counts. Negative prompt rejects giant fans and fisheye. User image attachment was unavailable for inspection; visual outcome remains unverified.

SHA-256 fingerprints:
- app.py: e3ddb361954b6bcedfc00f803d288c6f22086ade54f9625a00b35b4c66a5530d
- tests/test_app_helpers.py: 663a29dee33f146a6bdd869b612145b7e7902d58473009d5605e4009367b0dd1
- tests/test_streamlit_ui.py: fed4de21b4bf4067284ed5fd9224123f015928ce6cdf5b922e461e8822c6b851
- README.md: 4354aab30d02ab9d4ba9899b16cca653f07ba8e257d17688be47a9c189694b48

Validation: .venv/bin/python -m pytest -q: 157 passed, 3 failed in test_trust_client.py (Bynara request model/size/quality expectations). trust_client.py and its tests unchanged against HEAD; baseline suite not separately executed. Focused helpers/UI suite: 95 passed. git diff --check clean. Prompt limits tested for full and condensed variants across styles; no paid image generation or visual verification.

Next: generate a new concept using refreshed default prompts and inspect fan proportions. Existing edited prompts are preserved by application reruns. Engineering sizing requires ventilation calculations and product dimensions. Avoid reading local secrets. Use git --no-pager for diff (default pager blocked one inspection command).