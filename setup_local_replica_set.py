""" This script deploys mongodb cluster for illustration purposes.

    * Cluster is deployed on 3 Zero-os containers.
    * Each container runs a shard of a shard server replica set and a shard of config server replica set.
    * Cluster can be reached by communicating with a mongos instance, with configured access to the config server replica set

"""

import os
import sys
import time

from js9 import j

# set up parameters
CONTAINER_TEMPLATE_UID = 'github.com/zero-os/0-templates/container/0.0.1'
# IP of zos node
IP = '192.168.122.89'
DATA_DIR = '/mnt/data/db/'
CONFIG_DIR = '/mnt/data/configdb/'
PATH_CONFIG_CONFSERVER = '/etc/confserv'
PATH_CONFIG_SHARDS = '/etc/shardserv'
NODE_REF = 'local'
PORT_CONF_SERV = 27018
PORT_SHARDS = 27019

# flist used to run mongo containers from
FLIST = 'https://hub.gig.tech/ekaterina_evdokimova_1/ubuntu-16.04-mongodb.flist'
NAME_REPLICA_SET = 'shard-replica-set'
NAME_CONF_REPLICA_SET = 'config-replica'

# number of shards, cannot be even
shard_nr = 3
if not shard_nr % 2:
    raise ValueError('number of shards cannot be even')

def get_robot(ip):
    """ Get robot instance
    
    :param ip: IP addres of Zero-os node
    """    
    url = "http://{}:6600".format(ip)
    zrobot_instance = "zos_local"                         
    j.clients.zrobot.get(
            instance=zrobot_instance,
            data= {
                'url': url,
                'jwt_': j.clients.itsyouonline.get(instance='main').jwt_get(refreshable=True),
            }
        )
    robot = j.clients.zrobot.robots[zrobot_instance]
    # wait for robot if not running

    return robot

def get_node(ip):
    """ Get robot instance
    
    :param ip: IP addres of Zero-os node
    """
    node_id = NODE_REF
    j.clients.zos.get(
            instance=node_id,
            data={
                    "host": ip,
                    "port": 6379,
                    }
            )
    j.clients.zero_os.sal.get_node(instance=NODE_REF)
    return j.clients.zos.sal.get_node(node_id)    

def get_container(robot, node, name, flist):
    """ Create container and mount persistent volume

    :param robot: robot instance
    :param node: Zero-os node object
    :param flist: url of flist that will be user to run container
    """
    sp = node.storagepools.get('zos-cache')
    try:
        fs = sp.get(name)
    except ValueError:
        fs = sp.create(name)
    node_fs = node.client.filesystem
    vol = os.path.join(fs.path, DATA_DIR)
    node_fs.mkdir(vol)

    vol_config = os.path.join(fs.path, CONFIG_DIR)
    node_fs.mkdir(vol_config)

    mounts = [
        {
            'source': vol,
            'target': "{}_{}".format(DATA_DIR,name)
        },
        {
            'source': vol_config,
            'target': "{}_{}".format(CONFIG_DIR,name)
        },
    ]

    # determine parent interface for macvlan
    candidates = list()
    for route in node.client.ip.route.list():
        if route['gw']:
            candidates.append(route)
    if not candidates:
        raise RuntimeError("Could not find interface for macvlan parent")
    elif len(candidates) > 1:
        raise RuntimeError("Found multiple eligible interfaces for macvlan parent: %s" % ", ".join(c['dev'] for c in candidates))
    parent_if = candidates[0]['dev']

    container_data = {
        'flist': flist,
        'node': NODE_REF,
        'nics': [{'type': 'macvlan', 'id': parent_if, 'name': 'stoffel', 'config': { 'dhcp': True }}],
        'mounts': mounts
    }

    return robot.services.find_or_create(CONTAINER_TEMPLATE_UID, name, data=container_data)


def error_check(result, message=''):
    """ Raise error if call wasn't successfull """

    if result.state != 'SUCCESS':
        err = '{}: {} \n {}'.format(message, result.stderr, result.data)
        raise RuntimeError(err)


# get robot running on the node with given ip
robot = get_robot(IP)

# start containers
container_services = {}
node = get_node(IP)
for n in range(shard_nr):
    service_name = 'shard_{}'.format(n)
    container_service = get_container(robot=robot, node=node, name=service_name, flist=FLIST)
    container_service.schedule_action('install').wait(die=True)
    container_services[service_name] = container_service

# start DBs with mongod in each container
containers = []
addrs = []
for container in node.containers.list():
    if container.name in container_services:
        # wait for container to respond, get ip of container
        start = time.time()
        while time.time() <  start + 100:
            try:
                container.default_ip()
                break
            except LookupError:
                time.sleep(1)
        else:
            raise LookupError
        containers.append(container)
        addrs.append(container.default_ip().ip.format())

# configure replica set with mongo
for idx, container in enumerate(containers):
    # create directory
    container.client.filesystem.mkdir(DATA_DIR)

    # run mongod instance
    cmd = "mongod --shardsvr --replSet {} --dbpath {}  --bind_ip localhost,{} --port {} --logpath /tmp/shard".format(
        NAME_REPLICA_SET, DATA_DIR, addrs[idx], PORT_SHARDS)
    container.client.system(cmd)    

    # run config server
    container.client.filesystem.mkdir(CONFIG_DIR)
    cmd = 'mongod --configsvr --replSet {name} --dbpath {dir} --bind_ip localhost,{addr} --port {port} --logpath /tmp/conf'.format(
        name=NAME_CONF_REPLICA_SET, dir=CONFIG_DIR,  addr=addrs[idx], port=PORT_CONF_SERV)
    container.client.system(cmd)

# initialize config server replica set
container = containers[0]
confserv_conf = """
rs.initiate( 
    {_id : '%s',
    members: [
        { _id: 0, host: '%s:%s' },
        { _id: 1, host: '%s:%s' },
        { _id: 2, host: '%s:%s' },
      ]
    }
)
"""% ( NAME_CONF_REPLICA_SET, addrs[0], PORT_CONF_SERV, addrs[1], PORT_CONF_SERV, addrs[2], PORT_CONF_SERV)

# create config file to init config server replica set
conf_file = '/tmp/confserv.js'
container.client.filesystem.remove(conf_file)
container.client.bash('echo "%s" >> %s' % (confserv_conf, conf_file)).get()
cmd = 'mongo --port {port} {file}'.format(port=PORT_CONF_SERV, file=conf_file)

# wait for config server to be up and running
start = time.time()
while time.time() < start + 100:
    try:
        result = container.client.system(cmd).get()
        error_check(result)
        break
    except:
        time.sleep(1)
else:
    raise RuntimeError('failed connecting to conf server')

# connect mongo to the shard server
shard_conf = """
rs.initiate( {
   _id : '%s',
   members: [
      { _id: 0, host: '%s:%s' },
      { _id: 1, host: '%s:%s' },
      { _id: 2, host: '%s:%s' }
   ]
})
""" % (NAME_REPLICA_SET, addrs[0], PORT_SHARDS, addrs[1], PORT_SHARDS, addrs[2], PORT_SHARDS)

# create config file to init shard server replica set
conf_file = '/tmp/replserv.js'
container.client.filesystem.remove(conf_file)
container.client.bash('echo "%s" >> %s' % (shard_conf, conf_file)).get()
cmd = 'mongo --port {port} {file}'.format( port=PORT_SHARDS, file=conf_file)
result = container.client.system(cmd).get()
error_check(result)

