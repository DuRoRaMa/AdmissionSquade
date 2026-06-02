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
        stage('Sync backend master') {
            steps {
                sh '''
                    git config --global --add safe.directory /srv/pk-services/Squad/AdmissionSquade

                    cd /srv/pk-services/Squad/AdmissionSquade
                    git fetch origin master
                    git reset --hard origin/master
                '''
            }
        }

        stage('Build and deploy backend') {
            steps {
                sh '''
                    cd /srv/pk-services/Squad/AdmissionSquade

                    docker network inspect pk_proxy >/dev/null 2>&1 || docker network create pk_proxy

                    docker compose -f docker-compose.prod.yml up -d --build
                '''
            }
        }

        stage('Backend checks') {
            steps {
                sh '''
                    docker ps | grep sopk_backend
                    docker exec pk_nginx wget -q --spider http://sopk_backend:8000/admin/login/
                    docker exec pk_nginx nginx -s reload
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
