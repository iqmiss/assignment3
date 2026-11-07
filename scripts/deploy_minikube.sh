#!/bin/sh
# Manual CD to Minikube from your own machine (no registry needed):
#   minikube start
#   sh scripts/deploy_minikube.sh
set -eu
TAG="hode:$(git rev-parse --short HEAD)"
docker build --target runtime -t "$TAG" .
minikube image load "$TAG"
kubectl apply -f k8s/namespace.yaml
kubectl -n hode delete job hode-analysis --ignore-not-found
sed "s|IMAGE_PLACEHOLDER|$TAG|" k8s/job.yaml | kubectl apply -f -
kubectl -n hode wait --for=condition=complete job/hode-analysis --timeout=600s
kubectl -n hode get jobs,pods
kubectl -n hode logs job/hode-analysis | tail -n 20
