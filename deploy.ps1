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

# Create repository if it does not exist
$repositoryName = "mia-lambda"
if (-not (Check-ECRRepositoryExists $repositoryName)) {
    aws ecr create-repository --repository-name $repositoryName
}

# AWS Login
aws ecr get-login-password | docker login --username AWS --password-stdin 832214191436.dkr.ecr.ap-south-1.amazonaws.com

# Build Docker image
docker build -t mia-lambda .

# Tag the image with 'latest'. This tag will overwrite any existing 'latest' image in the repository.
docker tag mia-lambda:latest 832214191436.dkr.ecr.ap-south-1.amazonaws.com/mia-lambda:latest

# Push the image. This will overwrite the existing 'latest' image in the ECR repository.
docker push 832214191436.dkr.ecr.ap-south-1.amazonaws.com/mia-lambda:latest

# List images in the repository to confirm the push
aws ecr list-images --repository-name mia-lambda --region ap-south-1

# TODO: Need to update this

# Define Lambda function name
$lambdaFunctionName = "mia-audio"

# Update Lambda function with the new image
$imageUri = "832214191436.dkr.ecr.ap-south-1.amazonaws.com/mia-lambda:latest"
aws lambda update-function-code --function-name $lambdaFunctionName --image-uri $imageUri

# Function to check if the Lambda function has been updated with the new image
function Check-LambdaUpdate {
    param ($functionName, $expectedUri)
    $functionInfo = aws lambda get-function --function-name $functionName | ConvertFrom-Json
    return $functionInfo.Configuration.Code.ImageUri -eq $expectedUri
}

# Wait for the update to be confirmed
$tries = 0
$maxTries = 10
$updated = $false
while ($tries -lt $maxTries -and -not $updated) {
    Write-Host "Checking if Lambda function has been updated... (Attempt: $($tries + 1))"
    Start-Sleep -Seconds 3
    $updated = Check-LambdaUpdate -functionName $lambdaFunctionName -expectedUri $imageUri
    $tries++
}

if ($updated) {
    Write-Host "Lambda function updated successfully with the new image."
} else {
    Write-Host "Failed to confirm the update of the Lambda function after $($maxTries) attempts."
}