# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import time

from libcloud.common.dimensiondata import DimensionDataServerCpuSpecification

from plumbery.polisher import PlumberyPolisher
from plumbery.nodes import PlumberyNodes


class ConfigurePolisher(PlumberyPolisher):
    """
    Finalizes the setup of fittings

    This polisher looks at each node in sequence, and adjust settings
    according to fittings plan. This is covering various features that
    can not be set during the creation of nodes, such as:
    - number of CPU
    - quantity of RAM
    - monitoring

    """

    def move_to(self, facility):
        """
        Moves to another API endpoint

        :param facility: access to local parameters and functions
        :type facility: :class:`plumbery.PlumberyFacility`


        """

        self.facility = facility
        self.region = facility.region
        self.nodes = PlumberyNodes(facility)

    def shine_container(self, container):
        """
        prepares a container until it shines

        :param container: the container to be polished
        :type container: :class:`plumbery.PlumberyInfrastructure`

        This is where the hard work is done. You have to override this
        function in your own polisher. Note that you can compare the reality
        versus the theoritical settings if you want.

        """

        logging.info("Configuring blueprint '{}'".format(
            container.blueprint['target']))

        if container.network is None:
            logging.info("- aborted - no network here")
            return

        logging.info("- waiting for nodes to be deployed")

        names = self.nodes.list_nodes(container.blueprint)
        for name in names:
            while True:
                node = self.nodes.get_node(name)
                if node is None:
                    logging.info("- aborted - missing node '{}'".format(name))
                    return

                if node.extra['status'].action is None:
                    break

                if (node is not None
                        and node.extra['status'].failure_reason is not None):

                    logging.info("- aborted - failed deployment "
                                 "of node '{}'".format(name))
                    return

                time.sleep(20)

        logging.info("- nodes have been deployed")

        container._build_firewall_rules()

        container._build_balancer()

    def set_node_compute(self, node, cpu, memory):
        """
        Sets compute capability

        :param node: the node to be polished
        :type node: :class:`libcloud.compute.base.Node`

        :param cpu: the cpu specification
        :type cpu: ``DimensionDataServerCpuSpecification``

        :param memory: the memory size, expressed in Giga bytes
        :type memory: ``int``

        """

        changed = False

        if cpu is not None and 'cpu' in node.extra:

            if int(cpu.cpu_count) != int(node.extra['cpu'].cpu_count):
                logging.info("- changing to {} cpu".format(
                    cpu.cpu_count))
                changed = True

            if int(cpu.cores_per_socket) != int(node.extra['cpu'].cores_per_socket):
                logging.info("- changing to {} core(s) per socket".format(
                    cpu.cores_per_socket))
                changed = True

            if cpu.performance != node.extra['cpu'].performance:
                logging.info("- changing to '{}' cpu performance".format(
                    cpu.performance.lower()))
                changed = True

        if memory is not None and 'memoryMb' in node.extra:

            if memory != int(node.extra['memoryMb']/1024):
                logging.info("- changing to {} GB memory".format(
                    memory))
                changed = True

        if not changed:
            logging.debug("- no change in compute")
            return

        if self.engine.safeMode:
            logging.info("- skipped - safe mode")
            return

        while True:
            try:
                self.region.ex_reconfigure_node(
                    node=node,
                    memory_gb=memory,
                    cpu_count=cpu.cpu_count,
                    cores_per_socket=cpu.cores_per_socket,
                    cpu_performance=cpu.performance)

                logging.info("- in progress")

            except Exception as feedback:
                if 'RESOURCE_BUSY' in str(feedback):
                    time.sleep(10)
                    continue

                if 'Please try again later' in str(feedback):
                    time.sleep(10)
                    continue

                logging.info("- unable to reconfigure node")
                logging.error(str(feedback))

            break

    def change_node_disk_size(self, node, id, size):
        """
        Changes an existing virtual disk

        :param node: the node to be polished
        :type node: :class:`libcloud.compute.base.Node`

        :param id: the disk unique identifier, as reported by the API
        :type id: ``str``

        :param size: the disk size, expressed in Giga bytes
        :type size: ``int``

        """

        if self.engine.safeMode:
            logging.info("- skipped - safe mode")
            return

        while True:
            try:
                self.region.ex_change_storage_size(
                    node=node,
                    disk_id=id,
                    size=size)

                logging.info("- in progress")

            except Exception as feedback:
                if 'RESOURCE_BUSY' in str(feedback):
                    time.sleep(10)
                    continue

                if 'Please try again later' in str(feedback):
                    time.sleep(10)
                    continue

                logging.info("- unable to change disk size to {}GB"
                             .format(size))
                logging.error(str(feedback))

            break

    def change_node_disk_speed(self, node, id, speed):
        """
        Changes an existing virtual disk

        :param node: the node to be polished
        :type node: :class:`libcloud.compute.base.Node`

        :param id: the disk unique identifier, as reported by the API
        :type id: ``str``

        :param speed: storage type, either 'standard',
            'highperformance' or 'economy'
        :type speed: ``str``

        """

        if self.engine.safeMode:
            logging.info("- skipped - safe mode")
            return

        while True:
            try:
                self.region.ex_change_storage_speed(
                    node=node,
                    disk_id=id,
                    speed=speed)

                logging.info("- in progress")

            except Exception as feedback:
                if 'RESOURCE_BUSY' in str(feedback):
                    time.sleep(10)
                    continue

                if 'Please try again later' in str(feedback):
                    time.sleep(10)
                    continue

                logging.info("- unable to change disk to '{}'"
                             .format(speed))
                logging.error(str(feedback))

            break

    def set_node_disk(self, node, id, size, speed='standard'):
        """
        Sets a virtual disk

        :param node: the node to be polished
        :type node: :class:`libcloud.compute.base.Node`

        :param id: the disk id, starting at 0 and growing
        :type id: ``int``

        :param size: the disk size, expressed in Giga bytes
        :type size: ``int``

        :param speed: storage type, either 'standard',
            'highperformance' or 'economy'
        :type speed: ``str``

        """

        if size < 1:
            logging.info("- minimum disk size is 1 GB")
            return

        if size > 1000:
            logging.info("- disk size cannot exceed 1000 GB")
            return

        if speed not in ['standard', 'highperformance', 'economy']:
            logging.info("- disk speed should be either 'standard' "
                         "or 'highperformance' or 'economy'")
            return

        if 'disks' in node.extra:
            for disk in node.extra['disks']:
                if disk['scsiId'] == id:
                    changed = False

                    if disk['size'] > size:
                        logging.info("- disk shrinking could break the node")
                        logging.info("- skipped - disk {} will not be reduced"
                                     .format(id))

                    if disk['size'] < size:
                        logging.info("- expanding disk {} to {} GB"
                                     .format(id, size))
                        self.change_node_disk_size(node, disk['id'], size)
                        changed = True

                    if disk['speed'].lower() != speed.lower():
                        logging.info("- changing disk {} to '{}'"
                                     .format(id, speed))
                        self.change_node_disk_speed(node, disk['id'], speed)
                        changed = True

                    if not changed:
                        logging.debug("- no change in disk {}".format(id))

                    return

        logging.info("- adding {} GB '{}' disk".format(
            size, speed))

        if self.engine.safeMode:
            logging.info("- skipped - safe mode")
            return

        while True:
            try:
                self.region.ex_add_storage_to_node(
                    node=node,
                    amount=size,
                    speed=speed.upper())

                logging.info("- in progress")

            except Exception as feedback:
                if 'RESOURCE_BUSY' in str(feedback):
                    time.sleep(10)
                    continue

                if 'Please try again later' in str(feedback):
                    time.sleep(10)
                    continue

                logging.info("- unable to add disk {} GB '{}'"
                             .format(size, speed))
                logging.error(str(feedback))

            break

    def shine_node(self, node, settings, container):
        """
        Finalizes setup of one node

        :param node: the node to be polished
        :type node: :class:`libcloud.compute.base.Node`

        :param settings: the fittings plan for this node
        :type settings: ``dict``

        :param container: the container of this node
        :type container: :class:`plumbery.PlumberyInfrastructure`

        """

        logging.info("Configuring node '{}'".format(settings['name']))
        if node is None:
            logging.info("- not found")
            return

        cpu = None
        if 'cpu' in settings:
            tokens = str(settings['cpu']).split(' ')
            if len(tokens) < 2:
                tokens.append('1')
            if len(tokens) < 3:
                tokens.append('standard')

            if (int(tokens[0]) < 1
                    or int(tokens[0]) > 32):

                logging.info("- cpu should be between 1 and 32")

            elif (int(tokens[1]) < 1
                    or int(tokens[1]) > 2):

                logging.info("- core per cpu should be either 1 or 2")

            elif tokens[2].upper() not in ('STANDARD',
                                           'HIGHPERFORMANCE'):

                logging.info("- cpu speed should be either 'standard'"
                             " or 'highspeed'")

            else:
                logging.debug("- setting compute {}".format(' '.join(tokens)))
                cpu = DimensionDataServerCpuSpecification(
                    cpu_count=tokens[0],
                    cores_per_socket=tokens[1],
                    performance=tokens[2].upper())

        memory = None
        if 'memory' in settings:
            memory = int(settings['memory'])
            if memory < 1 or memory > 256:
                logging.info("- memory should be between 1 and 256")
                memory = None
            else:
                logging.debug("- setting {} GB of memory".format(
                    memory))

        self.set_node_compute(node, cpu, memory)

        if 'disks' in settings:
            for item in settings['disks']:
                logging.debug("- setting disk {}".format(item))
                attributes = item.split()
                if len(attributes) < 2:
                    logging.info("- malformed disk attributes;"
                                 " provide disk id and size in GB, e.g., 1 50;"
                                 " add disk type if needed, e.g., economy")
                elif len(attributes) < 3:
                    id = int(attributes[0])
                    size = int(attributes[1])
                    speed = 'standard'
                else:
                    id = int(attributes[0])
                    size = int(attributes[1])
                    speed = attributes[2]

                self.set_node_disk(node, id, size, speed)

        if 'monitoring' in settings:
            self.nodes._start_monitoring(node, settings['monitoring'])

        if 'backup' in settings:
            self.nodes._configure_backup(node, settings['backup'])

        if 'glue' in settings:
            container._attach_node(node, settings['glue'])

        container._add_to_pool(node)
