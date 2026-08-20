#!/usr/bin/env bash
# Scale Neo4j down, dump the data PVC with the live image, upload to S3, scale back.
# Must run in a pod that does NOT mount the Neo4j PVC (RWO deadlock).
set -euo pipefail

NS="${NAMESPACE:?NAMESPACE is required}"
STS="${STATEFULSET_NAME:?STATEFULSET_NAME is required}"
PVC="${PVC_NAME:?PVC_NAME is required}"
BUCKET="${S3_BUCKET:?S3_BUCKET is required}"
PREFIX="${S3_PREFIX:?S3_PREFIX is required}"
REGION="${AWS_REGION:?AWS_REGION is required}"
AWS_CLI_IMAGE="${AWS_CLI_IMAGE:?AWS_CLI_IMAGE is required}"
TIMEOUT="${DUMP_TIMEOUT_SECONDS:-1200}"
CLUSTER="${CLUSTER_NAME:-cluster}"
SA="${SERVICE_ACCOUNT:-opensre-neo4j-backup}"

POD="${STS}-0"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP_JOB="opensre-neo4j-dump-${STAMP}"
KEY="${PREFIX}${CLUSTER}/${STAMP}.dump"

# Bring Neo4j back. Delete the dump Job first so it releases the RWO PVC.
# Scale and rollout must not be masked with || true — a downed STS is a failed backup.
scale_up() {
  echo "$(date -Is) scaling ${STS} to 1"
  # Always attempt scale even if Job cleanup fails; rollout then reports PVC/STS errors.
  kubectl -n "$NS" delete job "$DUMP_JOB" --ignore-not-found || true
  # Wait until dump pods are gone (none matching means the volume is already free).
  if kubectl -n "$NS" get pods -l "job-name=${DUMP_JOB}" -o name 2>/dev/null | grep -q .; then
    kubectl -n "$NS" wait --for=delete pod -l "job-name=${DUMP_JOB}" --timeout=180s || true
  fi
  kubectl -n "$NS" scale "sts/${STS}" --replicas=1
  kubectl -n "$NS" rollout status "sts/${STS}" --timeout=180s
}

# Always attempt scale-up, including on dump failure. Exit non-zero if the
# original command failed or Neo4j did not come back.
cleanup() {
  orig_exit=$?
  trap - EXIT
  scale_exit=0
  scale_up || scale_exit=$?
  if [ "$orig_exit" -ne 0 ]; then
    exit "$orig_exit"
  fi
  if [ "$scale_exit" -ne 0 ]; then
    exit "$scale_exit"
  fi
}
trap cleanup EXIT

echo "$(date -Is) dump start sts=${STS} pvc=${PVC} key=s3://${BUCKET}/${KEY}"

IMAGE="$(kubectl -n "$NS" get "sts/${STS}" -o jsonpath='{.spec.template.spec.containers[0].image}')"
echo "$(date -Is) using image ${IMAGE}"

kubectl -n "$NS" scale "sts/${STS}" --replicas=0
kubectl -n "$NS" wait --for=delete "pod/${POD}" --timeout=180s || true

# If the pod name differs, wait until the STS reports 0 replicas.
kubectl -n "$NS" wait --for=jsonpath='{.status.replicas}'=0 "sts/${STS}" --timeout=180s || \
  kubectl -n "$NS" wait --for=jsonpath='{.status.currentReplicas}'=0 "sts/${STS}" --timeout=180s || true

cat <<EOF | kubectl -n "$NS" apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: ${DUMP_JOB}
  labels:
    app.kubernetes.io/name: opensre-neo4j-dump
spec:
  ttlSecondsAfterFinished: 86400
  backoffLimit: 0
  activeDeadlineSeconds: ${TIMEOUT}
  template:
    spec:
      restartPolicy: Never
      serviceAccountName: ${SA}
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: ${PVC}
        - name: backups
          emptyDir: {}
      initContainers:
        - name: dump
          image: ${IMAGE}
          imagePullPolicy: IfNotPresent
          command: ["/bin/bash", "-c"]
          args:
            - |
              set -euo pipefail
              mkdir -p /backups
              neo4j-admin database dump neo4j --to-path=/backups --overwrite-destination=true
              ls -lh /backups
          volumeMounts:
            - name: data
              mountPath: /data
            - name: backups
              mountPath: /backups
      containers:
        - name: upload
          image: ${AWS_CLI_IMAGE}
          imagePullPolicy: IfNotPresent
          command: ["/bin/sh", "-c"]
          args:
            - |
              set -euo pipefail
              test -s /backups/neo4j.dump
              aws s3 cp /backups/neo4j.dump "s3://${BUCKET}/${KEY}" --region "${REGION}"
              aws s3 ls "s3://${BUCKET}/${KEY}" --region "${REGION}"
          env:
            - name: AWS_DEFAULT_REGION
              value: "${REGION}"
          volumeMounts:
            - name: backups
              mountPath: /backups
EOF

kubectl -n "$NS" wait --for=condition=complete "job/${DUMP_JOB}" --timeout="${TIMEOUT}s"
echo "$(date -Is) dump complete s3://${BUCKET}/${KEY}"
