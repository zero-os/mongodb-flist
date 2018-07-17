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

jobs=$(($(grep -c 'bogomips' /proc/cpuinfo) + 1))

python2 buildscripts/scons.py mongod mongo mongos -j $jobs

cd build/opt/mongo/
strip -s mongo
strip -s mongod
strip -s mongos

mkdir -p /tmp/archives/
tar cf "/tmp/archives/mongodb.tar.gz" --transform "s,^,usr/bin/," mongo mongod mongos

function collect_dependencies(){
for lib in `ldd "$PATH_TO_BINARY" | cut -d'>' -f2 ` ; do
   if [ -f "$lib" ] ; then
        tar rvf "/tmp/archives/mongodb.tar.gz" $lib
   fi
done
}

PATH_TO_BINARY=mongo
collect_dependencies
PATH_TO_BINARY=mongod
collect_dependencies
PATH_TO_BINARY=mongos
collect_dependencies





