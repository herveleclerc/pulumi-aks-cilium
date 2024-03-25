# UP

## Cluster

```bash
pulumi up 
```

## kubeconfig

```bash
for i in ne we fc 
do
  az aks get-credentials -n k8s-cluster-$i -g k8s-cluster-$i -f config
done
```

## Cilium

```bash

cilium install --set cluster.name=k8s-cluster-ne \
--set cluster.id=1 \
--set azure.resourceGroup=k8s-cluster-ne \
--set ipam.operator.clusterPoolIPv4PodCIDRList='{10.0.4.0/22}' \
--context k8s-cluster-ne


kubectl get secret -n kube-system cilium-ca -o yaml --context k8s-cluster-ne | kubectl neat > cilium-ca.yaml 


cilium install --set cluster.name=k8s-cluster-we \
--set cluster.id=2 \
--set azure.resourceGroup=k8s-cluster-we \
--set ipam.operator.clusterPoolIPv4PodCIDRList='{10.0.20.0/22}' \
--context k8s-cluster-we

kubectl apply -f cilium-ca.yaml -n kube-system --context k8s-cluster-we


cilium install --set cluster.name=k8s-cluster-fc \
--set cluster.id=3 \
--set azure.resourceGroup=k8s-cluster-fc \
--set ipam.operator.clusterPoolIPv4PodCIDRList='{10.0.36.0/22}' \
--context k8s-cluster-fc


kubectl apply -f cilium-ca.yaml -n kube-system --context k8s-cluster-fc

for i in ne we fc 
do
  cilium status --context k8s-cluster-$i
done

```

## Clustermesh

```bash

for i in ne we fc 
do
  cilium clustermesh enable --context k8s-cluster-$i

done

cilium clustermesh connect --context k8s-cluster-we --destination-context k8s-cluster-ne
cilium clustermesh connect --context k8s-cluster-we --destination-context k8s-cluster-fc
cilium clustermesh connect --context k8s-cluster-ne --destination-context k8s-cluster-fc

cilium connectivity test  --context k8s-cluster-ne --multi-cluster k8s-cluster-fc
cilium connectivity test  --context k8s-cluster-ne --multi-cluster k8s-cluster-we
cilium connectivity test  --context k8s-cluster-we --multi-cluster k8s-cluster-fc

for i in ne we fc 
do
  cilium clustermesh status --context k8s-cluster-$i
  
done

```
## Application

```bash
kubectl apply -f https://raw.githubusercontent.com/cilium/cilium/1.15.1/examples/kubernetes/clustermesh/global-service-example/cluster1.yaml --context k8s-cluster-ne
kubectl apply -f https://raw.githubusercontent.com/cilium/cilium/1.15.1/examples/kubernetes/clustermesh/global-service-example/cluster2.yaml --context k8s-cluster-we

```

## tests 

Sur le cluster k8s-cluster-ne

```bash
for i in {1..10} 
do
kubectl exec -ti deployment/x-wing --context k8s-cluster-ne -- curl rebel-base
done

```


