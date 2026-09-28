# Requirements — Story 746042

- **Story ID:** 746042
- **Title:** Provision AWS ECS environments for D2R2 (DEV / TEST / PREPROD / PROD)
- **Type:** User Story
- **State:** In Dev
- **Area:** DEFRA-LAI\DEFRA LAP D2R2
- **Iteration:** DEFRA-LAI\D2R2 Sprint 2
- **Cycle:** 1
- **Trigger:** none (initial requirements stage)

## Restatement

As the D2R2 delivery team, we need the Platform Team (Defra AWS CCoE) to provision the AWS environments described in `D2R2-AWS-ECS-Environment-Request.docx` — ECS Fargate clusters/services, RDS SQL Server, ElastiCache Redis, security groups, S3 buckets, and SSM Parameter Store/Secrets Manager entries — across DEV, TEST, PREPROD and PROD, so that `CDC.Web` and `CDC.Api` can be built, deployed and tested end-to-end.

## Acceptance Criteria

1. Given the provisioning request document, CCoE has created ECS Fargate clusters/services, RDS SQL Server, ElastiCache Redis and the security groups (`<ENV>LDNCDCSGP001`, `<ENV>LDNCDCRDSSGP001`, `<ENV>LDNCDCCACHESGP001`) in all four environments, matching the sizing/naming in the document.
2. Given the environments are provisioned, `CDC.Web` and `CDC.Api` can be deployed to at least DEV via the CI/CD pipeline and successfully connect to RDS and Redis over the expected security-group rules (no public IP, private-subnet only).
3. Given SSM Parameter Store/Secrets Manager have been created for the keys listed in Section 9, the D2R2 team has been given the parameter/secret names (and access) needed to populate real values before first deployment.

**Definition of Done:** All four environments provisioned and confirmed reachable by the pipeline; any deviations from the request document reconciled back into it.

**Testability flags:**
- AC1 is testable only if `D2R2-AWS-ECS-Environment-Request.docx` — the sizing/naming source of truth — is available to verify against. That document was not supplied to this agent and is not present in the workspace. **[NEEDS INPUT]**
- AC2 is testable (deploy + connectivity check on DEV).
- AC3 is testable (confirm parameter/secret names and access handed over), but "Section 9" of the request document could not be inspected to enumerate the exact keys expected. **[NEEDS INPUT]**

## In Scope

- Provisioning (by CCoE, not this team) of ECS Fargate clusters/services, RDS SQL Server, ElastiCache Redis, S3 buckets, and the three named security groups in DEV, TEST, PREPROD and PROD.
- Creation of SSM Parameter Store / Secrets Manager entries for the keys listed in Section 9 of the request document, and handover of names/access to the D2R2 team.
- Verifying `CDC.Web` and `CDC.Api` can deploy to DEV via CI/CD and connect to RDS and Redis over private-subnet-only security-group rules (no public IP).
- Reconciling any deviations from the request document back into that document.

## Out of Scope

- Provisioning or deployment work for TEST, PREPROD and PROD beyond confirming they are provisioned (only DEV requires an end-to-end deploy/connectivity check per AC2).
- Populating real secret/parameter values — the story only requires that names and access are handed over, not that values are populated.
- Any application-level code changes to `CDC.Web` or `CDC.Api` (this story is infrastructure provisioning only).
- Creating or amending the `D2R2-AWS-ECS-Environment-Request.docx` specification itself, beyond reconciling confirmed deviations.

## Affected Components

- AWS infrastructure: ECS Fargate (clusters/services), RDS SQL Server, ElastiCache Redis, S3, security groups, SSM Parameter Store, Secrets Manager.
- Applications: `CDC.Web`, `CDC.Api` (consumers of the provisioned environments, deployed via CI/CD).
- Environments: DEV, TEST, PREPROD, PROD.

*(No HLD/HLSA/LLD paths were supplied — this is not a migration project — so affected components are drawn solely from the story text.)*

## Open Questions for the Developer

1. `D2R2-AWS-ECS-Environment-Request.docx` is referenced as the source of truth for sizing, naming, and the Section 9 secret/parameter key list, but was not supplied to this agent and is not present in the workspace. Can it be attached so AC1 and AC3 can be verified precisely?
2. AC2 only requires DEV deployment/connectivity to be proven — should TEST, PREPROD and PROD receive the same verification before this story is considered done, or is that deferred to later stories?
3. Tags field on the ADO story is empty — confirm there are no additional labels/classifications (e.g. security review required) that should apply to this story.
4. "Reconciled back into it" (the request document) implies CCoE or the D2R2 team may update `D2R2-AWS-ECS-Environment-Request.docx` — who owns that document update, and where does it live so it can be updated?
