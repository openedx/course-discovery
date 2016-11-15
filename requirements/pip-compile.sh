#! /bin/bash
echo "COMPILING BASE"
pip-compile base.in
echo "COMPILING DOCS"
pip-compile docs.in
echo "COMPILING OPTIONAL"
pip-compile optional.in
echo "COMPILING TEST"
pip-compile test.in
echo "COMPILING PRODUCTION"
pip-compile production.in
echo "COMPILING LOCAL"
pip-compile local.in

