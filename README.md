# Enforcing Single-Role Authentication for Cortex Code CLI with Programmatic Access Tokens

## The problem you are trying to solve

The **Cortex Code CLI** is designed to authenticate against Snowflake using either:

* **Browser-based SSO** (authenticator = "externalbrowser") as the default, or
* **Programmatic Access Tokens (PATs)** (stored as the password value in the connection definition). [[1]](https://docs.snowflake.com/en/user-guide/cortex-code/cli-reference)

If your goal is: **“This CLI must run under exactly one Snowflake role, always”**, then PATs are attractive because Snowflake can bind a PAT to a role using ROLE\_RESTRICTION. When a PAT is role-restricted, Snowflake uses that role for **privilege evaluation** and **object creation**, and **secondary roles are not used**. [[2]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token)

The catch is enforcement:

* A **human user** (TYPE=PERSON) can generate PATs for themselves **without special privileges**, and can choose to omit ROLE\_RESTRICTION. [[3]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)
* If ROLE\_RESTRICTION is omitted, Snowflake evaluates privileges against the user’s **primary role and secondary roles**. [[2]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token)
* Snowflake’s built-in PAT policy controls can require role restriction **for service users**, but not (as of the current documented behavior) for person users. [[4]](https://docs.snowflake.com/en/sql-reference/sql/alter-authentication-policy)

That is why the “Miguel + Miguel\_cli” pattern (a dedicated service user that is the only user allowed to use PAT for the CLI) is not just a workaround—it’s the only approach that turns “best practice” into an enforceable boundary using documented primitives. [[5]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)

## How role restriction actually behaves in Snowflake PATs

### Role restriction is a hard gate, not a default

When you create a PAT using:

ALTER USER ADD PROGRAMMATIC ACCESS TOKEN <token\_name>
 ROLE\_RESTRICTION = '<role\_name>';

Snowflake documents the following security-critical behaviors:

* The ROLE\_RESTRICTION role **must already be granted** to the user; setting it does not magically grant the role. [[2]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token)
* During authentication with that token, the restricted role is used for **privilege evaluation** and **object creation**. [[2]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token)
* **Secondary roles are not used**, even if the user’s DEFAULT\_SECONDARY\_ROLES is ('ALL'). [[2]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token)
* If the restricted role is revoked from the user, authentication with that PAT fails. [[6]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token)
* The token secret is only shown in the **output** of the ALTER USER … ADD PROGRAMMATIC ACCESS TOKEN command (you do not get it again later). [[2]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token)

### If you omit ROLE\_RESTRICTION, you effectively allow multiple roles

Snowflake is explicit: if you omit ROLE\_RESTRICTION, objects are owned by the user’s primary role, and privileges are evaluated against the user’s **primary and secondary roles**. [[2]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token)

That is the exact “multi-role PAT” risk you are describing.

### The same concept shows up in Snowflake’s REST context rules

Snowflake’s REST API context docs state that **when using a PAT**, the requested role must be within the PAT’s ROLE\_RESTRICTION; asking for a more privileged role fails even if the user has that role granted. [[7]](https://docs.snowflake.com/en/developer-guide/snowflake-rest-api/setting-context)

This reinforces the mental model: **role restriction is the enforcement mechanism**—but only if you can ensure the token is created with a restriction and the user cannot mint other unrestricted tokens.

## Who can create PATs and what privileges are required

### Can “all users” generate their own PATs?

Under documented behavior, for **human users** (TYPE=PERSON):

* They **do not need any special privileges** to generate / modify / drop / display a PAT for themselves. [[8]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)
* If they omit the username in ALTER USER … ADD PROGRAMMATIC ACCESS TOKEN, it generates a token for the **currently logged in user**. [[2]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token)

So the answer is:

Yes—**by default, a person user can self-issue PATs for themselves** (subject to prerequisites like authentication policy and network policy rules). [[9]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)

### What privilege is needed to run ADD PROGRAMMATIC ACCESS TOKEN?

Snowflake’s SQL reference for ALTER USER … ADD PROGRAMMATIC ACCESS TOKEN states:

* The minimum privilege involved is **MODIFY PROGRAMMATIC AUTHENTICATION METHODS on the USER**, and it is **required only when generating a token for a user other than yourself**. [[2]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token)

Snowflake’s PAT overview further clarifies:

* If you are generating/managing a PAT for **a different user OR a service user**, you must use a role with **OWNERSHIP** or **MODIFY PROGRAMMATIC AUTHENTICATION METHODS** on that user. [[10]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)
* The privilege MODIFY PROGRAMMATIC AUTHENTICATION METHODS is defined as the ability to create/modify/delete/rotate/view programmatic access tokens and key pairs for that user. [[11]](https://docs.snowflake.com/en/user-guide/security-access-control-privileges)

So, concretely:

* **Self-service PAT (TYPE=PERSON, for yourself):** no special privilege required. [[3]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)
* **Admin issues PAT for someone else:** needs MODIFY PROGRAMMATIC AUTHENTICATION METHODS (or OWNERSHIP) on that user. [[12]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)
* **Admin issues PAT for a service user:** same requirement: OWNERSHIP or MODIFY PROGRAMMATIC AUTHENTICATION METHODS on that service user. [[10]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)

## What you can and cannot enforce with authentication policies

Snowflake gives you two major levers that matter here:

### Authentication policy can block PATs entirely for a user

Snowflake states that if an authentication policy limits authentication methods for a user, then that user **cannot generate or use PATs** unless the policy’s AUTHENTICATION\_METHODS includes PROGRAMMATIC\_ACCESS\_TOKEN. [[13]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)

That means:

* If you remove PROGRAMMATIC\_ACCESS\_TOKEN from the allowed methods *for that user (or that user type)*, you block both:
* **PAT creation** and
* **PAT usage**

…for that scope. [[13]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)

### Account policies can be applied separately to person users vs service users

Snowflake supports setting an authentication policy at the account level, and scoping it to:

* FOR ALL PERSON USERS (TYPE NULL or PERSON), or
* FOR ALL SERVICE USERS (TYPE SERVICE or LEGACY\_SERVICE). [[14]](https://docs.snowflake.com/en/sql-reference/sql/alter-account)

It also documents precedence:

* A policy set on a **specific user** or **specific user type** takes precedence over a broader account policy unless you override with FORCE. [[15]](https://docs.snowflake.com/en/sql-reference/sql/alter-account)

This is the key to the “Miguel + Miguel\_cli” design:

* Apply a **no-PAT** authentication policy to all person users.
* Apply a **PAT-allowed** authentication policy to service users (or to specific CLI users).

### PAT policy can tune network policy requirements and service-user role restriction behavior

Snowflake’s PAT policies (PAT\_POLICY) support:

* NETWORK\_POLICY\_EVALUATION = ENFORCED\_REQUIRED | ENFORCED\_NOT\_REQUIRED | NOT\_ENFORCED [[4]](https://docs.snowflake.com/en/sql-reference/sql/alter-authentication-policy)
* REQUIRE\_ROLE\_RESTRICTION\_FOR\_SERVICE\_USERS (default TRUE). [[4]](https://docs.snowflake.com/en/sql-reference/sql/alter-authentication-policy)

Importantly, Snowflake only documents **mandatory role restriction** for *service users*—not for person users. [[4]](https://docs.snowflake.com/en/sql-reference/sql/alter-authentication-policy)

## The only enforceable single-role pattern for Cortex Code CLI

### The design

* **Miguel (TYPE=PERSON):** uses browser-based SSO for interactive work; cannot use PAT at all. [[16]](https://docs.snowflake.com/en/user-guide/cortex-code/cli-reference)
* **Miguel\_cli (TYPE=SERVICE):** is the only identity allowed to authenticate with a PAT for CLI usage; PAT is forced to a single role (and ideally the service user only has that one meaningful role). [[17]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token)

Snowflake documents that service users are meant for non-interactive authentication and have restrictions such as: they **cannot log in using password or SAML SSO** and cannot enroll in MFA. [[18]](https://docs.snowflake.com/en/user-guide/admin-user-management)
That aligns with the goal: **PAT-only (or keypair/OAuth/WIF) non-interactive access**. [[19]](https://docs.snowflake.com/en/user-guide/admin-user-management)

### Why this is enforceable (and “same-user PAT restriction” is not)

* For TYPE=PERSON, users can self-issue PATs without special privileges. [[3]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)
* If that person user has multiple roles, they can create a PAT without ROLE\_RESTRICTION, which causes privilege evaluation to include primary + secondary roles. [[20]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token)
* There is no documented PAT policy setting to require role restriction for person users, only service users. [[4]](https://docs.snowflake.com/en/sql-reference/sql/alter-authentication-policy)

So, if you need **guaranteed single-role**, you must ensure the identity used by the CLI:

* is not a person user that can mint unrestricted tokens, and
* is controlled as a service identity whose PAT is role-restricted (and preferably whose role grants are minimal). [[21]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)

## A walkthrough in the style of a FastAPI guide

This is written as a practical “do this, get that” recipe—with the security boundary as the main feature.

### Create the CLI role

You’ll typically create a dedicated role that has only the privileges the CLI needs.

USE ROLE USERADMIN;

CREATE ROLE MIGUEL\_CLI\_ROLE
 COMMENT = 'Least-privileged role for Cortex Code CLI';

Only roles with the CREATE ROLE privilege (USERADMIN or higher by default) can create roles. [[22]](https://docs.snowflake.com/en/sql-reference/sql/create-role)

Tip: Keep this role narrow. The whole point of role restriction is that this role becomes the entire permission envelope for the token session. [[2]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token)

### Create the service user

USE ROLE USERADMIN;

CREATE USER MIGUEL\_CLI
 TYPE = SERVICE
 COMMENT = 'Service user for Cortex Code CLI';

Snowflake’s CREATE USER supports TYPE = SERVICE. [[23]](https://docs.snowflake.com/en/sql-reference/sql/create-user)
Service users are intended for non-interactive access and cannot use password or SAML SSO. [[18]](https://docs.snowflake.com/en/user-guide/admin-user-management)

### Grant the role to the service user

USE ROLE SECURITYADMIN;

GRANT ROLE MIGUEL\_CLI\_ROLE TO USER MIGUEL\_CLI;

ROLE\_RESTRICTION requires the role to already be granted to the user. [[2]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token)

### Put guardrails in place with authentication policies

You are going to apply two policies:

* One policy for **all person users** that does **not** allow PAT.
* One policy for **service users** that **does** allow PAT.

Create the policies:

-- Stored in some admin schema of your choice
CREATE AUTHENTICATION POLICY person\_users\_no\_pat
 AUTHENTICATION\_METHODS = ('SAML', 'OAUTH', 'KEYPAIR', 'WORKLOAD\_IDENTITY', 'PASSWORD');

CREATE AUTHENTICATION POLICY service\_users\_pat\_allowed
 AUTHENTICATION\_METHODS = ('PROGRAMMATIC\_ACCESS\_TOKEN', 'KEYPAIR', 'OAUTH', 'WORKLOAD\_IDENTITY')
 PAT\_POLICY = (
 NETWORK\_POLICY\_EVALUATION = ENFORCED\_REQUIRED
 );

Snowflake documents AUTHENTICATION\_METHODS and PAT\_POLICY syntax for CREATE AUTHENTICATION POLICY. [[24]](https://docs.snowflake.com/en/sql-reference/sql/create-authentication-policy)

Apply them at the account level by user type:

ALTER ACCOUNT SET AUTHENTICATION POLICY person\_users\_no\_pat
 FOR ALL PERSON USERS;

ALTER ACCOUNT SET AUTHENTICATION POLICY service\_users\_pat\_allowed
 FOR ALL SERVICE USERS;

Snowflake explicitly supports FOR ALL PERSON USERS and FOR ALL SERVICE USERS in ALTER ACCOUNT SET AUTHENTICATION POLICY, including how user-type scoping and precedence work. [[14]](https://docs.snowflake.com/en/sql-reference/sql/alter-account)

Note: If PAT is not in the allowed authentication methods for a user, Snowflake says that user cannot generate or use PATs. That is exactly what you want for person users. [[13]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)

### Generate the role-restricted PAT for the service user

Because you are generating a PAT for a **service user** (and typically not logged in as that service user), you need a role with OWNERSHIP or MODIFY PROGRAMMATIC AUTHENTICATION METHODS on that user. [[25]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)

Then:

ALTER USER MIGUEL\_CLI ADD PROGRAMMATIC ACCESS TOKEN cortex\_cli\_token
 ROLE\_RESTRICTION = 'MIGUEL\_CLI\_ROLE'
 DAYS\_TO\_EXPIRY = 30
 COMMENT = 'Token for Cortex Code CLI';

Role restriction is required for service users by default. [[26]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token)
Copy token\_secret immediately; it is only shown in the output of this command. [[2]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token)

### Configure Cortex Code CLI

Snowflake’s Cortex Code CLI reference shows a connections.toml sample. For PAT auth, it uses password = "<PAT>" and notes you should omit the authenticator value (which is used for browser-based SSO). [[27]](https://docs.snowflake.com/en/user-guide/cortex-code/cli-reference)

Create/edit ~/.snowflake/connections.toml:

[miguel\_cli]
account = "<ACCOUNT>"
user = "MIGUEL\_CLI"
password = "<PASTE\_TOKEN\_SECRET\_HERE>"
warehouse = "<WAREHOUSE>"
role = "MIGUEL\_CLI\_ROLE"
database = "<DATABASE>"
schema = "<SCHEMA>"

This matches the documented Cortex Code CLI format. [[27]](https://docs.snowflake.com/en/user-guide/cortex-code/cli-reference)
It also aligns with Snowflake’s statement that a PAT can be used as a **replacement for a password** in command-line clients. [[28]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)

Run:

cortex -c miguel\_cli

The CLI supports -c for selecting a specific connection. [[29]](https://docs.snowflake.com/en/user-guide/cortex-code/cli-reference)

Tip: If someone tries to “change role” in the connection, the token-bound role restriction should prevent using a more privileged role than the PAT allows. Snowflake states this explicitly for PAT-authenticated REST requests, and the PAT’s restricted role is the one used for privilege evaluation during authentication. [[30]](https://docs.snowflake.com/en/developer-guide/snowflake-rest-api/setting-context)

## Hardening and operational controls that matter in practice

### Keep network policy evaluation strict unless you truly can’t

By default, Snowflake requires that a user be subject to a network policy with network rules to generate/use PATs, and it explains how NETWORK\_POLICY\_EVALUATION can modify this requirement. [[31]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)

If you set:

* NETWORK\_POLICY\_EVALUATION = ENFORCED\_REQUIRED: the user must be subject to a network policy (default behavior). [[31]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)
* ENFORCED\_NOT\_REQUIRED: user does not need a network policy to generate/use PATs, but if they are subject to one, it is still enforced. [[31]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)
* NOT\_ENFORCED: network policy is not required and is not enforced even if present. [[31]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)

For a “single-role CLI token” threat model, broadening PAT usability beyond network policy constraints is usually the opposite of what you want—unless you have compensating controls on the workstation and secrets handling.

### Audit and lifecycle controls

A few behaviors from Snowflake’s PAT documentation are operationally important:

* A user can have **up to 15** programmatic access tokens. [[2]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token)
* Tokens are time-bound; once created, you cannot “recover” the secret; generating a token prints it once. [[2]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token)
* Snowflake provides SHOW USER PROGRAMMATIC ACCESS TOKENS and also references querying SNOWFLAKE.ACCOUNT\_USAGE.CREDENTIALS for PAT rows (type = 'PAT'). [[32]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)

### Use Cortex Code CLI managed settings as a defense-in-depth layer

Cortex Code CLI supports **managed settings** (system-managed JSON) that administrators can deploy so users generally cannot change them without elevated privileges. Those policies can restrict allowed account patterns and disable bypass capabilities. [[33]](https://docs.snowflake.com/en/user-guide/cortex-code/settings)

This does not replace Snowflake-side enforcement (auth policies + service user + role-restricted PAT), but it can reduce accidental misconfiguration on developer machines. [[33]](https://docs.snowflake.com/en/user-guide/cortex-code/settings)

## Bottom line

* **Privilege to run ALTER USER … ADD PROGRAMMATIC ACCESS TOKEN for yourself (TYPE=PERSON):** none special. [[3]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)
* **Privilege to generate/manage PATs for another user or a service user:** OWNERSHIP or MODIFY PROGRAMMATIC AUTHENTICATION METHODS on that user. [[25]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens)
* **Enforce “Cortex Code CLI can only ever use one role”:** use a dedicated **TYPE=SERVICE** CLI user, issue a role-restricted PAT for that user, and block PAT for person users via authentication policy scoping (FOR ALL PERSON USERS). [[34]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token)

[[1]](https://docs.snowflake.com/en/user-guide/cortex-code/cli-reference) [[16]](https://docs.snowflake.com/en/user-guide/cortex-code/cli-reference) [[27]](https://docs.snowflake.com/en/user-guide/cortex-code/cli-reference) [[29]](https://docs.snowflake.com/en/user-guide/cortex-code/cli-reference) https://docs.snowflake.com/en/user-guide/cortex-code/cli-reference

<https://docs.snowflake.com/en/user-guide/cortex-code/cli-reference>

[[2]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token) [[6]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token) [[17]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token) [[20]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token) [[26]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token) [[34]](https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token) ALTER USER … ADD PROGRAMMATIC ACCESS TOKEN (PAT) | Snowflake Documentation

<https://docs.snowflake.com/en/sql-reference/sql/alter-user-add-programmatic-access-token>

[[3]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens) [[5]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens) [[8]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens) [[9]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens) [[10]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens) [[12]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens) [[13]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens) [[21]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens) [[25]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens) [[28]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens) [[31]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens) [[32]](https://docs.snowflake.com/en/user-guide/programmatic-access-tokens) Using programmatic access tokens for authentication | Snowflake Documentation

<https://docs.snowflake.com/en/user-guide/programmatic-access-tokens>

[[4]](https://docs.snowflake.com/en/sql-reference/sql/alter-authentication-policy) https://docs.snowflake.com/en/sql-reference/sql/alter-authentication-policy

<https://docs.snowflake.com/en/sql-reference/sql/alter-authentication-policy>

[[7]](https://docs.snowflake.com/en/developer-guide/snowflake-rest-api/setting-context) [[30]](https://docs.snowflake.com/en/developer-guide/snowflake-rest-api/setting-context) https://docs.snowflake.com/en/developer-guide/snowflake-rest-api/setting-context

<https://docs.snowflake.com/en/developer-guide/snowflake-rest-api/setting-context>

[[11]](https://docs.snowflake.com/en/user-guide/security-access-control-privileges) https://docs.snowflake.com/en/user-guide/security-access-control-privileges

<https://docs.snowflake.com/en/user-guide/security-access-control-privileges>

[[14]](https://docs.snowflake.com/en/sql-reference/sql/alter-account) [[15]](https://docs.snowflake.com/en/sql-reference/sql/alter-account) ALTER ACCOUNT | Snowflake Documentation

<https://docs.snowflake.com/en/sql-reference/sql/alter-account>

[[18]](https://docs.snowflake.com/en/user-guide/admin-user-management) [[19]](https://docs.snowflake.com/en/user-guide/admin-user-management) https://docs.snowflake.com/en/user-guide/admin-user-management

<https://docs.snowflake.com/en/user-guide/admin-user-management>

[[22]](https://docs.snowflake.com/en/sql-reference/sql/create-role) CREATE ROLE | Snowflake Documentation

<https://docs.snowflake.com/en/sql-reference/sql/create-role>

[[23]](https://docs.snowflake.com/en/sql-reference/sql/create-user) https://docs.snowflake.com/en/sql-reference/sql/create-user

<https://docs.snowflake.com/en/sql-reference/sql/create-user>

[[24]](https://docs.snowflake.com/en/sql-reference/sql/create-authentication-policy) https://docs.snowflake.com/en/sql-reference/sql/create-authentication-policy

<https://docs.snowflake.com/en/sql-reference/sql/create-authentication-policy>

[[33]](https://docs.snowflake.com/en/user-guide/cortex-code/settings) https://docs.snowflake.com/en/user-guide/cortex-code/settings

<https://docs.snowflake.com/en/user-guide/cortex-code/settings>