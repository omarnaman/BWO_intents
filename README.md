# BWO: A bandwidth optimization service for IBNs
An service for optimizing the utilization of bandwidth in Software Defined Networks (SDNs) that use Intent Based Networking (IBN)

# Contributors
* Jane Wen (@janenxiao)
* Omar Naman (@omarnaman)

# Getting Started
* Start off by changing the value of `BASE_URL` in `utilClasses.py` to match the address of the ONOS controller.
* Describe the topology to be deployed in the file `g.gragh`, where each line represents a single edge/link in the topology
  *  `Source` `Destination` `Link_Capacity`
  *  If the `Source` starts with `h`, the node is considered a host; e.g. `h1`, `h20`
* Deploy the topology by running `sudo ./mntopo.py`, the script creates a Mininet network from the topology described in `g.graph`, and connects the switches to the ONOS controller deployed locally `localhost`.
* Due to ONOS not discovering the hosts until they generate some traffic, running the `pingall` command in Mininet is advised.
* Run the main script `./intentapp.py` to start BWO.

## BWO Commands
BWO currently supports four types of commands:
1. Adding Intents: `add {src_host} {dst_host} {Demand}`
2. Listing Intents: `(list | ls)`
3. Removing intents: `(rm | remove | delete) ({Intent ID} | all)`
4. Exiting BWO: `exit`


