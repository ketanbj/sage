.PHONY: bootstrap doctor lint test test-integration build-containers build-einsums-container prepare-einsums demo demo-offline demo-symsan report check test-rust

bootstrap:
	uv sync --all-extras

doctor:
	uv run sage doctor

lint:
	uv run ruff format --check sage tests tools
	uv run ruff check sage tests tools
	uv run mypy sage

test:
	uv run pytest tests/unit

test-integration:
	uv run pytest tests/integration

build-containers:
	docker build --platform linux/amd64 -t sage-symsan:ecbe8a7 containers/symsan
	docker build -t sage-runner:latest containers/runner

build-einsums-container:
	docker build --platform linux/amd64 -t sage-einsums:22a1159 containers/einsums

prepare-einsums:
	uv run sage target prepare --target einsums

demo: demo-symsan

demo-offline: demo-symsan

demo-symsan:
	uv run sage run --target einsums --mode platform-demo --provider offline

report:
	uv run sage report --run "$$(ls -dt runs/* | head -1)"

test-rust:
	cargo fmt --check --manifest-path ports/einsums-rs/Cargo.toml
	rustfmt --check verification/einsums/tensor.rs
	cargo test --locked --offline --manifest-path ports/einsums-rs/Cargo.toml

check: lint test test-integration test-rust

.PHONY: build-einsums-python-container build-einsums-wheel validate-einsums-api
build-einsums-python-container:
	docker build --platform linux/amd64 -t sage-einsums-python:22a1159 containers/einsums-python

build-einsums-wheel:
	uv build --wheel ports/einsums-rs

validate-einsums-api:
	uv run python tools/validate_einsums_api.py --run "$(RUN)"

.PHONY: setup-verification prove-einsums
setup-verification:
	uv run python tools/setup_verification.py

prove-einsums:
	uv run sage prove --target einsums

.PHONY: demo-cpp20 prove-einsums-cpp20 test-cpp20
demo-cpp20:
	uv run sage run --config configs/einsums-cpp.yaml --provider offline

prove-einsums-cpp20:
	uv run sage prove --target einsums --language cpp20

test-cpp20:
	uv run pytest tests/unit/test_modern_cpp.py tests/integration/test_einsums_cpp.py

.PHONY: build-einsums-cpp-wheel demo-cpp20-library validate-einsums-cpp-api test-cpp20-library
build-einsums-cpp-wheel:
	uv run python tools/build_einsums_cpp_wheel.py

demo-cpp20-library:
	uv run sage run --config configs/einsums-cpp-library.yaml --provider offline

validate-einsums-cpp-api:
	uv run python tools/validate_einsums_api.py --language cpp20 --run "$(RUN)"

test-cpp20-library:
	uv run pytest tests/integration/test_einsums_cpp_library.py tests/integration/test_einsums_python_api.py -k cpp
