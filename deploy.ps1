# Function to check if AWS ECR repository exists
function Check-ECRRepositoryExists {
    param ($name)
    try {
        $repo = aws ecr describe-repositories --repository-names $name 2>$null
        if ($repo) {
            return $true
        } else {
            return $false
        }
    } catch {
        return $false
    }
}

# Name
$name = "mia-audio"

# Login
"Loggin in..."
aws ecr get-login-password | docker login --username AWS --password-stdin 832214191436.dkr.ecr.ap-south-1.amazonaws.com

# ECR
"ECR"
# Create repository if it does not exist
if (-not (Check-ECRRepositoryExists $name)) {
    aws ecr create-repository --repository-name $name
}
# Delete all images in the repository
$images = aws ecr describe-images --repository-name $name --output json | ConvertFrom-Json
if ($images.imageDetails) {
    $images.imageDetails | ForEach-Object {
        aws ecr batch-delete-image --repository-name $name --image-ids "imageDigest=$($_.imageDigest)"
    }
}

# Docker
"Docker"
# Build Docker image
docker build -t ${name} .
# Tag the image with 'latest'. This tag will overwrite any existing 'latest' image in the repository.
docker tag ${name}:latest 832214191436.dkr.ecr.ap-south-1.amazonaws.com/${name}:latest
# Push the image. This will overwrite the existing 'latest' image in the ECR repository.
docker push 832214191436.dkr.ecr.ap-south-1.amazonaws.com/${name}:latest
# List images in the repository to confirm the push
aws ecr list-images --repository-name ${name} --region ap-south-1

# ECR
"ECR"
# Make sure $latestImageDigest is populated
$images = aws ecr describe-images --repository-name $name --output json | ConvertFrom-Json
if ($images.imageDetails) {
    $images.imageDetails | ForEach-Object {
        if ($_.imageTags -contains "latest") {
            $latestImageDigest = $_.imageDigest
        }
    }
}
if (-not $latestImageDigest) {
    $latestImageDigest = (aws ecr describe-images --repository-name $name --query 'imageDetails[?imageTags[?contains(@, `latest`)]].imageDigest' --output text)
}
# Construct the image URI using the image digest
$imageUri = "832214191436.dkr.ecr.ap-south-1.amazonaws.com/${name}@${latestImageDigest}"    

# Lambda
"Lambda"
# TODO: Update to also create Lambda if it doesn't exist 
# Update the Lambda function to use the new image URI
$lambdaUpdate = aws lambda update-function-code --function-name $name --image-uri $imageUri
if ($lambdaUpdate) {
    "Lambda function updated successfully"
} else {
    "Failed to update Lambda function"
}