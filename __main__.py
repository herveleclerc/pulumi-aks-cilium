import pulumi
import pulumi_azure_native as azure_native
from   pulumi_azure_native import containerservice, resources, authorization
import base64

"""Creates a new Azure resource group.

Args:
    resource_group_name (str): The name of the resource group.
    location (str): The location of the resource group.

Returns:
    ResourceGroup: A new ResourceGroup object.
"""
def create_resource_group(resource_group_name, location):
    return azure_native.resources.ResourceGroup(resource_group_name,
                                                resource_group_name=resource_group_name,
                                                location=location)

"""Creates a new Azure virtual network.

Args:
    resource_group (ResourceGroup): The resource group to create the virtual network in.
    vnet_name (str): The name of the virtual network.
    address_prefixes (list[str]): The address prefixes (CIDR blocks) for the virtual network.

Returns:
    VirtualNetwork: The new VirtualNetwork object.
"""
def create_virtual_network(resource_group, vnet_name, address_prefixes):
    return azure_native.network.VirtualNetwork(vnet_name,
                                              resource_group_name=resource_group.name,
                                              virtual_network_name=vnet_name,
                                              location=resource_group.location,
                                              address_space=azure_native.network.AddressSpaceArgs(
                                                  address_prefixes=address_prefixes,
                                              ))

"""Creates a new Azure subnet.

Args:
    resource_group (ResourceGroup): The resource group to create the subnet in. 
    virtual_network (VirtualNetwork): The virtual network to create the subnet in.
    subnet_name (str): The name of the subnet.
    address_prefix (str): The address prefix (CIDR block) for the subnet.

Returns:
    Subnet: The new Subnet object.
"""
def create_subnet(resource_group, virtual_network, subnet_name, address_prefix):
    return azure_native.network.Subnet(subnet_name,
                                       address_prefix=address_prefix,
                                       resource_group_name=resource_group.name,
                                       virtual_network_name=virtual_network.name,
                                       subnet_name=subnet_name)

"""Creates a new virtual network peering between two virtual networks.

Args:
    resource_group1 (ResourceGroup): The resource group for the first virtual network.
    virtual_network1 (VirtualNetwork): The first virtual network to peer.
    resource_group2 (ResourceGroup): The resource group for the second virtual network. 
    virtual_network2 (VirtualNetwork): The second virtual network to peer.
    vnet_peering_name (str): The name for the virtual network peering.

Returns:
    VirtualNetworkPeering: The new VirtualNetworkPeering object.
"""
def create_vnet_peering(resource_group1, virtual_network1, resource_group2, virtual_network2, vnet_peering_name):
    return azure_native.network.VirtualNetworkPeering(vnet_peering_name,
                                                     resource_group_name=resource_group1.name,
                                                     virtual_network_name=virtual_network1.name,
                                                     virtual_network_peering_name=vnet_peering_name,
                                                     remote_virtual_network=azure_native.network.SubResourceArgs(id=virtual_network2.id,),
                                                     allow_virtual_network_access=True,
                                                     allow_forwarded_traffic=True,
                                                     opts=pulumi.ResourceOptions(depends_on=[virtual_network1, virtual_network2]),
                                                     )

def create_k8s_cluster(resource_group, k8s_cluster_name, subnet_node_id, service_cidr, dns_service_ip, pod_cidr):
    return azure_native.containerservice.ManagedCluster(
        k8s_cluster_name,
        resource_name_=k8s_cluster_name,
        resource_group_name=resource_group.name,
        location=resource_group.location,
        node_resource_group=f"{k8s_cluster_name}-vm",
        agent_pool_profiles=[{
            "count": 1,
            "max_pods": 250,
            "mode": "System",
            "name": "main",
            "node_labels": {"location": resource_group.location},
            "os_disk_size_gb": 30,
            "os_type": "Linux",
            "type": "VirtualMachineScaleSets",
            "vm_size": "Standard_B2s",
            "vnet_subnet_id": subnet_node_id
        }],
        dns_prefix='k8s-ne',
        enable_rbac=True,
        identity=azure_native.containerservice.ManagedClusterIdentityArgs(
            type="SystemAssigned",
        ),
        kubernetes_version='1.27.7',
        network_profile=azure_native.containerservice.ContainerServiceNetworkProfileArgs(
            network_plugin='none',
            pod_cidr=pod_cidr,
            service_cidr=service_cidr,
            dns_service_ip=dns_service_ip
        ),
    )

