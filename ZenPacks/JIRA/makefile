# applied research

PYTHON=$(shell which python)

default: build

egg:
	@python setup.py bdist_egg

build:
	@python setup.py bdist_egg

install: build
	@zenpack --install dist/*.egg

clean:
	@rm -rf build dist *.egg-info

check:
	@echo -e "python : ${PYTHON}"
