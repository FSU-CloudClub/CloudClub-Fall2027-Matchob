# DynamoDB User Pipeline

## User table outline

# This was generated with codex based on what we wrote down on paper during the Thursday meeting. Hasn't been verified as exactly what we want to ultimately do yet.

Each item represents one user. The partition key identifies the user, and the remaining attributes store their personal information, education, websites, and resumes.

| Attribute | Type | Description |
| --- | --- | --- |
| `userId` | String | Partition key: the authenticated user's unique ID (Cognito `sub`). |
| `firstname` | String | User's first name. |
| `lastname` | String | User's last name. |
| `email` | String | User's email address. |
| `phoneNumber` | String | Phone number, stored as text to preserve country codes and leading zeros. |
| `age` | Number | User's age in years. |
| `year` | String | Academic year, such as freshman, sophomore, junior, or senior. |
| `major` | String | User's field of study. |
| `websites` | List of strings | Website links, such as LinkedIn, GitHub, or a personal portfolio. |
| `resumes` | List of strings | Links to the user's resumes. |
| `defaultResume` | String | Link to the user's default resume. |
| `structuredJsonResume` | Map | Resume content stored as a structured JSON object, including nested fields and lists. |

The key is written as `userId` to match the existing DynamoDB table and endpoint code. DynamoDB stores the other fields as individual attributes on the item, rather than inside a single `Value` field.

## Operations

- Create a user.
- Edit a user.
- Delete a user.
- Get a user's core metadata.
- Get a user's full profile.