"""Creates Azure role assignments to grant the AKS managed identity access to the node resource group and cluster resource group.

Args:
  cluster_name (str): The name of the AKS cluster.
  resource_group_name (ResourceGroup): The resource group of the AKS cluster.
  cluster (ManagedCluster): The AKS managed cluster.
  
Returns:
  Tuple[RoleAssignment, RoleAssignment]: The two role assignments granting access.
"""
def create_role_assignments(cluster_name, resource_group_name, cluster):
    role_assignment_1 = authorization.RoleAssignment(
        f'role_assignment-aks-{cluster_name}',
        scope=f'/subscriptions/{config.subscription_id}/resourceGroups/{cluster_name}-vm',
        role_definition_id=f'/subscriptions/{config.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/4d97b98b-1d4f-4787-a291-c67834d212e7'.format(
            subscriptionId=cluster.id.apply(lambda id: id.split('/')[2])),
        principal_id=cluster.identity.apply(lambda i: i.principal_id),
        principal_type='ServicePrincipal'
    )

    role_assignment_2 = authorization.RoleAssignment(
        f'role_assignment-aks-{cluster_name}-2',
        scope=resource_group_name.id,
        role_definition_id=f'/subscriptions/{config.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/4d97b98b-1d4f-4787-a291-c67834d212e7'.format(
            subscriptionId=cluster.id.apply(lambda id: id.split('/')[2])),
        principal_id=cluster.identity.apply(lambda i: i.principal_id),
        principal_type='ServicePrincipal'
    )

    return role_assignment_1, role_assignment_2

    

"""Gets Kubernetes credentials for a managed AKS cluster.

Args:
  resource_group: The resource group of the AKS cluster.
  k8s_cluster: The AKS managed cluster.
  
Returns: 
  The Kubernetes config file contents.
"""
def get_k8s_credentials(resource_group, k8s_cluster):
    creds = containerservice.list_managed_cluster_user_credentials_output(
        resource_group_name=resource_group.name,
        resource_name=k8s_cluster.name)

    encoded = creds.kubeconfigs[0].value
    kubeconfig = encoded.apply(
        lambda enc: base64.b64decode(enc).decode())
    return kubeconfig

config = authorization.get_client_config()

"""
regions: A dictionary containing configuration details for Kubernetes clusters in different Azure regions.

Each region contains the following details:
- rg_name: Resource group name 
- location: Azure region location
- address_prefixes: Address prefixes for the VNet
- vnet_name: Name of the VNet
- subnet_node_name: Name of the node subnet 
- subnet_node_address_prefix: Address prefix for the node subnet
- subnet_pod_address_prefix: Address prefix for the pod subnet
- pod_cidr: CIDR range for pod IPs
- service_cidr: CIDR range for service IPs  
- dns_service_ip: IP address for DNS service
- k8s_cluster_name: Name of the Kubernetes cluster

This provides the configuration needed to deploy Kubernetes clusters in different regions with appropriate networking.
"""
regions = {
    "northeurope": {
        "rg_name": "rg-aks-northeurope",
        "location": "northeurope",
        "address_prefixes": ["10.0.0.0/20"],
        "vnet_name": "vnet-ne",
        "subnet_node_name": "node-subnet-ne",
        "subnet_node_address_prefix": "10.0.0.0/23",
        "subnet_pod_address_prefix": "10.0.4.0/22",
        "pod_cidr": "198.170.0.0/16",
        "service_cidr": "192.172.0.0/16",
        "dns_service_ip": "192.172.0.53",
        "k8s_cluster_name": "k8s-cluster-ne",
    },
    "westeurope": {
        "rg_name": "rg-aks-westeurope",
        "location": "westeurope",
        "address_prefixes": ["10.0.16.0/20"],
        "vnet_name": "vnet-we",
        "subnet_node_name": "node-subnet-we",
        "subnet_node_address_prefix": "10.0.16.0/23",
        "subnet_pod_address_prefix": "10.0.20.0/22",
        "pod_cidr": "198.174.0.0/16",
        "service_cidr": "192.176.0.0/16",
        "dns_service_ip": "192.176.0.53",
        "k8s_cluster_name": "k8s-cluster-we",
    },
    "francecentral": {
        "rg_name": "rg-aks-francecentral",
        "location": "francecentral",
        "address_prefixes": ["10.0.32.0/20"],
        "vnet_name": "vnet-fc",
        "subnet_node_name": "node-subnet-fc",
        "subnet_node_address_prefix": "10.0.32.0/23",
        "subnet_pod_address_prefix": "10.0.36.0/22",
        "pod_cidr": "198.178.0.0/16",
        "service_cidr": "192.180.0.0/16",
        "dns_service_ip": "192.180.0.53",
        "k8s_cluster_name": "k8s-cluster-fc",
    }
}

