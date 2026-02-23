# aws-pack Specification

## Purpose

Defines the `aws` tool pack for the `otdev` MCP server, providing credential management, identity queries, ARN utilities, pricing discovery, and lifecycle control for AWS MCP sub-servers.

## Requirements

### Requirement: AWS pack registration
The `otdev` server SHALL expose a tool pack named `aws` when boto3 is installed.

#### Scenario: Pack available at startup
- **WHEN** the `otdev` MCP server starts with boto3 installed
- **THEN** the `aws` namespace SHALL be available with all credential, identity, discovery, and lifecycle tools

### Requirement: Credential validation
The `aws.check()` tool SHALL validate the active AWS credentials and return a structured health report.

#### Scenario: Valid credentials
- **WHEN** `aws.check()` is called with valid credentials
- **THEN** it SHALL return a dict with keys `status`, `profile`, `account`, `arn`, `expiry`, `fix`
- **AND** `status` SHALL be `"ok"`
- **AND** `expiry` SHALL show remaining TTL

#### Scenario: SSO token expired (detected from cache)
- **WHEN** `aws.check()` is called and the SSO token in `~/.aws/sso/cache/` is expired
- **THEN** `status` SHALL be `"expired"`
- **AND** `fix` SHALL contain the appropriate `aws.login(profile=...)` call

#### Scenario: No credentials configured
- **WHEN** `aws.check()` is called and no credentials are configured
- **THEN** `status` SHALL be `"no_credentials"`
- **AND** `fix` SHALL be `"aws configure"`

#### Scenario: Profile not found
- **WHEN** `aws.check(profile="nonexistent")` is called
- **THEN** `status` SHALL be `"error"`
- **AND** `fix` SHALL reference `aws.profiles()`

### Requirement: SSO login
The `aws.login()` tool SHALL initiate an AWS SSO login flow and block until complete.

#### Scenario: Successful SSO login
- **WHEN** `aws.login(profile="prod-sso")` is called
- **AND** the user completes authentication in the browser
- **THEN** it SHALL return a success message with the confirmed identity

#### Scenario: Login with no profile argument
- **WHEN** `aws.login()` is called with no profile
- **THEN** it SHALL use the active profile from config or `AWS_PROFILE`

### Requirement: MFA session creation
The `aws.mfa()` tool SHALL obtain a temporary MFA session and write it to `~/.aws/credentials`.

#### Scenario: Successful MFA session
- **WHEN** `aws.mfa(profile="prod", token="123456")` is called with a valid 6-digit TOTP
- **THEN** it SHALL write temporary credentials to `~/.aws/credentials` under `[prod-mfa]`
- **AND** return a message indicating the profile name and TTL (12h)

#### Scenario: Invalid token
- **WHEN** `aws.mfa(profile="prod", token="000000")` is called with an invalid token
- **THEN** it SHALL return an error message with the AWS error reason

### Requirement: Profile listing
The `aws.profiles()` tool SHALL return all configured AWS profiles.

#### Scenario: List profiles
- **WHEN** `aws.profiles()` is called
- **THEN** it SHALL return a list of all profile names from `~/.aws/config` and `~/.aws/credentials`

### Requirement: Profile switching
The `aws.use()` tool SHALL switch the active AWS profile and restart active AWS stdio sub-servers.

#### Scenario: Switch profile
- **WHEN** `aws.use(profile="prod")` is called
- **THEN** it SHALL update `os.environ["AWS_PROFILE"]` and the pack config
- **AND** restart all currently active `aws-*` stdio sub-servers
- **AND** return confirmed identity after switch

#### Scenario: Switch with region override
- **WHEN** `aws.use(profile="prod", region="eu-west-1")` is called
- **THEN** it SHALL also update the active region in the pack config
- **AND** restart active stdio sub-servers

### Requirement: Identity query
The `aws.whoami()` tool SHALL return the current caller identity.

#### Scenario: Identity lookup
- **WHEN** `aws.whoami()` is called
- **THEN** it SHALL return a dict with keys `account`, `arn`, `user_id`, `region`, `profile`

### Requirement: Active profile info
The `aws.profile()` tool SHALL return the active profile, region, account, and account alias.

#### Scenario: Profile info
- **WHEN** `aws.profile()` is called
- **THEN** it SHALL return a dict with the active profile name, region, account ID, and account alias

### Requirement: ARN parsing
The `aws.arn()` tool SHALL parse an AWS ARN string into its components.

#### Scenario: Parse valid ARN
- **WHEN** `aws.arn("arn:aws:iam::123456789012:role/MyRole")` is called
- **THEN** it SHALL return a dict with keys `partition`, `service`, `region`, `account`, `resource`, `console_url`

#### Scenario: Parse ARN with region
- **WHEN** `aws.arn("arn:aws:lambda:us-east-1:123456789:function:my-fn")` is called
- **THEN** `region` SHALL be `"us-east-1"` and `console_url` SHALL point to the Lambda console

