from kubernetes import client, config, watch
import logging
import time
import os
import smtplib
from email.message import EmailMessage

class K8sPodMonitor:
    def __init__(self):
        config.load_kube_config()
        self.core_api = client.CoreV1Api()
        self.apps_api = client.AppsV1Api()
        self.max_restarts = int(os.getenv('MAX_RESTARTS', 3))
        self.email_alerts = os.getenv('EMAIL_ALERTS', 'False').lower() in ['true', '1', 't']
        self.restart_attempts = {}

    def watch_pods(self):
        w = watch.Watch()
        for event in w.stream(self.core_api.list_pod_for_all_namespaces):
            pod = event['object']
            self.evaluate_pod_status(pod)

    def evaluate_pod_status(self, pod):
        status = pod.status.phase
        if status in ["Failed", "Unknown"]:
            self.handle_failing_pod(pod)
        elif status == "Running":
            self.check_pod_health(pod)

    def handle_failing_pod(self, pod):
        pod_name = pod.metadata.name
        if pod_name not in self.restart_attempts:
            self.restart_attempts[pod_name] = 0

        self.restart_attempts[pod_name] += 1
        if self.restart_attempts[pod_name] <= self.max_restarts:
            logging.info(f"Restarting pod: {pod_name}, Attempt: {self.restart_attempts[pod_name]}")
            self.restart_pod(pod)
        else:
            logging.error(f"Pod {pod_name} failed after maximum restart attempts. Scaling down deployment.")
            self.scale_down_deployment(pod)
            self.send_alert(pod)

    def restart_pod(self, pod):
        try:
            # Fetch the existing pod's configuration
            pod_manifest = self.core_api.read_namespaced_pod(name=pod.metadata.name, namespace=pod.metadata.namespace)

            # Remove certain fields that should not be in the new pod manifest
            pod_manifest.metadata.resource_version = None
            pod_manifest.metadata.uid = None
            pod_manifest.metadata.creation_timestamp = None
            pod_manifest.metadata.self_link = None
            pod_manifest.metadata.namespace = pod.metadata.namespace

            # Delete the existing pod
            self.core_api.delete_namespaced_pod(name=pod.metadata.name, namespace=pod.metadata.namespace)
            logging.info(f"Deleted pod {pod.metadata.name}")

            # Wait for a short period to ensure the pod is fully terminated
            time.sleep(5)

            # Create a new pod with the same configuration
            self.core_api.create_namespaced_pod(namespace=pod.metadata.namespace, body=pod_manifest)
            logging.info(f"Recreated pod {pod.metadata.name}")

        except client.rest.ApiException as e:
            logging.error(f"Failed to restart pod: {e}")

    def scale_down_deployment(self, pod):
        try:
            deployments = self.apps_api.list_namespaced_deployment(pod.metadata.namespace)
            for deployment in deployments.items:
                if pod.metadata.name in deployment.metadata.name:
                    self.apps_api.patch_namespaced_deployment_scale(
                        name=deployment.metadata.name,
                        namespace=pod.metadata.namespace,
                        body={"spec": {"replicas": 0}}
                    )
                    logging.info(f"Scaled down deployment {deployment.metadata.name}")
                    break
        except client.rest.ApiException as e:
            logging.error(f"Error scaling down deployment: {e}")

   def check_pod_health(self, pod):
        for condition in pod.status.conditions:
            if condition.type == 'Ready':
                if condition.status != 'True':
                    logging.warning(f"Pod {pod.metadata.name} is not ready.")
            elif condition.type == 'ContainersReady':
                if condition.status != 'True':
                    logging.warning(f"Containers in pod {pod.metadata.name} are not ready.")

    def send_alert(self, pod):
        if self.email_alerts:
            try:
                msg = EmailMessage()
                msg.set_content(f"Alert: Pod {pod.metadata.name} in namespace {pod.metadata.namespace} is failing.")
                msg['Subject'] = 'Kubernetes Pod Failure Alert'
                msg['From'] = 'pod.monitoring@gmail.com'
                msg['To'] = 'alerting@gmail.com'

                # Replace SMTP details as per your setup
                with smtplib.SMTP('smtp.example.com', 587) as s:
                    s.starttls()
                    s.login('user@example.com', 'password')
                    s.send_message(msg)
                    logging.info(f"Sent email alert for failing pod: {pod.metadata.name}")
            except Exception as e:
                logging.error(f"Failed to send email alert: {e}")


# Main execution
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    monitor = K8sPodMonitor(max_restarts=2, email_alerts=True)
    monitor.watch_pods()