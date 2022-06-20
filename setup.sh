#!/bin/bash -e
# Setup virtualenv for testing and development
#

realpath() {
    perl -MCwd -e 'print Cwd::realpath($ARGV[0]),qq<\n>' "$1"
}

root=${0%/*}
req=$(realpath ${root}/requirements.txt)
venv=$(realpath ${root}/venv)
python3=$(command -v python3) || echo "could not find python 3"
virtualenv=$(command -v virtualenv) || { echo "could not find python virtualenv"; exit 1; }
PYTHON=${PYTHON:-$python3}  # if variable not set/null use $python3
if [[ ! -e "$PYTHON" ]]; then
    echo "No python found, or specified, stopping"
    exit 1
fi

echo "setup virtualenv for testing and devel (${venv})"
echo "python: $PYTHON"
echo "press enter to continue with setup..."
read ENT

echo "starting setup..."
pushd $root >/dev/null
echo "creating virtualenv for $($PYTHON --version)..."
$virtualenv -p ${PYTHON} --always-copy --no-download ${venv}

echo "installing required packages..."
source ${venv}/bin/activate
pip=$(command -v pip) || { echo "could not find pip in virtualenv"; exit 1; }
$pip install -r $req
$pip install -e .[test]
popd >/dev/null

