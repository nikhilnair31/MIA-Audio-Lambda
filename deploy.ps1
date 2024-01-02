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

# AWS Login
aws ecr get-login-password | docker login --username AWS --password-stdin 832214191436.dkr.ecr.ap-south-1.amazonaws.com

# Create repository if it does not exist
$repositoryName = "mia-audio-lambda"
if (-not (Check-ECRRepositoryExists $repositoryName)) {
    aws ecr create-repository --repository-name $repositoryName
}

# Delete all images in the repository
$images = aws ecr describe-images --repository-name $repositoryName --output json | ConvertFrom-Json
if ($images.imageDetails) {
    $images.imageDetails | ForEach-Object {
        aws ecr batch-delete-image --repository-name $repositoryName --image-ids "imageDigest=$($_.imageDigest)"
    }
}

# Build Docker image
docker build -t mia-audio-lambda .
# Tag the image with 'latest'. This tag will overwrite any existing 'latest' image in the repository.
docker tag mia-audio-lambda:latest 832214191436.dkr.ecr.ap-south-1.amazonaws.com/mia-audio-lambda:latest
# Push the image. This will overwrite the existing 'latest' image in the ECR repository.
docker push 832214191436.dkr.ecr.ap-south-1.amazonaws.com/mia-audio-lambda:latest
# List images in the repository to confirm the push
aws ecr list-images --repository-name mia-audio-lambda --region ap-south-1

# Deploy the latest image to Lambda
$lambdaName = "mia-audio"
# Make sure $latestImageDigest is populated
$images = aws ecr describe-images --repository-name $repositoryName --output json | ConvertFrom-Json
if ($images.imageDetails) {
    $images.imageDetails | ForEach-Object {
        if ($_.imageTags -contains "latest") {
            $latestImageDigest = $_.imageDigest
        }
    }
}
if (-not $latestImageDigest) {
    $latestImageDigest = (aws ecr describe-images --repository-name $repositoryName --query 'imageDetails[?imageTags[?contains(@, `latest`)]].imageDigest' --output text)
}
# Construct the image URI using the image digest
$imageUri = "832214191436.dkr.ecr.ap-south-1.amazonaws.com/mia-audio-lambda@${latestImageDigest}"    
# Update the Lambda function to use the new image URI
$lambdaUpdate = aws lambda update-function-code --function-name $lambdaName --image-uri $imageUri
if ($lambdaUpdate) {
    "Lambda function updated successfully"
} else {
    "Failed to update Lambda function"
}   