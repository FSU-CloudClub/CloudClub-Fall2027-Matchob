# Adding a Lambda Function

**Purpose:** Add a new endpoint to the backend.
**Tech:** AWS SAM (`template.yaml`, YAML), Python 3.13.
**Role in the project:** Adds your endpoint to the infrastructure as code (IaC), so `sam deploy` creates the Lambda, its permissions, and its API Gateway route.

## 1. Create the code folder

```
src/<function-name>/          # kebab-case, e.g. src/update-profile/
├── app.py                    # defines lambda_handler (see powertools.md)
└── requirements.txt          # function-only dependencies (shared ones go in src/shared/)
```

## 2. Add the resource to `template.yaml` (under `Resources:`)

```yaml
  # Lambda for PUT /profile
  UpdateProfileFunction:                        # logical ID: PascalCase + "Function"
    Type: AWS::Serverless::Function             # SAM Lambda resource
    Properties:
      CodeUri: src/update-profile/              # folder from step 1
      Handler: app.lambda_handler               # <file>.<function> to run
      Environment:
        Variables:
          POWERTOOLS_SERVICE_NAME: update-profile   # name shown in logs
      Policies:                                 # IAM permissions for this function only
        - DynamoDBCrudPolicy:                   # read + write one table
            TableName: !Ref MatchobUsersTable   # which table
      Events:                                   # what triggers the function
        UpdateProfile:                          # event name, unique within this function
          Type: Api                             # an API Gateway route
          Properties:
            RestApiId: !Ref MatchobApi          # attach to our API (Cognito auth applied automatically)
            Path: /profile                      # URL path
            Method: put                         # HTTP method
```

You don't repeat `Runtime`, `Timeout`, `Layers` (the shared auth layer), or the shared env vars. They come from `Globals`.

## Policy cheat sheet

```yaml
      Policies:
        - DynamoDBReadPolicy:                   # get/query/scan only
            TableName: !Ref MatchobUsersTable
        - DynamoDBCrudPolicy:                   # read + write
            TableName: !Ref MatchobUsersTable
        - S3ReadPolicy:                         # get objects
            BucketName: !Ref UploadBucket
        - S3CrudPolicy:                         # get + put + delete objects
            BucketName: !Ref UploadBucket
        - Statement:                            # raw IAM statement (Bedrock has no SAM shortcut)
            - Effect: Allow
              Action: bedrock:InvokeModel       # needed for converse()
              Resource: "*"                     # narrow to the model ARN once we pick one
```

Give each function only the policies it uses.

## Other options

```yaml
      Timeout: 30                               # override Globals (e.g. Bedrock calls). API Gateway gives up at 29s
      Events:
        Health:
          Type: Api
          Properties:
            RestApiId: !Ref MatchobApi
            Path: /health
            Method: get
            Auth:
              Authorizer: NONE                  # public route, no Cognito login required
```

## 3. Checklist

```bash
sam validate --lint                       # template is valid
sam build                                 # function + layer build
# add events/<function-name>.json         # event with requestContext.authorizer.claims.sub
# add any new env var to Globals AND env.example.json (see setup.md)
```

Then test it with [testing.md](testing.md), steps 4–5.