"""
vnet_peerings: Dictionary mapping region pairs to the peering names for connecting them.
    The keys are tuples of (region1, region2) and values are tuples 
    (peering1_name, peering2_name). This allows creating bidirectional 
    peerings between regions.
"""
vnet_peerings = {
    ("northeurope", "westeurope"): ("vnet-peering-ne-we", "vnet-peering-we-ne"),
    ("northeurope", "francecentral"): ("vnet-peering-ne-fc", "vnet-peering-fc-ne"),
    ("westeurope", "francecentral"): ("vnet-peering-we-fc", "vnet-peering-fc-we"),
}

"""
Create Azure resource groups, virtual networks, and subnets for each region.

The resource groups, virtual networks, and node subnets are created by looping through 
the regions dictionary and calling the respective Azure resource creation functions. The
names and properties for each resource are populated from the per-region dictionaries.
"""
resource_groups = {region: create_resource_group(regions[region]["rg_name"], regions[region]["location"]) for region in regions}
virtual_networks = {region: create_virtual_network(resource_groups[region], regions[region]["vnet_name"], regions[region]["address_prefixes"]) for region in regions}
subnet_nodes = {region: create_subnet(resource_groups[region], virtual_networks[region], regions[region]["subnet_node_name"], regions[region]["subnet_node_address_prefix"]) for region in regions}

"""
Create VNet peerings between regions. 

Loops through the vnet_peerings dictionary to create bidirectional VNet 
peerings between each region pair using the provided peering names.

Create Kubernetes clusters in each region.

Loops through the regions to create a Kubernetes cluster in each region's 
resource group, subnet, and other configured networking settings. 

Create role assignments to grant access to clusters.

Loops through regions to create role assignments granting access to the
cluster for the current user/service principal.

Get kubeconfig files for each cluster.

Loops through regions to download the kubeconfig files for accessing
each cluster.
"""
for (region1, region2), (peering_name1, peering_name2) in vnet_peerings.items():
    vnet_peering1 = create_vnet_peering(resource_groups[region1], virtual_networks[region1], resource_groups[region2], virtual_networks[region2], peering_name1)
    vnet_peering2 = create_vnet_peering(resource_groups[region2], virtual_networks[region2], resource_groups[region1], virtual_networks[region1], peering_name2)

k8s_clusters = {region: create_k8s_cluster(resource_groups[region], regions[region]["k8s_cluster_name"], subnet_nodes[region].id, regions[region]["service_cidr"], regions[region]["dns_service_ip"], regions[region]["pod_cidr"]) for region in regions}
role_assignments = {region: create_role_assignments(regions[region]["k8s_cluster_name"], resource_groups[region], k8s_clusters[region]) for region in regions}
kubeconfigs = {region: get_k8s_credentials(resource_groups[region], k8s_clusters[region]) for region in regions}

"""
Exports output values for use by other services:

- subnet_node_ids: Map of subnet ids for each region's node subnet 
- virtual_network_ids: Map of virtual network ids for each region
- vnet_peering_states: Map of peering states for each vnet peering
- kubeconfigs: Map of kubeconfig files for accessing each cluster

"""
pulumi.export('subnet_node_ids', {region: subnet_nodes[region].id for region in regions})
pulumi.export('virtual_network_ids', {region: virtual_networks[region].id for region in regions})
pulumi.export('vnet_peering_states', {f"{region1}_{region2}": (vnet_peering1.peering_state, vnet_peering2.peering_state) for (region1, region2), (peering_name1, peering_name2) in vnet_peerings.items()})
pulumi.export('kubeconfigs', kubeconfigs)
