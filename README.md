# MongoDB flist

This repository contains [MongoDB](https://github.com/mongodb/mongo) buildscripts used to download and compile [MongoDB](https://github.com/mongodb/mongo) of version 3.6.5.

**Binaries**: `/usr/bin/mongo`, `/usr/bin/mongod`, `/usr/bin/mongos`.

## Usage example
An example of mongobd deployment in Zero-os containers can be found [here](/setup_local_replica_set.py).

* Prior to the deployment [Zero-os](https://github.com/zero-os/0-core) node with 0-robot has to be created. Options for booting Zero-os find [here](https://github.com/zero-os/0-core/tree/master/docs/booting).
* Cluster is deployed on basis of 3 containers, booted from [mongodb flist](https://hub.gig.tech/ekaterina_evdokimova_1/ubuntu-16.04-mongodb.flist.md).
* Each container runs a shard of a shard server replica set and a shard of config server replica set.
* Cluster can be reached by communicating with a mongos instance with configured access to the config server replica set.