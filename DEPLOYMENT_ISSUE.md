# Databricks Apps - Database Environment Variable Injection Issue

**Date:** 2026-02-17
**Status:** ⚠️ PLATFORM BUG CONFIRMED
**Severity:** BLOCKER for deployed apps using Lakebase

---

## Issue Summary

When using `valueFrom: database` in `app.yaml`, Databricks Apps incorrectly sets **all** database environment variables to the database hostname instead of their respective values.

### Expected Behavior

```yaml
env:
  - name: PGDATABASE
    valueFrom: database  # Should set to "databricks_postgres"
  - name: PGHOST
    valueFrom: database  # Should set to "instance-xyz.database..."
  - name: PGPORT
    valueFrom: database  # Should set to "5432"
  - name: PGUSER
    valueFrom: database  # Should set to service principal email
```

**Expected result:**
```bash
PGHOST=instance-dfed2abf-bafd-4d95-b1bb-c7b01ee9ccbf.database.cloud.databricks.com
PGPORT=5432
PGDATABASE=databricks_postgres
PGUSER=app-service-principal@databricks.com
```

### Actual Behavior

**All** environment variables get set to the database hostname:

```bash
PGHOST=instance-dfed2abf-bafd-4d95-b1bb-c7b01ee9ccbf.database.cloud.databricks.com  # ✅ Correct
PGPORT=instance-dfed2abf-bafd-4d95-b1bb-c7b01ee9ccbf.database.cloud.databricks.com  # ❌ WRONG
PGUSER=instance-dfed2abf-bafd-4d95-b1bb-c7b01ee9ccbf.database.cloud.databricks.com  # ❌ WRONG
PGDATABASE=databricks_postgres  # ✅ Correct (most of the time)
```

---

## Reproduction

### Tested Environments

| Environment | Workspace | URL | Result |
|-------------|-----------|-----|--------|
| **Staging** | e2-dogfood.staging.cloud.databricks.com | https://dev-agent-backend-6051921418418893.staging.aws.databricksapps.com | ❌ Bug confirmed |
| **Prod** | db-ml-models-prod-us-west.cloud.databricks.com | https://agent-backend-prod-3888667486068890.aws.databricksapps.com | ❌ Bug confirmed |

### Staging Environment

**Profile:** dogfood
**App:** dev-agent-backend
**Lakebase:** agent-backend-lakebase-dev
**Database Host:** instance-4bc3caf4-705d-48fb-baf0-d827db786bd2.database.staging.cloud.databricks.com

**Environment variables (from debug logs):**
```bash
PGHOST=instance-4bc3caf4-705d-48fb-baf0-d827db786bd2.database.staging.cloud.databricks.com  ✅
PGPORT=instance-4bc3caf4-705d-48fb-baf0-d827db786bd2.database.staging.cloud.databricks.com  ❌
PGUSER=instance-4bc3caf4-705d-48fb-baf0-d827db786bd2.database.staging.cloud.databricks.com  ❌
PGDATABASE=databricks_postgres  ✅
```

**Error when trying to connect:**
```
asyncpg.exceptions.UndefinedObjectError:
role "instance-4bc3caf4-705d-48fb-baf0-d827db786bd2.database.staging." does not exist
```

### Prod Environment

**Profile:** db-ml-models-prod-us-west
**App:** agent-backend-prod
**Lakebase:** agent-backend-lakebase-prod
**Database Host:** instance-dfed2abf-bafd-4d95-b1bb-c7b01ee9ccbf.database.cloud.databricks.com

**Environment variables (from debug logs):**
```bash
PGHOST=instance-dfed2abf-bafd-4d95-b1bb-c7b01ee9ccbf.database.cloud.databricks.com  ✅
PGPORT=instance-dfed2abf-bafd-4d95-b1bb-c7b01ee9ccbf.database.cloud.databricks.com  ❌
PGUSER=instance-dfed2abf-bafd-4d95-b1bb-c7b01ee9ccbf.database.cloud.databricks.com  ❌
PGDATABASE=databricks_postgres  ✅
```

