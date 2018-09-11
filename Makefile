tox: clean
	tox
install:
	pip install -r requirements-dev.txt
clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete
	rm -r -f *.egg-info
	rm -r -f .cache
	rm -r -f .eggs
	rm -r -f .tox
	rm -r -f build
	rm -r -f dist
sdist: clean
	python setup.py sdist
test:
	py.test -v -x tests
doc:
	cd docs && make html
testpypi: clean
	pip install --upgrade wheel twine
	python setup.py sdist bdist_wheel
	twine upload --repository-url https://test.pypi.org/legacy/ dist/*
pypi: clean
	pip install --upgrade wheel twine
	python setup.py sdist bdist_wheel
	twine upload dist/*
cov:
	py.test -v --cov-report=term-missing --cov=aiomongodel tests
