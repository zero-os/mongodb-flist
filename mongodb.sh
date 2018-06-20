#!/bin/bash
set -ex

apt-get update
apt-get install -y git
apt-get install -y build-essential build-essential curl python-pip python-dev build-essential 
apt-get install -y build-essential libssl-dev libffi-dev python3-dev
apt-get install -y libboost-filesystem-dev libboost-program-options-dev libboost-system-dev libboost-thread-dev libcurl4-openssl-dev

git clone https://github.com/mongodb/mongo.git

cd mongo

git checkout r3.6.5

pip2 install -r buildscripts/requirements.txt

python2 buildscripts/scons.py mongod mongo mongos

mkdir -p /tmp/archives/

cd build/opt/mongo/

tar cfz "/tmp/archives/mongodb.tar.gz" --transform "s,^,usr/bin/," mongo mongod mongos