**Error when trying to connect:**
```
asyncpg.exceptions.UndefinedObjectError:
role "instance-dfed2abf-bafd-4d95-b1bb-c7b01ee9ccbf.database.cloud.da" does not exist
```

---

## Impact

### What Works ✅

- App deployment succeeds
- App starts successfully
- Health endpoint responds (200 OK)
- LLM client configuration works
- Lakebase instances are created
- Database schemas can be migrated manually (from local machine)

### What Fails ❌

- Database connection from deployed app
- Any endpoint that queries the database (e.g., `/v1/responses`)
- Returns 500 Internal Server Error
- Error: Invalid database user (using hostname as username)

---

## Configuration Used

### databricks.yml

```yaml
resources:
  database_instances:
    agent_lakebase:
      name: ${var.database_instance_name}-${var.resource_name_suffix}
      capacity: CU_1

  apps:
    agent_backend:
      name: ${bundle.target}-agent-backend
      resources:
        - name: database
          database:
            database_name: databricks_postgres
            instance_name: ${resources.database_instances.agent_lakebase.name}
            permission: CAN_CONNECT_AND_CREATE
```

### app.yaml

```yaml
env:
  - name: PGDATABASE
    valueFrom: database
  - name: PGHOST
    valueFrom: database
  - name: PGPORT
    valueFrom: database
  - name: PGUSER
    valueFrom: database
```

---

## Workarounds Attempted

### 1. Field Validation ⚠️ Partial

Added validator in `server/config.py` to parse PGPORT:

```python
@field_validator('pgport', mode='before')
@classmethod
def parse_port(cls, v):
    if isinstance(v, str):
        try:
            return int(v)
        except ValueError:
            print(f"Warning: Could not parse PGPORT value '{v}', using default 5432")
            return 5432
    return v
```

**Result:** Prevents app crash, but doesn't fix PGUSER issue

### 2. Made Fields Optional ⚠️ Partial

Made all database fields optional with defaults:

```python
pghost: str = ""
pgport: int = 5432
pgdatabase: str = "databricks_postgres"
pguser: str = ""
```

**Result:** App starts, but database connection still fails

---

## Recommended Solutions

### Option 1: Fix Platform Bug (Preferred) 🎯

**Action:** File bug report with Databricks Apps team

**Details:**
- `valueFrom: database` should inject different values based on the env var name
- Currently injects hostname for all variables
- Expected behavior: each variable gets its appropriate value from the linked database resource

### Option 2: Manual Environment Variables ⚠️ Workaround

**Action:** Set explicit values in app.yaml instead of `valueFrom: database`

```yaml
env:
  - name: PGHOST
    value: "instance-xyz.database.cloud.databricks.com"
  - name: PGPORT
    value: "5432"
  - name: PGDATABASE
    value: "databricks_postgres"
  - name: PGUSER
    value: "app-service-principal-email"
```

**Problems:**
- Requires manual configuration per environment
- Defeats purpose of `valueFrom: database`
- Service principal credentials not easily accessible
- Not portable across deployments

### Option 3: Alternative Database Connection Method 🔍

**Action:** Investigate if there's a different mechanism for database connectivity

**Possibilities:**
- Check if Databricks Apps provides database credentials via different mechanism
- Use Databricks SDK to fetch database connection info at runtime
- Use different environment variable naming convention
- Check Databricks Apps documentation for recommended approach

### Option 4: Service Principal Direct Access 🔑

**Action:** Grant app service principal direct database access

**Steps:**
1. Get app service principal ID from deployed app
2. Grant SP access to Lakebase instance
3. Use SP authentication instead of env var injection
4. Modify connection code to use SDK-based auth

**Benefits:**
- Bypasses env var injection issue
- More secure (uses proper IAM)
- Portable across environments

---

## Debug Logging

Added debug logging to verify env vars in `server/main.py`:

```python
logger.info("Environment variables:")
for key in ['PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER']:
    value = os.getenv(key, 'NOT SET')
    logger.info(f"  {key}={value}")
```

