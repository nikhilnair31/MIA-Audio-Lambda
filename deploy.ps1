# Function to check if Docker is logged in to AWS ECR
function Check-DockerLogin {
    try {
        docker info | Out-String -Stream | Select-String -Pattern "ECRLogin"
        return $true
    } catch {
        return $false
    }
}

# Function to check if AWS ECR repository exists
function Check-ECRRepositoryExists {
    param ($repositoryName)
    try {
        $repo = aws ecr describe-repositories --repository-names $repositoryName 2>$null
        if ($repo) {
            return $true
        } else {
            return $false
        }
    } catch {
        return $false
    }
}

# Login to AWS ECR if not logged in
if (Check-DockerLogin) {
    aws ecr get-login-password | docker login --username AWS --password-stdin 832214191436.dkr.ecr.ap-south-1.amazonaws.com
}

# Create repository if it does not exist
$repositoryName = "mia-lambda"
if (-not (Check-ECRRepositoryExists $repositoryName)) {
    aws ecr create-repository --repository-name $repositoryName
}

# Build and push Docker image
docker build -t mia-lambda .
docker tag mia-lambda:latest 832214191436.dkr.ecr.ap-south-1.amazonaws.com/mia-lambda:latest
docker push 832214191436.dkr.ecr.ap-south-1.amazonaws.com/mia-lambda:latest
aws ecr list-images --repository-name mia-lambda --region ap-south-1