### Requirement: Region listing
The `aws.regions()` tool SHALL return available regions for an AWS service.

#### Scenario: Default regions
- **WHEN** `aws.regions()` is called with no arguments
- **THEN** it SHALL return regions for EC2

#### Scenario: Service-specific regions
- **WHEN** `aws.regions(service="lambda")` is called
- **THEN** it SHALL return regions where Lambda is available

### Requirement: Pricing service discovery
The `aws.services()` tool SHALL list AWS service codes from the Pricing API.

#### Scenario: List all services
- **WHEN** `aws.services()` is called
- **THEN** it SHALL return ~200 service code strings from the AWS Pricing API

#### Scenario: Filtered service list
- **WHEN** `aws.services(filter="RDS")` is called
- **THEN** it SHALL return only service codes containing "RDS" (case-insensitive)

### Requirement: Pricing attribute discovery
The `aws.attributes()` tool SHALL return filterable attribute names for an AWS pricing service.

#### Scenario: List attributes
- **WHEN** `aws.attributes(service="AmazonEC2")` is called
- **THEN** it SHALL return a list of attribute name strings (e.g., `["instanceType", "location", ...]`)

### Requirement: Pricing attribute values
The `aws.values()` tool SHALL return valid values for a pricing attribute.

#### Scenario: List instance types
- **WHEN** `aws.values(service="AmazonEC2", attribute="instanceType")` is called
- **THEN** it SHALL return all valid instance type strings

### Requirement: Role listing
The `aws.roles()` tool SHALL list all available roles with their server lists.

#### Scenario: List built-in roles
- **WHEN** `aws.roles()` is called
- **THEN** it SHALL display all 18 built-in roles with their member server names

#### Scenario: User-defined roles tagged
- **WHEN** user-defined roles are configured under `tools: aws: roles:` in `onetool.yaml`
- **AND** `aws.roles()` is called
- **THEN** user-defined roles SHALL be tagged with `[user]` in the output
- **AND** SHALL appear alongside built-in roles

### Requirement: Enable AWS MCP server packs
The `aws.enable_packs()` tool SHALL connect one or more AWS MCP sub-servers without disrupting existing connections.

#### Scenario: Enable by role
- **WHEN** `aws.enable_packs(role="finops")` is called
- **AND** credentials are valid
- **THEN** it SHALL connect all stdio servers in the `finops` role incrementally
- **AND** return a status report showing each server name and tool count

#### Scenario: Enable by server list
- **WHEN** `aws.enable_packs(pack=["iam", "cloudwatch"])` is called
- **THEN** it SHALL connect `aws-iam` and `aws-cloudwatch`

#### Scenario: Enable role and pack together
- **WHEN** `aws.enable_packs(role="finops", pack=["iam"])` is called
- **THEN** it SHALL connect the union of finops servers and `aws-iam` (deduplicated)

#### Scenario: Credential pre-flight fails
- **WHEN** `aws.enable_packs(role="finops")` is called
- **AND** credentials are expired or missing
- **THEN** it SHALL NOT attempt to connect any stdio servers
- **AND** SHALL return an error with the specific credential fix
- **AND** HTTP servers (e.g., `aws-knowledge`) in the role SHALL still connect

#### Scenario: Already connected server skipped
- **WHEN** `aws.enable_packs(pack=["iam"])` is called
- **AND** `aws-iam` is already connected
- **THEN** it SHALL report the server as already connected without reconnecting

#### Scenario: Unknown role name
- **WHEN** `aws.enable_packs(role="nonexistent-role")` is called
- **THEN** it SHALL return an error listing available role names

#### Scenario: Unknown server name in pack list
- **WHEN** `aws.enable_packs(pack=["nonexistent-server"])` is called
- **THEN** it SHALL return an error listing valid server short names

### Requirement: Disable AWS MCP server packs
The `aws.disable_packs()` tool SHALL disconnect one or more AWS MCP sub-servers without affecting other connections.

#### Scenario: Disable by role
- **WHEN** `aws.disable_packs(role="finops")` is called
- **THEN** it SHALL disconnect all connected servers in the `finops` role
- **AND** return a status report

#### Scenario: Disable by server list
- **WHEN** `aws.disable_packs(pack=["iam"])` is called
- **THEN** it SHALL disconnect `aws-iam`

#### Scenario: Disable non-connected server
- **WHEN** `aws.disable_packs(pack=["iam"])` is called
- **AND** `aws-iam` is not currently connected
- **THEN** it SHALL report the server as not active without error

### Requirement: List active AWS packs
The `aws.packs()` tool SHALL list currently connected AWS MCP sub-servers.

#### Scenario: Active packs with tool counts
- **WHEN** `aws.packs()` is called
- **AND** some AWS servers are connected
- **THEN** it SHALL display each active server name and its tool count

#### Scenario: No active packs
- **WHEN** `aws.packs()` is called
- **AND** no AWS sub-servers are connected
- **THEN** it SHALL return a message indicating no AWS packs are active