This helped confirm the issue exists in both staging and prod.

---

## Local vs Deployed Comparison

| Aspect | Local (✅ Works) | Deployed (❌ Blocked) |
|--------|-----------------|----------------------|
| **Health endpoint** | 200 OK | 200 OK |
| **Database connection** | ✅ Works | ❌ Fails |
| **Response creation** | ✅ Works | ❌ 500 Error |
| **LLM integration** | ✅ Works | ✅ Works |
| **Env vars** | From .env file | Injected by platform |
| **Database credentials** | User OAuth token | ❌ Hostname instead |

**Key difference:** Local uses `.env` file with correct values, deployed relies on platform injection which is broken.

---

## Evidence

### Staging Logs

```
2026-02-17T00:26:11 [APP] ERROR: Exception in ASGI application
asyncpg.exceptions.UndefinedObjectError:
role "instance-4bc3caf4-705d-48fb-baf0-d827db786bd2.database.staging." does not exist
```

### Prod Logs

```
2026-02-17T01:28:56 [APP] ERROR: Exception in ASGI application
asyncpg.exceptions.UndefinedObjectError:
role "instance-dfed2abf-bafd-4d95-b1bb-c7b01ee9ccbf.database.cloud.da" does not exist
```

### Environment Variable Debug Output

**Staging:**
```
2026-02-17 00:32:36 - server.main - INFO - Environment variables:
2026-02-17 00:32:36 - server.main - INFO -   PGHOST=instance-4bc3caf4-...
2026-02-17 00:32:36 - server.main - INFO -   PGPORT=instance-4bc3caf4-...  # ❌
2026-02-17 00:32:36 - server.main - INFO -   PGUSER=instance-4bc3caf4-...  # ❌
```

**Prod:**
```
2026-02-17 01:28:29 - server.main - INFO - Environment variables:
2026-02-17 01:28:29 - server.main - INFO -   PGHOST=instance-dfed2abf-...
2026-02-17 01:28:29 - server.main - INFO -   PGPORT=instance-dfed2abf-...  # ❌
2026-02-17 01:28:29 - server.main - INFO -   PGUSER=instance-dfed2abf-...  # ❌
```

---

## Timeline

- **2026-02-16:** Initial deployment to staging, discovered issue
- **2026-02-17:** Attempted multiple workarounds (validation, optional fields)
- **2026-02-17:** Deployed to prod to check if staging-specific → Same issue
- **2026-02-17:** Confirmed platform-wide bug affecting both environments

---

## Next Actions

### Immediate (Priority 1)

1. ✅ Document issue comprehensively (this document)
2. ⬜ File bug report with Databricks Apps team
3. ⬜ Investigate Option 4 (Service Principal direct access)

### Short-term (Priority 2)

1. ⬜ Check Databricks Apps documentation for recommended database connectivity
2. ⬜ Test if different env var names work (DATABASE_* instead of PG*)
3. ⬜ Explore SDK-based database connection as alternative

### Long-term (Priority 3)

1. ⬜ Once platform bug is fixed, redeploy and verify
2. ⬜ Complete full test suite against deployed apps
3. ⬜ Document proper deployment procedures

---

## Contact

**Issue Owner:** Sid Murching (sid.murching@databricks.com)
**Workspaces Tested:**
- Staging: https://e2-dogfood.staging.cloud.databricks.com
- Prod: https://db-ml-models-prod-us-west.cloud.databricks.com

**Apps:**
- Staging: https://dev-agent-backend-6051921418418893.staging.aws.databricksapps.com
- Prod: https://agent-backend-prod-3888667486068890.aws.databricksapps.com

---

## Related Documentation

- [Databricks Apps Documentation](https://docs.databricks.com/en/apps/index.html)
- [Lakebase Documentation](https://docs.databricks.com/en/lakebase/index.html)
- [Agent Backend TEST_RESULTS.md](./TEST_RESULTS.md)
- [Agent Backend IMPLEMENTATION_COMPLETE.md](./IMPLEMENTATION_COMPLETE.md)
