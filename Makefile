DESTDIR ?= /
PREFIX ?= /usr

PYTHON ?= python3

install:
	# Cleanup temporary files
	rm -f INSTALLED_FILES

	# Use Python setuptools
	${PYTHON} ./setup.py install -O1 --prefix="${PREFIX}" --root="${DESTDIR}" --record=INSTALLED_FILES

test:
	${PYTHON} -m pytest tests -svvvv --junitprefix=dpres-access-rest-api-client --junitxml=junit.xml

coverage:
	${PYTHON} -m pytest tests \
		--cov=dpres_access_rest_api_client \
		--cov-report=html \
		--cov-report=xml \
		--cov-report=term

clean: clean-rpm
	find . -iname '*.pyc' -type f -delete
	find . -iname '__pycache__' -exec rm -rf '{}' \; | true
	rm -rf coverage.xml htmlcov junit.xml .coverage

clean-rpm:
	rm -rf rpmbuild

rpm: clean
	create-archive.sh
	preprocess-spec-m4-macros.sh include/rhel7
	build-rpm.sh
