// CI/CD pipeline for HODE (Assignment 5).
//
// On every commit to the repository:
//   1. Checkout        - the exact commit that triggered the build (pollSCM)
//   2. Lint            - ruff (style and common bugs)
//   3. Unit tests      - pytest, JUnit report, coverage gate 80 %
//   4. Build image     - docker build (multi-stage, pinned libraries)
//   5. Smoke test      - run the synthetic sweep inside the image + hode verify
//   6. Push            - optional, to Docker Hub (needs the 'dockerhub' credential)
//   7. Deploy          - optional, Kubernetes Job on Minikube (needs 'kubeconfig')
//
// The server set-up is in jenkins/ (docker compose up -d --build).

pipeline {
    agent any

    parameters {
        string(name: 'IMAGE_REPO', defaultValue: 'iqmiss/hode',
               description: 'Docker Hub repository, <user>/<name>')
        booleanParam(name: 'PUSH_IMAGE', defaultValue: false,
               description: 'Push the image to Docker Hub (credential id: dockerhub)')
        booleanParam(name: 'DEPLOY_K8S', defaultValue: false,
               description: 'Run the analysis as a Kubernetes Job (credential id: kubeconfig)')
    }

    triggers {
        // Check GitHub for new commits every ~2 minutes. If Jenkins is reachable from
        // the internet, a GitHub webhook (githubPush) can replace polling.
        pollSCM('H/2 * * * *')
    }

    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
    }

    environment {
        IMAGE_TAG = "${env.GIT_COMMIT ? env.GIT_COMMIT.substring(0, 7) : env.BUILD_NUMBER}"
        LOCAL_IMAGE = "hode:${IMAGE_TAG}"
        VENV = "${JENKINS_HOME}/venvs/hode-ci"
        PIP_CACHE_DIR = "${JENKINS_HOME}/pip-cache"
    }

    stages {
        stage('Checkout') {
            // Jenkins has already checked out the triggering commit (Declarative: Checkout SCM).
            steps {
                sh 'git log -1 --pretty="commit %h by %an: %s"'
            }
        }

        stage('Set up Python') {
            steps {
                // Venv and pip cache live in jenkins_home, so later builds reuse them;
                // retries and resumable downloads survive short network drops.
                sh '''
                    [ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
                    "$VENV/bin/pip" install --quiet --retries 10 --timeout 60 --upgrade pip
                    "$VENV/bin/pip" install --quiet --retries 10 --timeout 60 --resume-retries 10 \
                        -e ".[dev]"
                    "$VENV/bin/python" --version
                '''
            }
        }

        stage('Lint') {
            steps {
                sh '"$VENV/bin/ruff" check . && "$VENV/bin/ruff" format --check .'
            }
        }

        stage('Unit tests') {
            steps {
                sh '''
                    "$VENV/bin/pytest" --junitxml=reports/junit.xml \
                        --cov --cov-report=term --cov-report=xml:reports/coverage.xml
                '''
            }
            post {
                always {
                    junit allowEmptyResults: false, testResults: 'reports/junit.xml'
                    archiveArtifacts artifacts: 'reports/*.xml', allowEmptyArchive: true
                }
            }
        }

        stage('Build Docker image') {
            steps {
                sh '''
                    docker build --pull --target runtime \
                        --label org.opencontainers.image.revision="$GIT_COMMIT" \
                        -t "$LOCAL_IMAGE" .
                    docker image ls hode
                '''
            }
        }

        stage('Smoke test in container') {
            steps {
                // Default command = hode run configs/synthetic.toml && hode verify
                sh '''
                    docker rm -f "hode-smoke-$BUILD_NUMBER" 2>/dev/null || true
                    docker run --name "hode-smoke-$BUILD_NUMBER" "$LOCAL_IMAGE"
                    mkdir -p results
                    docker cp "hode-smoke-$BUILD_NUMBER:/app/results/." results/
                    docker rm "hode-smoke-$BUILD_NUMBER"
                '''
                archiveArtifacts artifacts: 'results/*', fingerprint: true
            }
        }

        stage('Push to Docker Hub') {
            when {
                allOf {
                    expression { params.PUSH_IMAGE }
                    anyOf { branch 'main'; expression { env.BRANCH_NAME == null } }
                }
            }
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub',
                        usernameVariable: 'DH_USER', passwordVariable: 'DH_TOKEN')]) {
                    sh '''
                        echo "$DH_TOKEN" | docker login -u "$DH_USER" --password-stdin
                        docker tag "$LOCAL_IMAGE" "$IMAGE_REPO:$IMAGE_TAG"
                        docker tag "$LOCAL_IMAGE" "$IMAGE_REPO:latest"
                        docker push "$IMAGE_REPO:$IMAGE_TAG"
                        docker push "$IMAGE_REPO:latest"
                        docker logout
                    '''
                }
            }
        }

        stage('Deploy to Kubernetes (Minikube)') {
            when { expression { params.DEPLOY_K8S && params.PUSH_IMAGE } }
            steps {
                withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
                    sh '''
                        kubectl apply -f k8s/namespace.yaml
                        kubectl -n hode delete job hode-analysis --ignore-not-found
                        sed "s|IMAGE_PLACEHOLDER|$IMAGE_REPO:$IMAGE_TAG|" k8s/job.yaml \
                            | kubectl apply -f -
                        kubectl -n hode wait --for=condition=complete job/hode-analysis \
                            --timeout=600s
                        kubectl -n hode logs job/hode-analysis | tail -n 20
                    '''
                }
            }
        }
    }

    post {
        success { echo "Image ${LOCAL_IMAGE} built, tested and verified." }
        failure { echo 'Pipeline failed: see the stage marked red.' }
        always  { sh 'docker image prune -f >/dev/null 2>&1 || true' }
    }
}
