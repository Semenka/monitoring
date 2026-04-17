.PHONY: install system-deps convert fetch run verify test clean

install:
	pip install -r requirements.txt

system-deps:
	sudo apt-get update && sudo apt-get install -y mdbtools

fetch:
	python -m scripts.convert_mdb --config configs/qw_mn.yaml --download --fetch-only

convert:
	python -m scripts.convert_mdb --config configs/qw_mn.yaml

run:
	streamlit run app.py

verify:
	python -m scripts.verify --config configs/qw_mn.yaml

test:
	pytest -q

clean:
	rm -rf data/staging data/warehouse

clean-all: clean
	rm -rf data/raw
