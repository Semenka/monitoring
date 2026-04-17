.PHONY: install system-deps sample convert convert-all run verify verify-all test clean clean-all

install:
	pip install -r requirements.txt

system-deps:
	sudo apt-get update && sudo apt-get install -y mdbtools

# -- Demo / synthetic ----------------------------------------------------

sample:
	python scripts/generate_sample.py
	python scripts/convert_mdb.py --config configs/sample.yaml --force
	python scripts/convert_mdb.py --config configs/sample_asab.yaml --force
	python scripts/convert_mdb.py --config configs/sample_sahil.yaml --force
	python scripts/convert_mdb.py --config configs/sample_shah.yaml --force

# -- Real OFM databases --------------------------------------------------

convert-qw_mn:
	python scripts/convert_mdb.py --config configs/qw_mn.yaml

convert-asab:
	python scripts/convert_mdb.py --config configs/asab.yaml

convert-sahil:
	python scripts/convert_mdb.py --config configs/sahil.yaml

convert-shah:
	python scripts/convert_mdb.py --config configs/shah.yaml

convert-all: convert-qw_mn convert-asab convert-sahil convert-shah

# -- Runtime -------------------------------------------------------------

run:
	streamlit run app.py

verify:
	python scripts/verify.py --config configs/sample.yaml

verify-all:
	@for cfg in configs/*.yaml; do python scripts/verify.py --config $$cfg || true; done

test:
	PYTHONPATH=src pytest -q

clean:
	rm -rf data/staging data/warehouse

clean-all: clean
	rm -rf data/raw/*.mdb data/raw/SAMPLE*.synthetic
