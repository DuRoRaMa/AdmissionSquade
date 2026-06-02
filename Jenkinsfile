pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    triggers {
        pollSCM('H/2 * * * *')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Validate env file') {
            steps {
                sh '''
                    set -e

                    test -f /srv/pk-services/Squad/AdmissionSquade/Admissions_squad/.env

                    echo "Backend .env file exists"
                '''
            }
        }

        stage('Build and deploy backend') {
            steps {
                sh '''
                    set -e

                    docker network inspect pk_proxy >/dev/null 2>&1 || docker network create pk_proxy

                    docker compose -f docker-compose.prod.yml up -d --build
                '''
            }
        }

        stage('Check backend') {
            steps {
                sh '''
                    set -e

                    docker ps | grep sopk_backend

                    if docker ps --format '{{.Names}}' | grep -q '^pk_nginx$'; then
                        docker exec pk_nginx wget -q --spider http://sopk_backend:8000/admin/login/ || true
                        docker exec pk_nginx nginx -s reload || true
                    fi

                    echo "Backend deployed successfully"
                '''
            }
        }
    }

    post {
        success {
            echo 'Backend production deploy completed successfully.'
        }
        failure {
            echo 'Backend production deploy failed.'
        }
    }
}
