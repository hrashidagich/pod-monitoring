### Steps to Deploy

1. **Containerize Your Application**: Build a Docker image using the Dockerfile and push it to your Docker registry.

   ```bash
   docker build -t your-docker-registry/pod-monitor:latest .
   docker push your-docker-registry/pod-monitor:latest
   ```
2. **Apply Manifests**: Apply the Kubernetes manifests to your cluster.
   ```bash
    kubectl apply -f pod-monitor-sa.yaml
    kubectl apply -f pod-monitor-deployment.yaml
    # Apply ConfigMap if necessary
   ```
3. **Verify Deployment**: Check the deployment status and logs to ensure everything is running smoothly.
   ```bash
    kubectl get deployments
    kubectl logs -f deployment/pod-monitor
   ```
    Replace your-docker-registry/pod-monitor:latest with the actual path to your Docker image and adjust any configurations as necessary for your environment.