# AWS MCP

AWS services via the official [awslabs/mcp](https://github.com/awslabs/mcp) servers. Unlike the other proxy servers, AWS is managed as a dynamic tool pack — servers are activated on demand by role or name rather than being statically configured in `servers.yaml`.

## Quick Start

```python
aws.check()                          # Verify your credentials
aws.start_packs(role="finops")       # Activate cost/billing servers
aws.start_packs(pack=["iam"])        # Activate a specific server
aws.packs()                          # List active servers with doc links
aws.stop_packs(role="finops")        # Deactivate servers
```

## Roles

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

## Core Servers

Recommended starting points for most workflows:

| Server | Purpose |
|--------|---------|
| `know` ★ | Semantic AWS knowledge search (no credentials needed) |
| `core` ★ | OneTool core utilities and scaffolding |
| `api` ★ | General AWS CLI wrapper — any service, any operation |
| `iam` ★ | IAM users, roles, policies, permissions |
| `cloudtrail` ★ | Audit trail, event history |

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
aws.use(profile="staging")
aws.use(profile="prod", region="eu-west-1")
aws.whoami()     # Confirm identity
aws.profile()    # Profile + account alias
```

## `aws-api` vs Specialist Servers

| Situation | Use |
|-----------|-----|
| One-off CLI command, any service | `aws-api` — wraps the AWS CLI |
| Deep integration with a specific service | Specialist server (e.g., `aws-iam`, `aws-ecs`) |
| Cost analysis | `finops` role |
| Infrastructure management | `iac` role |
| AI/ML workloads | `ai` or `ml` role |

```python
aws.start_packs(pack=["api"])
# Then: api.execute_aws_api_call(service="s3", operation="list_buckets")
```

## Unlisted Servers

Any `awslabs` server can be started by package name, even if it isn't in the curated registry:

```python
aws.start_packs(pack="awslabs.frontend-mcp-server")
# Short name strips prefix/suffix: frontend.*
```

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

## Notes

- **Cold start**: `uvx` downloads packages on first use — expect 10–30s
- **Credential pre-flight**: stdio servers require valid credentials before spawning; `aws-know` (HTTP) skips this check
- **Session persistence**: Active servers persist until `stop_packs()` or session end
- **Namespace**: After `start_packs`, tools are available as `<server>.<tool>()` with hyphens replaced by underscores (e.g., `well_arch.CheckSecurityServices()`)

## Known Issues (Upstream)

These are bugs in the awslabs MCP servers. Track fixes at https://github.com/awslabs/mcp.

| Server | Issue | Workaround |
|--------|-------|------------|
| `well-arch` | `CheckNetworkSecurity` / `CheckStorageEncryption` crash with `'str' object has no attribute 'get'` | Use `CheckSecurityServices` or `GetSecurityFindings` |
| `well-arch` | `CheckSecurityServices(services=["trustedadvisor"])` leaks raw Python exception on accounts without Business/Enterprise Support | Exclude `trustedadvisor` from services list |
| `cost` | `get_cost_and_usage` takes CamelCase metrics; `get_cost_forecast` requires UPPER_SNAKE_CASE | Use `UNBLENDED_COST`, `AMORTIZED_COST`, etc. for forecasts |
| `ecs`, `mysql`, `spark-*` | Connection closed on startup | Use `aws-api` as fallback |
| `agentcore` | `search_agentcore_docs` returns empty response | Use `doc.search_documentation()` or `know` |
| `appsync` | Only `create_*` tools available — no list/get/update/delete | Use `api.execute_aws_api_call(service="appsync", ...)` |
| `bedrock-kb`, `sns-sqs`, `redshift` | Empty response instead of empty list when no resources exist | Treat empty/null as empty collection |
| `billing` | `cost_explorer()` requires undiscoverable `operation` arg | Use `billing.budgets()` or `cost.get_cost_and_usage(...)` |
| `cdk` | `GetAwsSolutionsConstructPattern` requires `pattern_name` or `services`, not `query` | `cdk.GetAwsSolutionsConstructPattern(services=["s3", "lambda"])` |
| `dataproc` | `list_s3_buckets()` silently filters to buckets with `'glue'` in the name | Use `api.execute_aws_api_call(service="s3", operation="list_buckets")` |
| `mq` | Tool names have typo: `rabbimq` instead of `rabbitmq` | Calls still succeed via fuzzy matching |
| `msk`, `mq`, `sagemaker` | `region` required on every call despite `AWS_DEFAULT_REGION` being set | Pass `region=` explicitly on every call |
| `repo-research` | `keywords` must be `list[str]`, not a string | `search_repos_on_github(keywords=["mcp", "aws"])` |
| `terraform` | `SearchAwsProviderDocs` requires `asset_name`, not `query` | `SearchAwsProviderDocs(asset_name="aws_s3_bucket")` |
