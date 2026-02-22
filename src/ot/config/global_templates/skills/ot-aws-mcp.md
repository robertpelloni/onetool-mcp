---
name: ot-aws-mcp
description: AWS MCP usage guide — activate curated awslabs/mcp servers by role, manage credentials, and discover AWS resources
tags: [aws, cloud, mcp, iam, finops, bedrock]
---

# AWS MCP Guide

OneTool integrates the official [awslabs/mcp](https://github.com/awslabs/mcp) servers through the `aws` tool pack. Activate servers by role in a single call; credentials are validated before any sub-process is spawned.

## Quick Start

```python
aws.check()                          # Verify your credentials
aws.start_packs(role="finops")      # Activate cost/billing servers
aws.start_packs(pack=["iam"])       # Activate a specific server
aws.packs()                          # List active servers with doc links
aws.stop_packs(role="finops")       # Deactivate servers
```

## Core Servers (★)

These are the recommended starting points for most workflows:

| Server | Purpose |
|--------|---------|
| `know` ★ | Semantic AWS knowledge search (no credentials needed) |
| `core` ★ | OneTool core utilities and scaffolding |
| `api` ★ | General AWS CLI wrapper — any service, any operation |
| `iam` ★ | IAM users, roles, policies, permissions |
| `cloudtrail` ★ | Audit trail, event history |

## Role Table

| Role | Servers |
|------|---------|
| `finops` | cost, billing, pricing, support |
| `security` | iam, cloudtrail, well-arch, support |
| `compute` | ecs, eks, lambda, sfn, serverless |
| `database` | dynamodb, documentdb, mysql, postgres, redshift, neptune |
| `cache` | elasticache, memcached, valkey |
| `storage` | s3-tables |
| `ai` | agentcore, bedrock-kb, bedrock-import, bedrock-da, canvas, qbusiness, kendra |
| `ml` | sagemaker, spark-debug, spark-upgrade, synth |
| `monitoring` | cloudwatch, appsignals, cloudwatch-appsignals, prometheus, cloudtrail |
| `networking` | network, location |
| `messaging` | sns-sqs, mq, msk |
| `iac` | cdk, cfn, terraform, iac |
| `devtools` | diagram, repo-research, loader, openapi, core |
| `data` | dataproc, s3-tables, redshift, synth |
| `discovery` | doc, core, know, pricing |
| `all` | all registered servers |

Use `aws.roles()` to see the full list including user-defined roles.

## Credential Setup

### SSO (recommended)

```python
aws.profiles()                        # List configured profiles
aws.login(profile="prod-sso")         # Open browser for SSO auth
aws.check()                           # Confirm: status should be "ok"
```

### MFA session

```python
aws.mfa(profile="prod", token="123456")   # Creates [prod-mfa] in ~/.aws/credentials
aws.use(profile="prod-mfa")               # Switch to MFA session
```

### Profile switching

```python
aws.use(profile="staging")                        # Switch profile
aws.use(profile="prod", region="eu-west-1")       # Switch profile + region
aws.whoami()                                       # Confirm identity
aws.profile()                                      # Profile + account alias
```

## Discovery Workflow

```python
# Understand your environment
aws.check()                            # Credential health
aws.whoami()                           # Account + ARN
aws.regions(service="lambda")          # Available regions

# Parse an ARN
aws.arn(arn_string="arn:aws:iam::123456789012:role/MyRole")

# Explore pricing
aws.services(filter="RDS")             # Find service codes
aws.attributes(service="AmazonRDS")    # List filterable attributes
aws.values(service="AmazonRDS", attribute="databaseEngine")  # Valid values
```

## `aws-api` vs Specialist Servers

| Situation | Use |
|-----------|-----|
| One-off CLI command, any service | `aws-api` — wraps the AWS CLI |
| Deep integration with specific service | Specialist server (e.g., `aws-iam`, `aws-ecs`) |
| Cost analysis | `finops` role — cost, billing, pricing |
| Infrastructure management | `iac` role — cdk, cfn, terraform |
| AI/ML workloads | `ai` or `ml` role |

Enable `aws-api` for general access:

```python
aws.start_packs(pack=["api"])
# Then use: api.execute_aws_api_call(...)
```

## Starting Unlisted Servers (Escape Hatch)

Any `awslabs` server can be started by its package name, even if it isn't in the curated registry:

```python
aws.start_packs(pack="awslabs.frontend-mcp-server")
# Short name derived: frontend → available as frontend.*
```

The short name strips the `awslabs.` prefix and `-mcp-server` suffix. HTTP servers work the same way with an `https://` URL.

## User-Defined Roles

Add custom roles to `~/.onetool/onetool.yaml`:

```yaml
tools:
  aws:
    profile: prod-sso
    region: us-east-1
    roles:
      myteam:
        - ecs
        - dynamodb
        - cloudwatch
```

Then: `aws.start_packs(role="myteam")`

## Active Packs

`aws.packs()` returns per-server details for all active packs:

```python
aws.packs()
# → {
#     "iam":  {"tools": 45, "doc": "https://awslabs.github.io/mcp/servers/iam-mcp-server", "core": True},
#     "cost": {"tools": 12, "doc": "https://awslabs.github.io/mcp/servers/cost-explorer-mcp-server"},
#   }
```

Core servers (`"core": True`) are the recommended starting points. All `doc` links open the official awslabs documentation for that server.

## Notes

- **Server startup**: `uvx` downloads packages on first use. Expect 10–30s on cold start.
- **Credential pre-flight**: stdio servers require valid credentials before spawning. HTTP servers (`aws-know`) skip this check.
- **Session persistence**: Active servers persist until `stop_packs()` or session end.
- **Namespace access**: After `start_packs`, tools are available via the short server name with hyphens replaced by underscores (e.g., `iam.list_users()`, `cost.get_cost_and_usage(...)`, `well_arch.CheckSecurityServices()`).

## Known Issues (Upstream)

These are bugs in the awslabs MCP servers, not in OneTool. Track fixes upstream at https://github.com/awslabs/mcp.

### well-arch: CheckNetworkSecurity / CheckStorageEncryption crash

`CheckNetworkSecurity` and `CheckStorageEncryption` return `"error": "'str' object has no attribute 'get'"` and do not produce results. The upstream server calls `.get()` on a string response from a boto3 API.

**Workaround**: Use `CheckSecurityServices` (works correctly — uses GuardDuty/Inspector/etc. directly) or `GetSecurityFindings` to read previously stored context.

### well-arch: TrustedAdvisor leaks raw Python exception repr

`CheckSecurityServices(services=["trustedadvisor"])` returns a raw Python object repr in the error field:
```
"<botocore.errorfactory.SupportExceptions object at 0x...> object has no attribute SubscriptionRequiredException"
```
This happens on accounts without AWS Business or Enterprise Support.

**Workaround**: Exclude `trustedadvisor` from the services list. TrustedAdvisor requires a Business or Enterprise Support plan.

### cost: metric name casing inconsistency

`get_cost_and_usage` accepts **CamelCase** metrics (`UnblendedCost`), but `get_cost_forecast` requires **UPPER_SNAKE_CASE** (`UNBLENDED_COST`). Passing CamelCase to `get_cost_forecast` returns a clear error listing valid values.

**Workaround**: Use `UPPER_SNAKE_CASE` for `get_cost_forecast`: `AMORTIZED_COST`, `BLENDED_COST`, `NET_AMORTIZED_COST`, `NET_UNBLENDED_COST`, `UNBLENDED_COST`.

### ecs / lambda-handler / mysql / openapi / spark-debug / spark-upgrade: Connection closed on startup

These servers fail with `"Connection closed"` immediately on `start_packs()`. Likely causes: missing system dependencies (Java/Spark for spark-*, database client libs for mysql), or server-side crash on startup.

**Workaround**: Avoid these servers until upstream fixes the startup issue. Use `aws-api` as a general-purpose fallback.

### agentcore: search_agentcore_docs returns empty response

`agentcore.search_agentcore_docs(query="...")` returns an empty response for any query. The upstream server appears to have no indexed content or calls an unavailable backend.

**Workaround**: Use `doc.search_documentation()` or `know` (the HTTP knowledge server) for AWS documentation search instead.

### appsync: only create operations available

The `aws-appsync` pack exposes only 10 `create_*` tools. There are no tools to list, get, update, or delete existing AppSync APIs, resolvers, or data sources.

**Workaround**: Use `api.execute_aws_api_call(...)` with the AppSync service directly for read/update/delete operations.

### bedrock-kb / sns-sqs / redshift: empty response for empty collections

`bedrock_kb.ListKnowledgeBases()`, `sns_sqs.list_queues()`, and `redshift.list_clusters()` return `{}` or `"Tool returned empty response"` when no resources exist, rather than a structured empty list. This makes it impossible to distinguish "no resources" from "call failed".

**Workaround**: Treat an empty/null response as an empty collection. These calls do not error on valid credentials.

### billing: cost_explorer() requires undiscoverable `operation` arg

`billing.cost_explorer()` fails with `Missing required argument: operation`. No valid values are documented in the tool description.

**Workaround**: Use `billing.budgets()` (works with no args) or `cost.get_cost_and_usage(...)` directly from the `cost` pack.

### cdk: GetAwsSolutionsConstructPattern uses `pattern_name`/`services`, not `query`

`cdk.GetAwsSolutionsConstructPattern(query="S3 Lambda")` fails — the tool requires either `pattern_name` (exact name like `"aws-s3-lambda"`) or `services` (list like `["s3", "lambda"]`).

**Workaround**: `cdk.GetAwsSolutionsConstructPattern(services=["s3", "lambda"])`

### dataproc: list_s3_buckets silently filters to buckets with 'glue' in the name

`dataproc.list_s3_buckets()` hardcodes a filter for buckets with `'glue'` in their name despite the tool name implying a full list.

**Workaround**: Use `api.execute_aws_api_call(service="s3", operation="list_buckets")` for a true bucket listing.

### mq: rabbitmq tool name typo (`rabbimq` vs `rabbitmq`)

Two tools have a missing `t`: `rabbimq_broker_initialize_connection` and `rabbimq_broker_initialize_connection_with_oauth`. OneTool's fuzzy matching resolves `rabbitmq_broker_initialize_connection` to the typo'd name, so calls succeed, but the tool listing is confusing.

### msk / mq / sagemaker: region required on every call

These packs require an explicit `region` (or `region_name`) argument on every tool call with no default, even though `AWS_DEFAULT_REGION` is set in the environment.

**Workaround**: Pass the region explicitly: `msk.get_global_info(region="us-east-1")`. Get the active region from `aws.profile()["region"]`.

### repo-research: keywords must be a list, not a string

`repo_research.search_repos_on_github(keywords="mcp aws")` fails with a pydantic validation error — `keywords` requires `list[str]`.

**Workaround**: `repo_research.search_repos_on_github(keywords=["mcp", "aws"], org="awslabs")`

### terraform: SearchAwsProviderDocs requires asset_name, not a query string

`terraform.SearchAwsProviderDocs(query="S3 bucket")` fails — the tool requires `asset_name` (exact Terraform resource name like `"aws_s3_bucket"`).

**Workaround**: `terraform.SearchAwsProviderDocs(asset_name="aws_s3_bucket")`
