# Hayabusa2
Distributed Search Engine for Massive System Log Dataset

# Concept
- Distributed version of standalone Hayabusa(https://github.com/hirolovesbeer/hayabusa)
- Use Network Filesystem(NFS) for Large log storage
- Implement Request Broker for distributed workers
- Worker(nodes/processes) scale architecture
- WebUI

# Architecture
- WebUI
- RequestBroker
- Worker nodes
- NFS(Network File System)
- LogWriter
- Monitoring(Zabbix)

- Architecture Image
![Distributed Hayabusa Architecture](./images/distributed-hayabusa-with-NFS-arch.png "distributed hayabusa architecture image")

# WebUI Image

# Setup
## Provisioning with Ansible
