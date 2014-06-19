# applied research

PYTHON=$(shell which python)

default: build

egg:
	@python setup.py bdist_egg

build: distclean
	@python setup.py bdist_egg

install: build
	@zenpack --install dist/*.egg
	@zopectl restart
	@zenactiond restart

reload: remove install

clean:
	@rm -rf build *.egg-info

distclean:
	@rm -rf build dist *.egg-info

remove:
	@zenpack --remove ZenPacks.research.JIRA
	@zopectl restart

check:
	@echo -e "python : ${PYTHON}"
