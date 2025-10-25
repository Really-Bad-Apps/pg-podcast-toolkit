#!/bin/bash
# something like this to build and publish to pypi

rm dist/*
python -m build
python -m twine upload dist/*
