# API documentation

* `openapi.json`: the OpenAPI document of the current API, written by `python -m app.openapi` (in `services/api`).
  CI and `scripts/ci-local.sh` fail when the committed file differs from the code ("API · OpenAPI drift"). Production
  does not publish `/openapi.json` or `/docs`; use this file.
* `phase-N-contract.md`: what each phase added or changed, with its acceptance tests. The latest contract wins
  where two disagree.
* `../erd.md`: entity-relationship diagrams per schema, written by `python -m app.erd` and checked the same way.

## Version policy

* The API version is `API_VERSION` in `services/api/app/main.py` (`info.version` in the document). It follows
  semantic versioning: minor for additions, patch for fixes.
* `/api/v1` changes only **additively**: new endpoints, new optional request fields, new response fields, new error
  codes on new paths. Clients must ignore unknown response fields.
* A breaking change (removing or renaming a field or endpoint, changing a type or a meaning, making a field
  required) needs `/api/v2`. Both versions run side by side for at least **six months**, and the old one answers
  with a `Deprecation` header and a `Sunset` date during that time.
* The citizen app is the client that updates slowest: before a `/api/v1` endpoint is retired, the minimum app
  version that no longer uses it must be enforced through the store and the app's update prompt.
